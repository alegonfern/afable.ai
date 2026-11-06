"""El inventario de verdad (26-10-2026): stock con lo comprometido y lo que viene en camino,
entradas y salidas sin orden, kardex con costo promedio, valorización a una fecha, rotación,
tomas de inventario y carga inicial desde Excel.

El stock no se guarda en ninguna parte: es la suma de los MovimientoStock. Sobre eso:
    físico      lo que hay en bodega (suma de movimientos)
    reservado   lo que falta entregar de órdenes de venta confirmadas
    disponible  físico − reservado: lo que se puede vender
    por recibir lo que falta recibir de órdenes de compra confirmadas
    proyectado  disponible + por recibir
"""
from collections import defaultdict
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Max, Min, Q, Sum
from django.utils import timezone

from . import planillas
from .models import (CERO, COMPRA, SIN_INVENTARIO, VENTA, Bodega, ConfiguracionComercial, ConteoInventario,
                     LineaConteo, LineaPedido, MovimientoStock, Pedido, Producto, Secuencia, stock)
from .operaciones import ErrorComercial, costo_promedio, decimal

ENTRADAS_CON_COSTO = (MovimientoStock.COMPRA, MovimientoStock.INICIAL, MovimientoStock.ENTRADA)
MOTIVOS_ENTRADA = dict(MovimientoStock.MOTIVOS_ENTRADA)
MOTIVOS_SALIDA = dict(MovimientoStock.MOTIVOS_SALIDA)
MAX_MOVIMIENTOS = 500


def num(d):
    """Decimal → texto sin ceros de más ("12.5", "3"); None queda None."""
    if d is None:
        return None
    return format(Decimal(d).normalize(), 'f')


def pesos(d):
    return int(Decimal(d or 0).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def nivel(org):
    return ConfiguracionComercial.de(org).nivel_inventario


def exigir_activo(org):
    if nivel(org) == SIN_INVENTARIO:
        raise ErrorComercial('El inventario está desactivado. Actívelo en la configuración de Inventario '
                             '(básico o completo) para registrar movimientos.')


def _bodega(org, bodega_id):
    if bodega_id:
        b = Bodega.objects.filter(organization=org, pk=bodega_id, activa=True).first()
        if b is None:
            raise ErrorComercial('La bodega no existe o está desactivada.')
        return b
    return Bodega.principal_de(org)


def _fecha(valor, por_defecto=None):
    if valor in (None, ''):
        return por_defecto
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(str(valor)[:10])
    except ValueError:
        raise ErrorComercial(f'«{valor}» no es una fecha válida (AAAA-MM-DD).')


# ── Lo comprometido y lo que viene ────────────────────────────────────────────

def pendientes(org, tipo):
    """{(producto_id, bodega_id): cantidad} que falta entregar (VENTA) o recibir (COMPRA) de las
    órdenes confirmadas. Sin bodega en la orden, la principal."""
    principal = Bodega.principal_de(org).id
    salida = defaultdict(lambda: CERO)
    lineas = (LineaPedido.objects
              .filter(pedido__organization=org, pedido__tipo=tipo, pedido__estado=Pedido.CONFIRMADO,
                      producto__tipo=Producto.ALMACENABLE)
              .values('producto_id', 'pedido__bodega_id', 'cantidad', 'cantidad_entregada'))
    for l in lineas:
        falta = (l['cantidad'] or CERO) - (l['cantidad_entregada'] or CERO)
        if falta > 0:
            salida[(l['producto_id'], l['pedido__bodega_id'] or principal)] += falta
    return salida


def _sumar(mapa, producto_id, bodega_id=None):
    return sum((c for (p, b), c in mapa.items() if p == producto_id and (bodega_id is None or b == bodega_id)), CERO)


def estado_de(fisico, disponible, minimo, maximo):
    if fisico < 0:
        return 'negativo'
    if fisico == 0:
        return 'sin_stock'
    if minimo and minimo > 0 and disponible < minimo:
        return 'bajo_minimo'
    if maximo and maximo > 0 and fisico > maximo:
        return 'sobre_maximo'
    return 'ok'


def filas_stock(org, bodega_id=None, familia=None, estado=None, q=None):
    """Una fila por producto almacenable activo, con su físico, reservado, disponible, por recibir,
    proyectado, costo promedio, valor y estado. `bodega_id` acota todo a esa bodega."""
    bodegas = {b.id: b for b in Bodega.objects.filter(organization=org)}
    existencias = stock(org)
    reservas = pendientes(org, VENTA)
    en_camino = pendientes(org, COMPRA)
    ultimos = dict(MovimientoStock.objects.filter(organization=org).values('producto')
                   .annotate(u=Max('fecha')).values_list('producto', 'u'))
    qs = Producto.objects.filter(organization=org, tipo=Producto.ALMACENABLE, activo=True)
    if familia:
        qs = qs.filter(familia=familia)
    if q:
        qs = qs.filter(Q(nombre__icontains=q) | Q(codigo__icontains=q) | Q(codigo_barras__icontains=q))
    bid = int(bodega_id) if bodega_id else None
    filas = []
    for p in qs:
        fisico = _sumar(existencias, p.id, bid)
        reservado = _sumar(reservas, p.id, bid)
        por_recibir = _sumar(en_camino, p.id, bid)
        disponible = fisico - reservado
        costo = costo_promedio(org, p)
        fila = {
            'id': p.id, 'codigo': p.codigo, 'nombre': p.nombre, 'familia': p.familia, 'unidad': p.unidad,
            'ubicacion': p.ubicacion, 'codigo_barras': p.codigo_barras,
            'fisico': num(fisico), 'reservado': num(reservado), 'disponible': num(disponible),
            'por_recibir': num(por_recibir), 'proyectado': num(disponible + por_recibir),
            'stock_minimo': num(p.stock_minimo), 'stock_maximo': num(p.stock_maximo),
            'costo_promedio': num(costo), 'valor': pesos(max(fisico, CERO) * costo),
            'estado': estado_de(fisico, disponible, p.stock_minimo, p.stock_maximo),
            'ultimo_movimiento': ultimos.get(p.id).isoformat() if ultimos.get(p.id) else None,
            'por_bodega': [{'bodega_id': b, 'nombre': bodegas[b].nombre if b in bodegas else '', 'cantidad': num(c)}
                           for (pid, b), c in sorted(existencias.items(), key=lambda x: x[0][1])
                           if pid == p.id and c != 0 and (bid is None or b == bid)],
        }
        if estado and fila['estado'] != estado:
            continue
        filas.append(fila)
    return filas


def vista_stock(org, bodega_id=None, familia=None, estado=None, q=None):
    activo = nivel(org) != SIN_INVENTARIO
    productos = filas_stock(org, bodega_id, familia, estado, q) if activo else []
    return {
        'nivel': nivel(org),
        'bodegas': [{'id': b.id, 'nombre': b.nombre, 'principal': b.principal}
                    for b in Bodega.objects.filter(organization=org, activa=True)] if activo else [],
        'familias': sorted({f for f in Producto.objects.filter(organization=org, tipo=Producto.ALMACENABLE)
                            .exclude(familia='').values_list('familia', flat=True)}) if activo else [],
        'motivos_entrada': [{'valor': v, 'nombre': n} for v, n in MovimientoStock.MOTIVOS_ENTRADA],
        'motivos_salida': [{'valor': v, 'nombre': n} for v, n in MovimientoStock.MOTIVOS_SALIDA],
        'productos': productos,
        'totales': {'valor': sum(p['valor'] for p in productos), 'productos': len(productos)},
    }


def resumen(org, bodega_id=None):
    if nivel(org) == SIN_INVENTARIO:
        return {'nivel': SIN_INVENTARIO, 'kpis': {k: 0 for k in (
            'valor_total', 'productos', 'con_stock', 'sin_stock', 'bajo_minimo', 'comprometido_sin_stock',
            'inmovilizado_valor', 'inmovilizado_productos')}, 'alertas': [], 'por_familia': [], 'por_bodega': []}
    filas = filas_stock(org, bodega_id)
    alertas = []
    for f in filas:
        fisico, reservado = Decimal(f['fisico']), Decimal(f['reservado'])
        if f['estado'] == 'negativo':
            alertas.append({'tipo': 'negativo', 'producto_id': f['id'], 'nombre': f['nombre'],
                            'detalle': f'El stock quedó en {f["fisico"]} {f["unidad"]}: revise las entregas o haga una toma de inventario.'})
        if reservado > max(fisico, CERO):
            alertas.append({'tipo': 'comprometido', 'producto_id': f['id'], 'nombre': f['nombre'],
                            'detalle': f'Hay {f["reservado"]} {f["unidad"]} vendidos por entregar y {f["fisico"]} en bodega.'})
        elif f['estado'] == 'sin_stock' and (Decimal(f['stock_minimo']) > 0 or f['ultimo_movimiento']):
            alertas.append({'tipo': 'sin_stock', 'producto_id': f['id'], 'nombre': f['nombre'],
                            'detalle': 'Sin stock' + (f' · vienen {f["por_recibir"]} en camino' if Decimal(f['por_recibir']) else '.')})
        elif f['estado'] == 'bajo_minimo':
            alertas.append({'tipo': 'bajo_minimo', 'producto_id': f['id'], 'nombre': f['nombre'],
                            'detalle': f'Disponible {f["disponible"]} de un mínimo de {f["stock_minimo"]} {f["unidad"]}.'})
    orden = {'negativo': 0, 'comprometido': 1, 'sin_stock': 2, 'bajo_minimo': 3}
    alertas.sort(key=lambda a: orden[a['tipo']])
    familias = defaultdict(lambda: {'productos': 0, 'valor': 0})
    for f in filas:
        clave = f['familia'] or 'Sin familia'
        familias[clave]['productos'] += 1
        familias[clave]['valor'] += f['valor']
    por_bodega = []
    for b in Bodega.objects.filter(organization=org, activa=True):
        if bodega_id and int(bodega_id) != b.id:
            continue
        valor = 0
        for f in filas:
            cant = next((Decimal(x['cantidad']) for x in f['por_bodega'] if x['bodega_id'] == b.id), CERO)
            valor += pesos(max(cant, CERO) * Decimal(f['costo_promedio']))
        por_bodega.append({'bodega_id': b.id, 'nombre': b.nombre, 'valor': valor})
    rot = rotacion(org)
    return {
        'nivel': nivel(org),
        'kpis': {
            'valor_total': sum(f['valor'] for f in filas), 'productos': len(filas),
            'con_stock': sum(1 for f in filas if Decimal(f['fisico']) > 0),
            'sin_stock': sum(1 for f in filas if Decimal(f['fisico']) <= 0),
            'bajo_minimo': sum(1 for f in filas if f['estado'] == 'bajo_minimo'),
            'comprometido_sin_stock': sum(1 for f in filas if Decimal(f['reservado']) > max(Decimal(f['fisico']), CERO)),
            'inmovilizado_valor': sum(x['valor'] for x in rot['inmovilizados']),
            'inmovilizado_productos': len(rot['inmovilizados']),
        },
        'alertas': alertas[:30],
        'por_familia': sorted(({'familia': k, **v} for k, v in familias.items()), key=lambda x: -x['valor']),
        'por_bodega': por_bodega,
    }


# ── Entradas y salidas sin orden ──────────────────────────────────────────────

def _producto_almacenable(org, producto):
    if not isinstance(producto, Producto):
        producto = Producto.objects.filter(organization=org, pk=producto).first()
    if producto is None:
        raise ErrorComercial('El producto no existe.')
    if not producto.lleva_stock:
        raise ErrorComercial('Solo los productos almacenables llevan stock.')
    return producto


@transaction.atomic
def entrada_manual(org, producto, bodega_id=None, cantidad=None, costo_unitario=None, motivo='', referencia='',
                   fecha=None, usuario=None):
    """Entra mercadería sin una orden de compra: stock inicial, producción, una devolución sin orden,
    un sobrante. Con costo, cuenta para el costo promedio; sin costo, entra al costo promedio actual."""
    exigir_activo(org)
    producto = _producto_almacenable(org, producto)
    if motivo not in MOTIVOS_ENTRADA:
        raise ErrorComercial('Indique el motivo de la entrada.')
    bodega = _bodega(org, bodega_id)
    cant = decimal(cantidad, 'La cantidad', Decimal('0.001'))
    costo = decimal(costo_unitario, 'El costo', 0) if costo_unitario not in (None, '') else costo_promedio(org, producto)
    return MovimientoStock.objects.create(
        organization=org, producto=producto, bodega=bodega, cantidad=cant,
        tipo=MovimientoStock.INICIAL if motivo == 'inicial' else MovimientoStock.ENTRADA, motivo=motivo,
        fecha=_fecha(fecha, timezone.localdate()), costo_unitario=costo,
        referencia=(str(referencia or '') or MOTIVOS_ENTRADA[motivo])[:120], creado_por=usuario)


@transaction.atomic
def salida_manual(org, producto, bodega_id=None, cantidad=None, motivo='', referencia='', fecha=None, usuario=None):
    """Sale mercadería sin una orden de venta: merma, vencimiento, consumo interno, una muestra. No
    deja el stock de la bodega en negativo."""
    exigir_activo(org)
    producto = _producto_almacenable(org, producto)
    if motivo not in MOTIVOS_SALIDA:
        raise ErrorComercial('Indique el motivo de la salida.')
    bodega = _bodega(org, bodega_id)
    cant = decimal(cantidad, 'La cantidad', Decimal('0.001'))
    hay = stock(org, producto=producto, bodega=bodega).get((producto.id, bodega.id), CERO)
    if cant > hay:
        raise ErrorComercial(f'En {bodega.nombre} hay {num(hay)} {producto.unidad} de {producto.nombre}: '
                             f'no pueden salir {num(cant)}.')
    return MovimientoStock.objects.create(
        organization=org, producto=producto, bodega=bodega, cantidad=-cant, tipo=MovimientoStock.SALIDA,
        motivo=motivo, fecha=_fecha(fecha, timezone.localdate()), costo_unitario=costo_promedio(org, producto),
        referencia=(str(referencia or '') or MOTIVOS_SALIDA[motivo])[:120], creado_por=usuario)


# ── Kardex y movimientos ──────────────────────────────────────────────────────

def _documento(m):
    if m.entrega_id and m.entrega and m.entrega.pedido_id:
        pedido = m.entrega.pedido
        modulo = 'ventas' if pedido.tipo == VENTA else 'compras'
        return {'numero': f'{m.entrega.numero} · {pedido.numero}', 'enlace': f'/app/{modulo}/ordenes/{pedido.id}'}
    if m.conteo_id and m.conteo:
        return {'numero': m.conteo.numero, 'enlace': f'/app/inventario/conteos/{m.conteo_id}'}
    return None


def _usuario(u):
    if not u:
        return ''
    nombre = f'{u.first_name} {u.last_name}'.strip()
    return nombre or u.email


def fila_movimiento(m):
    return {
        'id': m.id, 'fecha': m.fecha.isoformat(), 'tipo': m.tipo, 'tipo_nombre': m.get_tipo_display(),
        'motivo': m.motivo, 'motivo_nombre': m.get_motivo_display() if m.motivo else '',
        'referencia': m.referencia, 'documento': _documento(m), 'bodega': m.bodega.nombre,
        'entrada': num(m.cantidad) if m.cantidad > 0 else None,
        'salida': num(-m.cantidad) if m.cantidad < 0 else None,
        'costo_unitario': num(m.costo_unitario), 'usuario': _usuario(m.creado_por),
    }


def kardex(org, producto, bodega_id=None, desde=None, hasta=None):
    """Los movimientos de un producto en orden, con el saldo corrido y su valor al costo promedio
    ponderado móvil: cada entrada con costo recalcula el promedio; las salidas salen a ese promedio."""
    producto = Producto.objects.filter(organization=org, pk=producto.pk if isinstance(producto, Producto) else producto).first()
    if producto is None:
        raise ErrorComercial('El producto no existe.')
    desde, hasta = _fecha(desde), _fecha(hasta)
    qs = (MovimientoStock.objects.filter(organization=org, producto=producto)
          .select_related('bodega', 'entrega__pedido', 'conteo', 'creado_por').order_by('fecha', 'id'))
    if bodega_id:
        qs = qs.filter(bodega_id=bodega_id)
    saldo, promedio = CERO, CERO
    if desde:
        anteriores = qs.filter(fecha__lt=desde)
        saldo = anteriores.aggregate(t=Sum('cantidad'))['t'] or CERO
        promedio = costo_promedio(org, producto, hasta=desde - timedelta(days=1))
        qs = qs.filter(fecha__gte=desde)
    if hasta:
        qs = qs.filter(fecha__lte=hasta)
    inicial = {'cantidad': num(saldo), 'valor': pesos(max(saldo, CERO) * promedio)}
    filas, serie = [], []
    if desde:
        serie.append({'fecha': desde.isoformat(), 'saldo': num(saldo)})
    for m in qs:
        if m.cantidad > 0 and m.tipo in ENTRADAS_CON_COSTO and m.costo_unitario is not None:
            base = max(saldo, CERO)
            promedio = ((base * promedio + m.cantidad * m.costo_unitario) / (base + m.cantidad)
                        if base + m.cantidad > 0 else m.costo_unitario)
        elif promedio == 0 and m.costo_unitario:
            promedio = m.costo_unitario
        saldo += m.cantidad
        fila = fila_movimiento(m)
        fila.update({'saldo': num(saldo), 'valor_saldo': pesos(max(saldo, CERO) * promedio)})
        filas.append(fila)
        if serie and serie[-1]['fecha'] == fila['fecha']:
            serie[-1]['saldo'] = num(saldo)
        else:
            serie.append({'fecha': fila['fecha'], 'saldo': num(saldo)})
    return {
        'producto': {'id': producto.id, 'codigo': producto.codigo, 'nombre': producto.nombre, 'unidad': producto.unidad,
                     'familia': producto.familia, 'costo_promedio': num(costo_promedio(org, producto))},
        'saldo_inicial': inicial, 'movimientos': filas,
        'saldo_final': {'cantidad': num(saldo), 'valor': pesos(max(saldo, CERO) * promedio)},
        'serie': serie,
    }


def movimientos(org, tipo=None, motivo=None, producto=None, bodega=None, desde=None, hasta=None, q=None):
    qs = (MovimientoStock.objects.filter(organization=org)
          .select_related('producto', 'bodega', 'entrega__pedido', 'conteo', 'creado_por'))
    for campo, valor in (('tipo', tipo), ('motivo', motivo), ('producto_id', producto), ('bodega_id', bodega)):
        if valor:
            qs = qs.filter(**{campo: valor})
    if desde:
        qs = qs.filter(fecha__gte=_fecha(desde))
    if hasta:
        qs = qs.filter(fecha__lte=_fecha(hasta))
    if q:
        qs = qs.filter(Q(producto__nombre__icontains=q) | Q(producto__codigo__icontains=q) | Q(referencia__icontains=q))
    salida = []
    for m in qs.order_by('-fecha', '-id')[:MAX_MOVIMIENTOS]:
        fila = fila_movimiento(m)
        fila.update({'producto_id': m.producto_id, 'producto': m.producto.nombre, 'cantidad': num(m.cantidad)})
        salida.append(fila)
    return salida


# ── Valorización y rotación ───────────────────────────────────────────────────

def valorizacion(org, fecha=None):
    """El inventario a una fecha: la cantidad que había ese día y su costo promedio con las entradas
    hasta ese día."""
    fecha = _fecha(fecha, timezone.localdate())
    cantidades = dict(MovimientoStock.objects.filter(organization=org, fecha__lte=fecha).values('producto')
                      .annotate(t=Sum('cantidad')).values_list('producto', 't'))
    productos, familias = [], defaultdict(int)
    for p in Producto.objects.filter(organization=org, tipo=Producto.ALMACENABLE, pk__in=cantidades.keys()):
        cant = cantidades.get(p.id) or CERO
        if cant == 0:
            continue
        costo = costo_promedio(org, p, hasta=fecha)
        valor = pesos(max(cant, CERO) * costo)
        productos.append({'id': p.id, 'codigo': p.codigo, 'nombre': p.nombre, 'familia': p.familia,
                          'cantidad': num(cant), 'costo_promedio': num(costo), 'valor': valor})
        familias[p.familia or 'Sin familia'] += valor
    productos.sort(key=lambda x: -x['valor'])
    return {'fecha': fecha.isoformat(), 'total': sum(x['valor'] for x in productos), 'productos': productos,
            'por_familia': sorted(({'familia': k, 'valor': v} for k, v in familias.items()), key=lambda x: -x['valor'])}


def rotacion(org, dias=90):
    """Cuánto se vende de cada producto y para cuántos días alcanza el stock. Inmovilizados: los que
    tienen stock y no se vendieron en el período."""
    dias = max(1, min(int(dias or 90), 730))
    if nivel(org) == SIN_INVENTARIO:
        return {'dias': dias, 'productos': [], 'inmovilizados': []}
    hoy = timezone.localdate()
    desde = hoy - timedelta(days=dias)
    existencias = defaultdict(lambda: CERO)
    for (pid, _b), c in stock(org).items():
        existencias[pid] += c
    salidas = dict(MovimientoStock.objects.filter(organization=org, tipo=MovimientoStock.VENTA, cantidad__lt=0,
                                                  fecha__gte=desde).values('producto')
                   .annotate(t=Sum('cantidad')).values_list('producto', 't'))
    ultimos = dict(MovimientoStock.objects.filter(organization=org).values('producto')
                   .annotate(u=Max('fecha')).values_list('producto', 'u'))
    primeros = dict(MovimientoStock.objects.filter(organization=org, cantidad__gt=0).values('producto')
                    .annotate(p=Min('fecha')).values_list('producto', 'p'))
    productos, inmovilizados = [], []
    for p in Producto.objects.filter(organization=org, tipo=Producto.ALMACENABLE, activo=True):
        actual = existencias[p.id]
        vendido = -(salidas.get(p.id) or CERO)
        diarias = vendido / dias
        ultimo = ultimos.get(p.id)
        fila = {
            'id': p.id, 'codigo': p.codigo, 'nombre': p.nombre, 'stock': num(actual), 'salidas': num(vendido),
            'salidas_diarias': num(diarias.quantize(Decimal('0.001'))),
            'dias_inventario': int(actual / diarias) if diarias > 0 and actual > 0 else None,
            'ultimo_movimiento': ultimo.isoformat() if ultimo else None,
            'dias_sin_movimiento': (hoy - ultimo).days if ultimo else None,
            'valor': pesos(max(actual, CERO) * costo_promedio(org, p)),
        }
        productos.append(fila)
        # Inmovilizado: con stock desde antes de que empezara el período y sin ventas en él. Lo recién
        # llegado no está inmovilizado, aunque todavía no se venda.
        if actual > 0 and vendido == 0 and primeros.get(p.id) and primeros[p.id] < desde:
            inmovilizados.append(fila)
    productos.sort(key=lambda x: (x['dias_inventario'] is None, x['dias_inventario'] or 0))
    inmovilizados.sort(key=lambda x: -x['valor'])
    return {'dias': dias, 'productos': productos, 'inmovilizados': inmovilizados}


# ── Tomas de inventario ───────────────────────────────────────────────────────

def detalle_conteo(c, con_lineas=True):
    lineas = list(c.lineas.select_related('producto', 'bodega'))
    contadas = [l for l in lineas if l.contada is not None]
    con_diferencia = [l for l in contadas if l.contada != l.sistema]
    datos = {
        'id': c.id, 'numero': c.numero, 'estado': c.estado, 'estado_nombre': c.get_estado_display(),
        'bodega': c.bodega.nombre if c.bodega_id else 'Todas', 'familia': c.familia, 'fecha': c.fecha.isoformat(),
        'lineas': len(lineas), 'contadas': len(contadas), 'con_diferencia': len(con_diferencia),
        'valor_diferencia': sum(pesos((l.contada - l.sistema) * l.costo_unitario) for l in con_diferencia),
    }
    if con_lineas:  # en el detalle, `lineas` es la lista (en la lista de tomas, cuántas son)
        datos['lineas'] = [{
            'id': l.id, 'producto_id': l.producto_id, 'codigo': l.producto.codigo, 'nombre': l.producto.nombre,
            'unidad': l.producto.unidad, 'ubicacion': l.producto.ubicacion, 'codigo_barras': l.producto.codigo_barras,
            'bodega': l.bodega.nombre, 'sistema': num(l.sistema), 'contada': num(l.contada),
            'diferencia': num(l.contada - l.sistema) if l.contada is not None else None,
            'valor_diferencia': pesos((l.contada - l.sistema) * l.costo_unitario) if l.contada is not None else None,
        } for l in lineas]
    return datos


def conteos(org):
    return [detalle_conteo(c, con_lineas=False) for c in ConteoInventario.objects.filter(organization=org)
            .select_related('bodega')]


@transaction.atomic
def crear_conteo(org, bodega_id=None, familia='', solo_con_stock=False, productos=None, usuario=None, notas=''):
    """Fotografía lo que dice el sistema de cada producto (y bodega) para contarlo."""
    exigir_activo(org)
    bodega = _bodega(org, bodega_id) if bodega_id else None
    qs = Producto.objects.filter(organization=org, tipo=Producto.ALMACENABLE, activo=True)
    if familia:
        qs = qs.filter(familia=familia)
    if productos:
        qs = qs.filter(pk__in=[int(x) for x in productos])
    existencias = stock(org)
    principal = Bodega.principal_de(org)
    if bodega:
        bodegas = [bodega]
    elif nivel(org) == 'completo':
        bodegas = list(Bodega.objects.filter(organization=org, activa=True))
    else:
        bodegas = [principal]
    c = ConteoInventario.objects.create(organization=org, numero=Secuencia.tomar(org, 'CI'), bodega=bodega,
                                        familia=familia or '', fecha=timezone.localdate(), notas=str(notas or '')[:2000],
                                        creado_por=usuario)
    lineas = []
    for p in qs:
        costo = costo_promedio(org, p)
        # Una bodega: el producto se cuenta ahí (o solo si tiene stock, con "solo con stock"). Todas
        # (inventario completo): cada bodega donde hay algo; si no hay en ninguna, la principal, para
        # poder registrar lo que aparezca.
        con_stock = [b for b in bodegas if existencias.get((p.id, b.id), CERO) != 0]
        if len(bodegas) == 1:
            elegidas = con_stock if solo_con_stock else bodegas
        else:
            elegidas = con_stock or ([] if solo_con_stock else [principal])
        for b in elegidas:
            lineas.append(LineaConteo(conteo=c, producto=p, bodega=b, sistema=existencias.get((p.id, b.id), CERO),
                                      costo_unitario=costo))
    if not lineas:
        raise ErrorComercial('No hay productos para contar con esos filtros.')
    LineaConteo.objects.bulk_create(lineas)
    return c


def _conteo_editable(c):
    if c.estado != ConteoInventario.CONTANDO:
        raise ErrorComercial(f'La toma {c.numero} está {c.get_estado_display().lower()}: ya no se edita.')


def registrar_contadas(c, lineas):
    _conteo_editable(c)
    por_id = {l.id: l for l in c.lineas.all()}
    for d in lineas or []:
        linea = por_id.get(int(d.get('id') or 0))
        if linea is None:
            raise ErrorComercial('Una de las líneas no es de esta toma de inventario.')
        valor = d.get('contada')
        linea.contada = None if valor in (None, '') else decimal(valor, 'La cantidad contada', 0)
        linea.save(update_fields=['contada'])
    return c


@transaction.atomic
def aplicar_conteo(c, usuario=None):
    """Deja el stock en lo contado. La diferencia se calcula contra el stock ACTUAL al aplicar, no
    contra la foto del sistema: si entre la toma y la aplicación hubo entregas o recepciones, lo
    contado manda. Las líneas sin contar no se tocan."""
    _conteo_editable(c)
    org = c.organization
    hoy = timezone.localdate()
    for l in c.lineas.select_related('producto', 'bodega'):
        if l.contada is None:
            continue
        actual = stock(org, producto=l.producto, bodega=l.bodega).get((l.producto_id, l.bodega_id), CERO)
        diferencia = l.contada - actual
        if diferencia:
            MovimientoStock.objects.create(
                organization=org, producto=l.producto, bodega=l.bodega, cantidad=diferencia,
                tipo=MovimientoStock.CONTEO, fecha=hoy, costo_unitario=costo_promedio(org, l.producto),
                referencia=f'Toma de inventario {c.numero}', conteo=c, creado_por=usuario)
    c.estado, c.aplicado_en, c.aplicado_por = ConteoInventario.APLICADO, timezone.now(), usuario
    c.save(update_fields=['estado', 'aplicado_en', 'aplicado_por'])
    return c


def cancelar_conteo(c):
    _conteo_editable(c)
    c.estado = ConteoInventario.CANCELADO
    c.save(update_fields=['estado'])
    return c


COLUMNAS_CONTEO = ['ID', 'Código', 'Producto', 'Ubicación', 'Bodega', 'Sistema', 'Contada']


def planilla_conteo(c):
    filas = [[l.id, l.producto.codigo, l.producto.nombre, l.producto.ubicacion, l.bodega.nombre, l.sistema,
              l.contada] for l in c.lineas.select_related('producto', 'bodega')]
    return planillas.libro(c.numero, COLUMNAS_CONTEO, filas)


def importar_planilla_conteo(c, archivo):
    """Las cantidades contadas desde la planilla (por ID de línea; si falta, por código y bodega)."""
    _conteo_editable(c)
    lineas = list(c.lineas.select_related('producto', 'bodega'))
    por_id = {l.id: l for l in lineas}
    por_codigo = {(l.producto.codigo, l.bodega.nombre): l for l in lineas if l.producto.codigo}
    errores = []
    for n, f in planillas.leer_filas(archivo):
        try:
            linea = None
            if f.get('id') not in (None, ''):
                linea = por_id.get(int(float(f['id'])))
            if linea is None:
                linea = por_codigo.get((planillas._texto(f.get('codigo'), 40), planillas._texto(f.get('bodega'), 80)))
            if linea is None:
                raise ErrorComercial('la línea no es de esta toma')
            valor = f.get('contada')
            linea.contada = None if valor in (None, '') else decimal(valor, 'La cantidad contada', 0)
            linea.save(update_fields=['contada'])
        except (ErrorComercial, ValueError) as e:
            errores.append({'fila': n, 'error': str(e)})
    return errores


# ── Carga inicial y planillas ─────────────────────────────────────────────────

COLUMNAS_INICIAL = ['Código', 'Nombre', 'Cantidad', 'Costo unitario', 'Bodega']


def plantilla_inicial():
    return planillas.libro('Stock inicial', COLUMNAS_INICIAL, [
        ['SILLA-01', 'Silla ergonómica', 12, 52000, ''], ['', 'Mesa de reuniones', 3, 145000, 'Bodega principal']])


@transaction.atomic
def importar_inicial(org, archivo, usuario=None):
    """Stock inicial desde Excel o CSV: cada fila es una entrada «Stock inicial» con su costo. Las
    filas con problemas no frenan las demás."""
    exigir_activo(org)
    bodegas = {planillas._clave(b.nombre): b for b in Bodega.objects.filter(organization=org, activa=True)}
    creados, errores = 0, []
    for n, f in planillas.leer_filas(archivo):
        try:
            codigo = planillas._texto(f.get('codigo'), 40)
            nombre = planillas._texto(f.get('nombre'), 200)
            p = (Producto.objects.filter(organization=org, codigo=codigo).first() if codigo else None) \
                or (Producto.objects.filter(organization=org, nombre__iexact=nombre).first() if nombre else None)
            if p is None:
                raise ErrorComercial(f'no existe el producto «{codigo or nombre}» (créelo primero en Productos)')
            if not p.lleva_stock:
                raise ErrorComercial(f'{p.nombre} no es almacenable')
            bodega_txt = planillas._texto(f.get('bodega'), 80)
            bodega = bodegas.get(planillas._clave(bodega_txt)) if bodega_txt else Bodega.principal_de(org)
            if bodega is None:
                raise ErrorComercial(f'no existe la bodega «{bodega_txt}»')
            cantidad = decimal(f.get('cantidad'), 'La cantidad', Decimal('0.001'))
            costo = f.get('costo unitario', f.get('costo'))
            costo = decimal(costo, 'El costo', 0) if costo not in (None, '') else p.costo
            MovimientoStock.objects.create(
                organization=org, producto=p, bodega=bodega, cantidad=cantidad, tipo=MovimientoStock.INICIAL,
                motivo='inicial', fecha=timezone.localdate(), costo_unitario=costo, referencia='Carga de stock inicial',
                creado_por=usuario)
            creados += 1
        except ErrorComercial as e:
            errores.append({'fila': n, 'error': str(e)})
    return {'creados': creados, 'errores': errores}


def exportar_stock(org, bodega_id=None):
    filas = [[f['codigo'], f['nombre'], f['familia'], f['ubicacion'], f['unidad'], Decimal(f['fisico']),
              Decimal(f['reservado']), Decimal(f['disponible']), Decimal(f['por_recibir']), Decimal(f['proyectado']),
              Decimal(f['stock_minimo']), Decimal(f['costo_promedio']), f['valor'], f['estado']]
             for f in filas_stock(org, bodega_id)]
    cols = ['Código', 'Producto', 'Familia', 'Ubicación', 'Unidad', 'Físico', 'Reservado', 'Disponible', 'Por recibir',
            'Proyectado', 'Stock mínimo', 'Costo promedio', 'Valor', 'Estado']
    return planillas.libro('Stock', cols, filas)


def exportar_kardex(org, producto_id, bodega_id=None, desde=None, hasta=None):
    k = kardex(org, producto_id, bodega_id, desde, hasta)
    filas = [[m['fecha'], m['tipo_nombre'], m['motivo_nombre'], (m['documento'] or {}).get('numero', ''), m['referencia'],
              m['bodega'], Decimal(m['entrada']) if m['entrada'] else None, Decimal(m['salida']) if m['salida'] else None,
              Decimal(m['saldo']), Decimal(m['costo_unitario']) if m['costo_unitario'] else None, m['valor_saldo']]
             for m in k['movimientos']]
    cols = ['Fecha', 'Tipo', 'Motivo', 'Documento', 'Referencia', 'Bodega', 'Entrada', 'Salida', 'Saldo',
            'Costo unitario', 'Valor del saldo']
    return k['producto']['nombre'], planillas.libro('Kardex', cols, filas)


def exportar_valorizacion(org, fecha=None):
    v = valorizacion(org, fecha)
    filas = [[x['codigo'], x['nombre'], x['familia'], Decimal(x['cantidad']), Decimal(x['costo_promedio']), x['valor']]
             for x in v['productos']]
    return v['fecha'], planillas.libro('Valorización', ['Código', 'Producto', 'Familia', 'Cantidad', 'Costo promedio',
                                                        'Valor'], filas)

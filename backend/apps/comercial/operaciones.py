"""Lo que se le hace a un pedido y al stock. La pantalla y el chat pasan por aquí: así una
regla (no entregar más de lo pedido, no cancelar lo ya entregado) vale igual para los dos."""

from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from apps.finanzas.models import Contacto, Proyecto

from .models import (CERO, CLP, COMPRA, DECIMALES, MONEDAS, VENTA, Bodega, ConfiguracionComercial,
                     Entrega, LineaEntrega, LineaPedido, MovimientoStock, PagoPedido, Pedido, PedidoFactura,
                     PrecioContacto, Producto, Secuencia)


class ErrorComercial(Exception):
    """Algo que la persona puede corregir: el mensaje se le muestra tal cual."""


def decimal(valor, nombre, minimo=None):
    try:
        d = Decimal(str(valor).replace(',', '.').strip())
    except (InvalidOperation, ValueError):
        raise ErrorComercial(f'{nombre}: tiene que ser un número.')
    if not d.is_finite():
        raise ErrorComercial(f'{nombre}: tiene que ser un número.')
    if minimo is not None and d < minimo:
        raise ErrorComercial(f'{nombre}: no puede ser menor que {minimo}.')
    return d


# ── Pedidos ───────────────────────────────────────────────────────────────────

def crear_pedido(org, tipo, contacto, usuario=None, **datos):
    if tipo not in (VENTA, COMPRA):
        raise ErrorComercial('Tipo de pedido no válido.')
    if contacto.organization_id != org.id:
        raise ErrorComercial('El contacto no es de esta empresa.')
    # Quien recibe una cotización pasa a ser cliente (o proveedor, en compras).
    marca = 'es_cliente' if tipo == VENTA else 'es_proveedor'
    if not getattr(contacto, marca):
        setattr(contacto, marca, True)
        contacto.save(update_fields=[marca])
    cfg = ConfiguracionComercial.de(org)
    hoy = timezone.localdate()
    pedido = Pedido(organization=org, tipo=tipo, contacto=contacto, creado_por=usuario,
                    numero=Secuencia.tomar(org, Pedido.PREFIJO[tipo]), fecha=hoy,
                    valida_hasta=hoy + timedelta(days=cfg.validez_cotizacion_dias) if tipo == VENTA else None,
                    condiciones=cfg.condiciones_venta if tipo == VENTA else '')
    if cfg.con_inventario:
        pedido.bodega = Bodega.principal_de(org)
    plazo = contacto.roles.filter(libro='ventas' if tipo == VENTA else 'compras').first()
    if plazo and plazo.plazo_dias is not None:
        pedido.plazo_dias = plazo.plazo_dias
    aplicar_datos(pedido, datos)
    pedido.save()
    return pedido


def aplicar_datos(pedido, datos):
    """Los campos de cabecera que se pueden cambiar mientras el pedido es editable."""
    from datetime import date
    for campo in ('fecha', 'fecha_compromiso', 'valida_hasta'):
        if campo in datos:
            v = datos[campo]
            try:
                setattr(pedido, campo, date.fromisoformat(v) if v else None)
            except (TypeError, ValueError):
                raise ErrorComercial('Fecha no válida (use AAAA-MM-DD).')
    if pedido.fecha is None:
        raise ErrorComercial('Falta la fecha.')
    for campo, largo in (('referencia', 60), ('notas', 5000), ('condiciones', 5000)):
        if campo in datos:
            setattr(pedido, campo, str(datos[campo] or '')[:largo])
    if 'plazo_dias' in datos:
        v = datos['plazo_dias']
        pedido.plazo_dias = None if v in (None, '') else int(decimal(v, 'El plazo', 0))
    if 'moneda' in datos:
        if datos['moneda'] not in dict(MONEDAS):
            raise ErrorComercial('Moneda no válida.')
        pedido.moneda = datos['moneda']
        if pedido.moneda == CLP:
            pedido.tipo_cambio = Decimal('1')
    if 'tipo_cambio' in datos and pedido.moneda != CLP:
        pedido.tipo_cambio = decimal(datos['tipo_cambio'], 'El tipo de cambio', Decimal('0.0001'))
    if 'proyecto' in datos:
        pid = datos['proyecto']
        pedido.proyecto = (Proyecto.objects.filter(organization=pedido.organization, pk=pid).first()
                           if pid else None)
        if pid and pedido.proyecto is None:
            raise ErrorComercial('El proyecto no existe.')
    if 'bodega' in datos:
        bid = datos['bodega']
        pedido.bodega = (Bodega.objects.filter(organization=pedido.organization, pk=bid, activa=True).first()
                         if bid else None)
        if bid and pedido.bodega is None:
            raise ErrorComercial('La bodega no existe.')
    if 'contacto' in datos and datos['contacto'] != pedido.contacto_id:
        c = Contacto.objects.filter(organization=pedido.organization, pk=datos['contacto']).first()
        if c is None:
            raise ErrorComercial('El contacto no existe.')
        pedido.contacto = c


def editable(pedido):
    return pedido.estado in (Pedido.BORRADOR, Pedido.ENVIADO)


@transaction.atomic
def guardar_lineas(pedido, lineas):
    """Reemplaza las líneas. Solo mientras es cotización: una orden confirmada ya comprometió
    cantidades (entregas, facturas), y cambiarla por debajo descuadra todo."""
    if not editable(pedido):
        raise ErrorComercial('Solo se pueden cambiar las líneas de una cotización. Vuelva la orden a borrador primero.')
    productos = {p.id: p for p in Producto.objects.filter(
        organization=pedido.organization, id__in=[l.get('producto') for l in lineas if l.get('producto')])}
    nuevas = []
    for i, l in enumerate(lineas):
        producto = productos.get(l.get('producto')) if l.get('producto') else None
        if l.get('producto') and producto is None:
            raise ErrorComercial('Uno de los productos no existe.')
        descripcion = str(l.get('descripcion') or (producto.nombre if producto else '')).strip()[:500]
        if not descripcion:
            raise ErrorComercial(f'La línea {i + 1} no tiene descripción.')
        precio_defecto = precio_para(producto, pedido.contacto, pedido.tipo) if producto else CERO
        cantidad = decimal(l.get('cantidad', 1), f'Cantidad de la línea {i + 1}', Decimal('0'))
        nuevas.append(LineaPedido(
            pedido=pedido, orden=i, producto=producto, descripcion=descripcion,
            cantidad=cantidad,
            unidad=str(l.get('unidad') or (producto.unidad if producto else 'un'))[:20],
            precio_unitario=decimal(l['precio_unitario'], f'Precio de la línea {i + 1}', Decimal('0'))
            if l.get('precio_unitario') not in (None, '') else precio_defecto,
            descuento_pct=decimal(l.get('descuento_pct') or 0, f'Descuento de la línea {i + 1}', Decimal('0')),
            exento=bool(l.get('exento', producto.exento if producto else False)),
        ))
        if nuevas[-1].descuento_pct > 100:
            raise ErrorComercial(f'El descuento de la línea {i + 1} no puede pasar de 100%.')
    pedido.lineas.all().delete()
    LineaPedido.objects.bulk_create(nuevas)
    pedido.recalcular()
    return pedido


def precio_para(producto, contacto, tipo):
    """El precio de un producto para ese cliente o de ese proveedor; si no tiene uno propio, el
    precio de venta (o el costo, en compras) del producto."""
    propio = PrecioContacto.objects.filter(producto=producto, contacto=contacto, tipo=tipo).first()
    if propio is not None:
        return propio.precio
    return producto.precio_venta if tipo == VENTA else producto.costo


@transaction.atomic
def duplicar(pedido, usuario=None):
    """Una cotización nueva igual a esta (mismo contacto, condiciones y líneas), con fecha de hoy."""
    copia = crear_pedido(pedido.organization, pedido.tipo, pedido.contacto, usuario,
                         moneda=pedido.moneda, plazo_dias=pedido.plazo_dias, notas=pedido.notas,
                         condiciones=pedido.condiciones)
    copia.tipo_cambio = pedido.tipo_cambio
    copia.proyecto = pedido.proyecto
    if pedido.bodega_id:
        copia.bodega = pedido.bodega
    copia.save()
    LineaPedido.objects.bulk_create([LineaPedido(
        pedido=copia, orden=l.orden, producto=l.producto, descripcion=l.descripcion, cantidad=l.cantidad,
        unidad=l.unidad, precio_unitario=l.precio_unitario, descuento_pct=l.descuento_pct, exento=l.exento,
    ) for l in pedido.lineas.all()])
    copia.recalcular()
    return copia


def marcar_enviado(pedido):
    if pedido.estado != Pedido.BORRADOR:
        return pedido
    pedido.estado = Pedido.ENVIADO
    pedido.enviado_en = timezone.now()
    pedido.save(update_fields=['estado', 'enviado_en', 'actualizado_en'])
    return pedido


def confirmar(pedido):
    if pedido.estado == Pedido.CONFIRMADO:
        return pedido
    if pedido.estado == Pedido.CANCELADO:
        raise ErrorComercial('Está cancelado: vuélvalo a borrador primero.')
    if not pedido.lineas.exists():
        raise ErrorComercial('No tiene líneas.')
    if pedido.moneda != CLP and pedido.tipo_cambio <= 0:
        raise ErrorComercial('Falta el tipo de cambio.')
    pedido.estado = Pedido.CONFIRMADO
    pedido.confirmado_en = timezone.now()
    pedido.save(update_fields=['estado', 'confirmado_en', 'actualizado_en'])
    return pedido


def cancelar(pedido):
    if pedido.entregas.filter(estado=Entrega.HECHA).exists():
        raise ErrorComercial('Tiene entregas hechas: anúlelas antes de cancelar.')
    if pedido.facturas.exists():
        raise ErrorComercial('Tiene facturas vinculadas: desvincúlelas antes de cancelar.')
    pedido.estado = Pedido.CANCELADO
    pedido.save(update_fields=['estado', 'actualizado_en'])
    return pedido


def volver_a_borrador(pedido):
    if pedido.entregas.filter(estado=Entrega.HECHA).exists() or pedido.facturas.exists():
        raise ErrorComercial('Ya tiene entregas o facturas: no puede volver a ser cotización.')
    pedido.estado = Pedido.BORRADOR
    pedido.save(update_fields=['estado', 'actualizado_en'])
    return pedido


# ── Entregas y recepciones ────────────────────────────────────────────────────

@transaction.atomic
def registrar_entrega(pedido, cantidades, usuario=None, fecha=None, bodega=None, folio_guia='', notas=''):
    """`cantidades`: {id de línea: cantidad}. Sin cantidades, entrega todo lo pendiente."""
    if pedido.estado != Pedido.CONFIRMADO:
        raise ErrorComercial('Solo se entrega o recibe una orden confirmada.')
    org = pedido.organization
    cfg = ConfiguracionComercial.de(org)
    lineas = {l.id: l for l in pedido.lineas.select_related('producto').select_for_update(of=('self',))}
    if not cantidades:
        cantidades = {lid: l.pendiente_entrega for lid, l in lineas.items() if l.pendiente_entrega > 0}
    pares = []
    for lid, cant in cantidades.items():
        linea = lineas.get(int(lid))
        if linea is None:
            raise ErrorComercial('Una de las líneas no es de este pedido.')
        cant = decimal(cant, f'Cantidad de «{linea.descripcion[:40]}»', Decimal('0'))
        if cant == 0:
            continue
        if cant > linea.pendiente_entrega:
            raise ErrorComercial(f'«{linea.descripcion[:40]}»: quedan {linea.pendiente_entrega.normalize()} por '
                                 f'{"entregar" if pedido.tipo == VENTA else "recibir"}, no {cant.normalize()}.')
        pares.append((linea, cant))
    if not pares:
        raise ErrorComercial('No hay nada que entregar.' if pedido.tipo == VENTA else 'No hay nada que recibir.')

    # `bodega` llega como id (de la pantalla o del chat); sin elegir, la del pedido.
    if cfg.con_inventario:
        bodega = (Bodega.objects.filter(organization=org, pk=bodega, activa=True).first() if bodega else None) \
            or pedido.bodega or Bodega.principal_de(org)
    from datetime import date
    entrega = Entrega.objects.create(
        organization=org, pedido=pedido, numero=Secuencia.tomar(org, Entrega.PREFIJO[pedido.tipo]),
        fecha=date.fromisoformat(fecha) if isinstance(fecha, str) and fecha else (fecha or timezone.localdate()),
        bodega=bodega if cfg.con_inventario else None, folio_guia=str(folio_guia or '')[:20],
        notas=str(notas or '')[:2000], creado_por=usuario)
    signo = -1 if pedido.tipo == VENTA else 1
    for linea, cant in pares:
        LineaEntrega.objects.create(entrega=entrega, linea=linea, cantidad=cant)
        linea.cantidad_entregada += cant
        linea.save(update_fields=['cantidad_entregada'])
        if cfg.con_inventario and linea.mueve_stock:
            MovimientoStock.objects.create(
                organization=org, producto=linea.producto, bodega=entrega.bodega, cantidad=signo * cant,
                tipo=MovimientoStock.VENTA if pedido.tipo == VENTA else MovimientoStock.COMPRA,
                fecha=entrega.fecha, entrega=entrega, referencia=f'{entrega.numero} · {pedido.numero}',
                costo_unitario=costo_de_linea(linea) if pedido.tipo == COMPRA else costo_promedio(org, linea.producto),
                creado_por=usuario)
    return entrega


@transaction.atomic
def registrar_devolucion(pedido, cantidades, usuario=None, fecha=None, bodega=None, notas=''):
    """Lo que el cliente devuelve (venta) o lo que se le devuelve al proveedor (compra).
    `cantidades`: {id de línea: cantidad}; no puede pasar de lo ya entregado o recibido."""
    if pedido.estado != Pedido.CONFIRMADO:
        raise ErrorComercial('Solo se registra una devolución de una orden confirmada.')
    org = pedido.organization
    cfg = ConfiguracionComercial.de(org)
    lineas = {l.id: l for l in pedido.lineas.select_related('producto').select_for_update(of=('self',))}
    pares = []
    for lid, cant in (cantidades or {}).items():
        linea = lineas.get(int(lid))
        if linea is None:
            raise ErrorComercial('Una de las líneas no es de este pedido.')
        cant = decimal(cant, f'Cantidad de «{linea.descripcion[:40]}»', Decimal('0'))
        if cant == 0:
            continue
        if cant > linea.cantidad_entregada:
            raise ErrorComercial(f'«{linea.descripcion[:40]}»: se {"entregaron" if pedido.tipo == VENTA else "recibieron"} '
                                 f'{linea.cantidad_entregada.normalize()}, no se pueden devolver {cant.normalize()}.')
        pares.append((linea, cant))
    if not pares:
        raise ErrorComercial('Indique cuánto se devuelve.')
    if cfg.con_inventario:
        bodega = (Bodega.objects.filter(organization=org, pk=bodega, activa=True).first() if bodega else None) \
            or pedido.bodega or Bodega.principal_de(org)
    from datetime import date
    devolucion = Entrega.objects.create(
        organization=org, pedido=pedido, tipo=Entrega.DEVOLUCION,
        numero=Secuencia.tomar(org, Entrega.PREFIJO_DEVOLUCION[pedido.tipo]),
        fecha=date.fromisoformat(fecha) if isinstance(fecha, str) and fecha else (fecha or timezone.localdate()),
        bodega=bodega if cfg.con_inventario else None, notas=str(notas or '')[:2000], creado_por=usuario)
    # Al revés que la entrega: lo que devuelve el cliente vuelve a la bodega; lo que se devuelve
    # al proveedor sale.
    signo = 1 if pedido.tipo == VENTA else -1
    for linea, cant in pares:
        LineaEntrega.objects.create(entrega=devolucion, linea=linea, cantidad=cant)
        linea.cantidad_entregada -= cant
        linea.save(update_fields=['cantidad_entregada'])
        if cfg.con_inventario and linea.mueve_stock:
            MovimientoStock.objects.create(
                organization=org, producto=linea.producto, bodega=devolucion.bodega, cantidad=signo * cant,
                tipo=MovimientoStock.DEVOLUCION, fecha=devolucion.fecha, entrega=devolucion,
                referencia=f'{devolucion.numero} · {pedido.numero}',
                costo_unitario=costo_de_linea(linea) if pedido.tipo == COMPRA else costo_promedio(org, linea.producto),
                creado_por=usuario)
    return devolucion


@transaction.atomic
def anular_entrega(entrega, usuario=None):
    if entrega.estado == Entrega.ANULADA:
        return entrega
    devolucion = entrega.tipo == Entrega.DEVOLUCION
    for le in entrega.lineas.select_related('linea'):
        if devolucion:
            le.linea.cantidad_entregada += le.cantidad
        else:
            le.linea.cantidad_entregada = max(le.linea.cantidad_entregada - le.cantidad, CERO)
        le.linea.save(update_fields=['cantidad_entregada'])
    for m in entrega.movimientos.all():
        MovimientoStock.objects.create(
            organization=m.organization, producto=m.producto, bodega=m.bodega, cantidad=-m.cantidad,
            tipo=MovimientoStock.ANULACION, fecha=timezone.localdate(), entrega=entrega,
            referencia=f'Anula {entrega.numero}', costo_unitario=m.costo_unitario, creado_por=usuario)
    entrega.estado = Entrega.ANULADA
    entrega.save(update_fields=['estado'])
    return entrega


# ── Stock ─────────────────────────────────────────────────────────────────────

def _bodega(org, bodega_id):
    b = Bodega.objects.filter(organization=org, pk=bodega_id, activa=True).first() if bodega_id else None
    return b or Bodega.principal_de(org)


def ajustar_stock(org, producto, cantidad_contada, bodega_id=None, usuario=None, motivo=''):
    """Inventario físico: deja el stock de esa bodega en lo contado (el movimiento es la diferencia)."""
    from .models import stock
    if not producto.lleva_stock:
        raise ErrorComercial('Solo los productos almacenables llevan stock.')
    bodega = _bodega(org, bodega_id)
    contada = decimal(cantidad_contada, 'La cantidad', Decimal('0'))
    actual = stock(org, producto=producto, bodega=bodega).get((producto.id, bodega.id), CERO)
    diferencia = contada - actual
    if diferencia == 0:
        return None
    return MovimientoStock.objects.create(
        organization=org, producto=producto, bodega=bodega, cantidad=diferencia,
        tipo=MovimientoStock.AJUSTE, fecha=timezone.localdate(), costo_unitario=costo_promedio(org, producto),
        referencia=(str(motivo or '') or 'Ajuste de inventario')[:120], creado_por=usuario)


@transaction.atomic
def traspasar(org, producto, origen_id, destino_id, cantidad, usuario=None):
    from .models import stock
    if not producto.lleva_stock:
        raise ErrorComercial('Solo los productos almacenables llevan stock.')
    origen = Bodega.objects.filter(organization=org, pk=origen_id, activa=True).first()
    destino = Bodega.objects.filter(organization=org, pk=destino_id, activa=True).first()
    if not origen or not destino or origen == destino:
        raise ErrorComercial('Elija dos bodegas distintas.')
    cant = decimal(cantidad, 'La cantidad', Decimal('0.001'))
    disponible = stock(org, producto=producto, bodega=origen).get((producto.id, origen.id), CERO)
    if cant > disponible:
        raise ErrorComercial(f'En {origen.nombre} hay {disponible.normalize()}, no {cant.normalize()}.')
    ref = f'Traspaso {origen.nombre} → {destino.nombre}'[:120]
    hoy = timezone.localdate()
    MovimientoStock.objects.create(organization=org, producto=producto, bodega=origen, cantidad=-cant,
                                   tipo=MovimientoStock.TRASPASO, fecha=hoy, referencia=ref, creado_por=usuario)
    MovimientoStock.objects.create(organization=org, producto=producto, bodega=destino, cantidad=cant,
                                   tipo=MovimientoStock.TRASPASO, fecha=hoy, referencia=ref, creado_por=usuario)


# ── Costo del inventario ──────────────────────────────────────────────────────

def costo_de_linea(linea):
    """Lo que cuesta una unidad de una línea de compra, en pesos y sin IVA (con su descuento)."""
    if not linea.cantidad:
        return CERO
    return (linea.subtotal / linea.cantidad * linea.pedido.tipo_cambio).quantize(Decimal('0.0001'))


def costo_promedio(org, producto, hasta=None):
    """Costo promedio ponderado de lo que entró a bodega con costo (recepciones, stock inicial y
    entradas manuales). Sin entradas con costo, el costo de la ficha del producto. `hasta` (una
    fecha) lo calcula con las entradas hasta ese día, para valorizar a una fecha pasada."""
    from django.db.models import F, Sum
    entradas = MovimientoStock.objects.filter(
        organization=org, producto=producto, cantidad__gt=0, costo_unitario__isnull=False,
        tipo__in=[MovimientoStock.COMPRA, MovimientoStock.INICIAL, MovimientoStock.ENTRADA])
    if hasta is not None:
        entradas = entradas.filter(fecha__lte=hasta)
    r = entradas.aggregate(valor=Sum(F('cantidad') * F('costo_unitario')), cantidad=Sum('cantidad'))
    if r['cantidad']:
        return (r['valor'] / r['cantidad']).quantize(Decimal('0.0001'))
    return producto.costo


# ── Cobros y pagos ────────────────────────────────────────────────────────────

def pagado(pedido):
    from django.db.models import Sum
    return pedido.pagos.aggregate(t=Sum('monto'))['t'] or 0


@transaction.atomic
def registrar_pago(pedido, monto, usuario=None, fecha=None, medio=PagoPedido.TRANSFERENCIA, referencia='', notas=''):
    """Un cobro de una orden de venta o un pago de una orden de compra (en pesos, con IVA)."""
    from datetime import date
    if pedido.estado != Pedido.CONFIRMADO:
        raise ErrorComercial('Solo se registra el pago de una orden confirmada.')
    monto = int(decimal(monto, 'El monto', Decimal('1')))
    total = pedido.a_pesos(pedido.total)
    falta = total - pagado(pedido)
    if monto > falta:
        raise ErrorComercial(f'Quedan {formato(max(falta, 0))} por {"cobrar" if pedido.tipo == VENTA else "pagar"}, no {formato(monto)}.')
    if medio not in dict(PagoPedido.MEDIOS):
        raise ErrorComercial('Medio de pago no válido.')
    try:
        dia = date.fromisoformat(fecha) if isinstance(fecha, str) and fecha else (fecha or timezone.localdate())
    except ValueError:
        raise ErrorComercial('Fecha no válida (use AAAA-MM-DD).')
    pago = PagoPedido.objects.create(pedido=pedido, fecha=dia, monto=monto, medio=medio,
                                     referencia=str(referencia or '')[:80], notas=str(notas or '')[:2000],
                                     creado_por=usuario)
    sincronizar_pago_facturas(pedido)
    return pago


@transaction.atomic
def borrar_pago(pago):
    pedido = pago.pedido
    pago.delete()
    sincronizar_pago_facturas(pedido)


def sincronizar_pago_facturas(pedido):
    """Con la orden pagada entera, sus facturas del SII quedan pagadas en Finanzas (Por cobrar y
    Por pagar dejan de mostrarlas). Si un pago se borra y deja de estar cubierta, se desmarcan las
    que marcó este pedido; las que alguien marcó a mano no se tocan."""
    cubierto = pagado(pedido) >= pedido.a_pesos(pedido.total) > 0
    ultimo = pedido.pagos.order_by('-fecha').first()
    for v in PedidoFactura.objects.filter(pedido=pedido).select_related('documento'):
        doc = v.documento
        if cubierto and not doc.pagado:
            doc.pagado, doc.fecha_pago = True, ultimo.fecha if ultimo else timezone.localdate()
            doc.save(update_fields=['pagado', 'fecha_pago'])
            v.marcado_pagado = True
            v.save(update_fields=['marcado_pagado'])
        elif not cubierto and v.marcado_pagado:
            doc.pagado, doc.fecha_pago = False, None
            doc.save(update_fields=['pagado', 'fecha_pago'])
            v.marcado_pagado = False
            v.save(update_fields=['marcado_pagado'])


# ── Reponer stock ─────────────────────────────────────────────────────────────

def proveedor_de(producto):
    """El proveedor al que se le compra: el preferido o, si no hay, el más barato."""
    return (PrecioContacto.objects.filter(producto=producto, tipo=COMPRA).select_related('contacto')
            .order_by('-preferido', 'precio').first())


def productos_bajo_minimo(org):
    from .models import stock
    hay = {}
    for (pid, _), cant in stock(org).items():
        hay[pid] = hay.get(pid, CERO) + cant
    return [(p, hay.get(p.id, CERO)) for p in Producto.objects.filter(
        organization=org, activo=True, tipo=Producto.ALMACENABLE, stock_minimo__gt=0)
        if hay.get(p.id, CERO) < p.stock_minimo]


@transaction.atomic
def reponer_stock(org, usuario=None):
    """Arma las solicitudes de compra para lo que está bajo el mínimo, una por proveedor. Salta lo
    que ya está pedido (una solicitud u OC abierta con ese producto pendiente de llegar). Devuelve
    (solicitudes creadas, productos sin proveedor)."""
    pedidos_abiertos = set(LineaPedido.objects.filter(
        pedido__organization=org, pedido__tipo=COMPRA,
        pedido__estado__in=[Pedido.BORRADOR, Pedido.ENVIADO, Pedido.CONFIRMADO],
    ).exclude(producto=None).values_list('producto_id', 'cantidad', 'cantidad_entregada'))
    ya_pedidos = {pid for pid, cant, recibida in pedidos_abiertos if cant > recibida}
    por_proveedor, sin_proveedor = {}, []
    for producto, hay in productos_bajo_minimo(org):
        if producto.id in ya_pedidos:
            continue
        precio = proveedor_de(producto)
        if precio is None:
            sin_proveedor.append(producto)
            continue
        cantidad = producto.cantidad_reorden if producto.cantidad_reorden > 0 else producto.stock_minimo * 2 - hay
        por_proveedor.setdefault(precio.contacto, []).append({
            'producto': producto.id, 'cantidad': str(max(cantidad, Decimal('1'))), 'precio_unitario': str(precio.precio)})
    creadas = []
    for proveedor, lineas in por_proveedor.items():
        pedido = crear_pedido(org, COMPRA, proveedor, usuario,
                              notas='Armada por Afable para reponer lo que está bajo el stock mínimo.')
        pedido.origen = 'reposicion'
        pedido.save(update_fields=['origen'])
        guardar_lineas(pedido, lineas)
        creadas.append(pedido)
    return creadas, sin_proveedor


def formato(cantidad, moneda=CLP):
    """Un monto como texto: $1.234.567, US$ 1.234,50, UF 12,3456."""
    d = DECIMALES.get(moneda, 0)
    texto = f'{Decimal(cantidad):,.{d}f}'.replace(',', '_').replace('.', ',').replace('_', '.')
    return {CLP: f'${texto}', 'USD': f'US$ {texto}', 'UF': f'UF {texto}'}.get(moneda, texto)

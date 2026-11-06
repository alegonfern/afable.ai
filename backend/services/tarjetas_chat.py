"""Las tarjetas del chat (25-10-2026): lo que Afable hizo o consultó en el ERP, como dato.

Cuando el chat usa Ventas, Compras o Finanzas, la respuesta no puede quedar en una frase:
la persona tiene que VER el documento que se creó, lo que se va a confirmar o los números
que se consultaron, igual que en la animación de la landing. `de()` toma la herramienta,
sus argumentos y su resultado, y devuelve una tarjeta lista para dibujar (montos ya
formateados), o None si no hay nada que mostrar (un error lo cuenta el texto).

Tipos: documento (líneas y totales) · confirmar (lo que va a pasar, con Sí / No) · hecho ·
lista (filas con enlace) · barras · cifras. Cada una lleva `modulo` (ventas, compras,
contabilidad, finanzas) para el ícono y `enlace` para abrirla en su pantalla.
"""
from decimal import Decimal, InvalidOperation

MAX_FILAS = 6
MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
         'septiembre', 'octubre', 'noviembre', 'diciembre']


def _clp(n):
    try:
        v = round(Decimal(str(n)))
        return f'{"-" if v < 0 else ""}${abs(v):,}'.replace(',', '.')
    except (InvalidOperation, TypeError, ValueError):
        return str(n)


def _num(n):
    try:
        d = Decimal(str(n)).normalize()
    except (InvalidOperation, TypeError, ValueError):
        return str(n)
    return f'{d:f}'.rstrip('0').rstrip('.') if '.' in f'{d:f}' else f'{d:f}'


def _pct(n):
    return f'{str(n).replace(".", ",")}%'


# El agente de cada módulo (25-10-2026): cada tarjeta dice quién hizo el trabajo.
AGENTES = {'ventas': 'Agente de Ventas', 'compras': 'Agente de Compras', 'inventario': 'Agente de Inventario',
           'contabilidad': 'Agente de Contabilidad', 'finanzas': 'Agente de Finanzas'}
# Las consultas de finanzas que son de la plata (Agente de Finanzas); las demás son de Contabilidad.
DE_FINANZAS = {'caja', 'por_cobrar', 'por_pagar', 'ventas', 'conciliacion'}


def modulo_de(nombre, args):
    """El módulo (y por lo tanto el agente) que hace el trabajo de una herramienta."""
    args = args or {}
    if nombre == 'compras_ventas':
        if args.get('accion') in ('reponer_stock', 'inventario', 'stock'):
            return 'inventario'
        if args.get('accion') == 'registrar_factura_proveedor' or args.get('tipo') == 'compra' \
                or str(args.get('numero') or '').upper().startswith('OC'):
            return 'compras'
        return 'ventas'
    if nombre == 'conciliar_banco':
        return 'finanzas'
    if nombre == 'consultar_finanzas':
        return 'finanzas' if args.get('consulta') in DE_FINANZAS else 'contabilidad'
    if nombre == 'guia_libros_sii':
        return 'contabilidad'
    return None


def agente_de(nombre, args):
    return AGENTES.get(modulo_de(nombre, args))


def de(nombre, args, resultado, org=None):
    tarjeta = _de(nombre, args, resultado, org)
    if tarjeta:
        modulo = modulo_de(nombre, args) or tarjeta.get('modulo')
        tarjeta['modulo'] = modulo or tarjeta.get('modulo')
        tarjeta['agente'] = AGENTES.get(tarjeta['modulo'], 'Afable')
    return tarjeta


def _de(nombre, args, resultado, org=None):
    if not isinstance(resultado, dict) or resultado.get('error'):
        return None
    args = args or {}
    try:
        if nombre == 'compras_ventas':
            return _comercial(args, resultado, org)
        if nombre == 'consultar_finanzas':
            return _finanzas(args, resultado)
        if nombre == 'conciliar_banco':
            return _conciliar(args, resultado)
        if nombre == 'guia_libros_sii':
            return {'tipo': 'guia', 'modulo': 'contabilidad', 'titulo': 'Cómo bajar sus libros del SII',
                    'subtitulo': 'Paso a paso, y el archivo se sube aquí mismo', 'libro': resultado.get('guia', 'compras')}
    except Exception:  # una tarjeta que no se pudo armar no debe tumbar la respuesta
        return None
    return None


# ── Compras y Ventas ─────────────────────────────────────────────────────────────

HECHOS = {
    'confirmar': 'Orden confirmada',
    'cancelar': 'Pedido cancelado',
    'registrar_entrega': 'Entrega registrada',
    'registrar_pago': 'Pago registrado',
    'enviar_correo': 'Correo enviado',
}


def _modulo(args, numero=''):
    if args.get('tipo') == 'compra' or str(numero).upper().startswith('OC'):
        return 'compras'
    return 'ventas'


def _documento(p, etapa, enlace, nota=''):
    from apps.comercial.models import VENTA
    venta = p.tipo == VENTA
    if p.es_orden:
        nombre = 'Orden de venta' if venta else 'Orden de compra'
    else:
        nombre = 'Cotización' if venta else 'Solicitud de compra'
    return {
        'tipo': 'documento', 'modulo': 'ventas' if venta else 'compras',
        'titulo': f'{nombre} {p.numero}', 'subtitulo': p.contacto.razon_social, 'estado': etapa,
        'lineas': [{'descripcion': l.descripcion, 'cantidad': _num(l.cantidad),
                    'precio': _clp(l.precio_unitario), 'monto': _clp(l.cantidad * l.precio_unitario)}
                   for l in p.lineas.all()[:MAX_FILAS]],
        'totales': [{'etiqueta': 'Neto', 'valor': _clp(p.neto)}, {'etiqueta': 'IVA', 'valor': _clp(p.iva)},
                    {'etiqueta': f'Total{"" if p.moneda == "CLP" else " " + p.moneda}', 'valor': _clp(p.total), 'destacado': True}],
        'enlace': enlace, 'nota': nota,
    }


def _factura(r, org):
    """La factura electrónica emitida: lo que la pantalla anima (se arma, se firma, va al SII y
    queda aceptada) y el id para bajar su PDF."""
    from apps.finanzas.models import DocumentoTributario
    f = r['factura_emitida']
    doc = DocumentoTributario.objects.filter(organization=org, pk=f['id']).first()
    vinculo = doc.pedidos.select_related('pedido').first() if doc else None
    pedido = vinculo.pedido if vinculo else None
    lineas = []
    if pedido and abs(pedido.base_clp - f['neto']) <= 1:
        lineas = [{'descripcion': l.descripcion, 'cantidad': _num(l.cantidad), 'precio': _clp(l.precio_unitario),
                   'monto': _clp(l.subtotal)} for l in pedido.lineas.all()[:MAX_FILAS]]
    return {
        'tipo': 'factura', 'modulo': 'ventas', 'titulo': f'Factura electrónica N° {f["folio"]}',
        'folio': f['folio'], 'fecha': f['fecha'], 'emisor': org.name, 'emisor_rut': org.rut or '',
        'subtitulo': f'{f["cliente"]} · {f["rut"]}', 'estado': 'Aceptada por el SII', 'lineas': lineas,
        'totales': [{'etiqueta': 'Neto', 'valor': _clp(f['neto'])}, {'etiqueta': 'IVA 19%', 'valor': _clp(f['iva'])},
                    {'etiqueta': 'Total', 'valor': _clp(f['total']), 'destacado': True}],
        'documento_id': f['id'], 'nota': f'Orden {r.get("pedido", "")} · {r.get("etapa", "")}'.strip(' ·'),
        'enlace': r.get('enlace', ''),
    }


def _comercial(args, r, org):
    from apps.comercial.models import Pedido
    accion = args.get('accion')

    if r.get('requiere_eleccion'):
        return {'tipo': 'elegir', 'modulo': 'ventas', 'titulo': '¿Qué factura?', 'texto': r.get('pregunta', ''),
                'opciones': r.get('opciones', [])}

    if r.get('requiere_confirmacion'):
        modulo = 'compras' if accion == 'registrar_factura_proveedor' else _modulo(args, args.get('numero'))
        return {'tipo': 'confirmar', 'modulo': modulo, 'titulo': '¿Lo confirma?', 'texto': r.get('se_hara', '')}

    if r.get('factura_emitida') and org is not None:
        return _factura(r, org)

    if r.get('registrada'):
        f = r['registrada']
        nota = ' · '.join(x for x in (f'Categoría: {f["categoria"]}' if f.get('categoria') else 'Sin categoría: queda por revisar',
                                       f'Amarrada a {f["orden"]}' if f.get('orden') else '') if x)
        return {'tipo': 'documento', 'modulo': 'compras', 'titulo': f'Factura de proveedor N° {f["folio"]}',
                'subtitulo': f'{f["proveedor"]} · {f["rut"]}', 'estado': 'Registrada', 'lineas': [],
                'totales': [{'etiqueta': 'Neto', 'valor': _clp(f['neto'])}, {'etiqueta': 'IVA', 'valor': _clp(f['iva'])},
                            {'etiqueta': 'Total', 'valor': _clp(f['total']), 'destacado': True}],
                'nota': nota, 'enlace': r.get('enlace', '')}

    if accion in ('crear_cotizacion', 'duplicar') and r.get('creada') and org is not None:
        p = Pedido.objects.filter(organization=org, numero=r['creada']).select_related('contacto').first()
        if p:
            return _documento(p, r.get('etapa', ''), r.get('enlace', ''), r.get('nota', ''))

    if accion == 'pedido' and org is not None:
        p = Pedido.objects.filter(organization=org, numero__iexact=r.get('numero', '')).select_related('contacto').first()
        if p:
            return _documento(p, r.get('etapa', ''), r.get('enlace', ''))

    if r.get('hecho'):
        return {'tipo': 'hecho', 'modulo': _modulo(args, args.get('numero')),
                'titulo': HECHOS.get(accion, 'Listo'), 'texto': r['hecho'],
                'estado': r.get('etapa', ''), 'enlace': r.get('enlace', '')}

    if accion in ('crear_contacto', 'crear_producto') and r.get('creado'):
        return {'tipo': 'hecho', 'modulo': 'compras' if 'proveedores' in r.get('enlace', '') else 'ventas',
                'titulo': 'Contacto creado' if accion == 'crear_contacto' else 'Producto creado',
                'texto': r['creado'] + (f' · {r["rut"]}' if r.get('rut') else ''), 'enlace': r.get('enlace', '')}

    if accion == 'reponer_stock' and r.get('creadas') is not None:
        return {'tipo': 'lista', 'modulo': 'compras', 'titulo': 'Solicitudes de compra para reponer',
                'filas': [{'titulo': x} for x in r['creadas'][:MAX_FILAS]],
                'nota': r.get('nota', ''), 'enlace': r.get('enlace', '')}

    if accion == 'resumen':
        v, c = r.get('venta') or {}, r.get('compra') or {}
        return {'tipo': 'cifras', 'modulo': 'ventas', 'titulo': 'Compras y ventas, hoy', 'cifras': [
            {'etiqueta': 'Cotizaciones abiertas', 'valor': _clp(v.get('cotizado_clp', 0)), 'detalle': f'{v.get("cotizaciones_abiertas", 0)} de venta'},
            {'etiqueta': 'Ventas por facturar', 'valor': _clp(v.get('por_facturar_clp', 0)), 'detalle': f'{v.get("ordenes_por_facturar", 0)} órdenes', 'destacado': True},
            {'etiqueta': 'Solicitudes abiertas', 'valor': _clp(c.get('cotizado_clp', 0)), 'detalle': f'{c.get("cotizaciones_abiertas", 0)} de compra'},
            {'etiqueta': 'Compras por facturar', 'valor': _clp(c.get('por_facturar_clp', 0)), 'detalle': f'{c.get("ordenes_por_facturar", 0)} órdenes'},
        ]}

    if accion in ('pedidos', 'por_facturar') and r.get('pedidos') is not None:
        por_facturar = accion == 'por_facturar'
        modulo = _modulo(args) if args.get('tipo') else 'ventas'
        return {'tipo': 'lista', 'modulo': modulo,
                'titulo': 'Por facturar' if por_facturar else ('Órdenes y cotizaciones' if not args.get('vista') else args['vista'].capitalize()),
                'filas': [{'titulo': p['numero'], 'detalle': p['contacto'], 'estado': p['etapa'],
                           'valor': _clp(p['por_facturar_clp'] if por_facturar else p['neto_clp']), 'enlace': p.get('enlace', '')}
                          for p in r['pedidos'][:MAX_FILAS]],
                'nota': f'{r.get("cantidad", 0)} en total' if r.get('cantidad', 0) > MAX_FILAS else '',
                'enlace': f'/app/{modulo}/{"por-facturar" if por_facturar else "ordenes"}'}

    if accion == 'reporte' and r.get('filas') is not None:
        total = r.get('total') or {}
        filas = r['filas'][:MAX_FILAS]
        mayor = max([abs(f.get('monto') or 0) for f in filas] or [1]) or 1
        compra = args.get('tipo') == 'compra'
        totales = [{'etiqueta': 'Total', 'valor': _clp(total.get('monto', 0)), 'destacado': True}]
        if not compra and total.get('margen') is not None:
            totales.append({'etiqueta': 'Margen', 'valor': f'{_clp(total["margen"])} · {_pct(total.get("margen_pct", 0))}'})
        return {'tipo': 'barras', 'modulo': 'compras' if compra else 'ventas',
                'titulo': f'{"Compras" if compra else "Ventas"} por {args.get("por") or "producto"}',
                'subtitulo': f'{r.get("desde")} a {r.get("hasta")}',
                'barras': [{'etiqueta': f.get('nombre') or f.get('clave'), 'valor': _clp(f.get('monto', 0)),
                            'proporcion': round(abs(f.get('monto') or 0) / mayor, 3)} for f in filas],
                'totales': totales, 'enlace': r.get('enlace', '')}

    if accion == 'stock' and r.get('productos') is not None:
        def bajo(x):
            try:
                return Decimal(str(x['stock'])) < Decimal(str(x['stock_minimo']))
            except (InvalidOperation, KeyError):
                return False
        productos = sorted(r['productos'], key=lambda x: not bajo(x))[:MAX_FILAS]
        return {'tipo': 'lista', 'modulo': 'compras', 'titulo': 'Stock', 'filas': [
            {'titulo': x['nombre'], 'detalle': f'mínimo {_num(x["stock_minimo"])} {x.get("unidad", "")}'.strip(),
             'valor': f'{_num(x["stock"])} {x.get("unidad", "")}'.strip(), 'estado': 'Bajo el mínimo' if bajo(x) else ''}
            for x in productos], 'enlace': '/app/compras/inventario'}
    return None


# ── Conciliación ─────────────────────────────────────────────────────────────────

HECHOS_CONCILIAR = {
    'conciliar': 'Movimiento conciliado', 'identificar': 'Movimiento identificado',
    'traspaso': 'Traspaso confirmado', 'no_es_traspaso': 'Traspaso descartado', 'deshacer': 'Movimiento deshecho',
}


def _conciliar(args, r):
    accion = args.get('accion')
    if r.get('requiere_confirmacion'):
        return {'tipo': 'confirmar', 'modulo': 'contabilidad', 'titulo': '¿Lo confirma?', 'texto': r.get('se_hara', '')}
    if r.get('hecho'):
        pct = r.get('porcentaje_cuadrado')
        return {'tipo': 'hecho', 'modulo': 'contabilidad', 'titulo': HECHOS_CONCILIAR.get(accion, 'Listo'),
                'texto': r['hecho'], 'estado': f'{_pct(pct)} cuadrado' if pct is not None else '',
                'nota': f'Quedan {r.get("quedan_pendientes", 0)} por explicar.' if r.get('quedan_pendientes') else 'El mes quedó cuadrado.',
                'enlace': r.get('enlace', '')}
    if accion == 'cruzar':
        return {'tipo': 'cifras', 'modulo': 'contabilidad', 'titulo': 'Cruce con el banco', 'cifras': [
            {'etiqueta': 'Cruzados ahora', 'valor': str(r.get('cruzados', 0)), 'destacado': True},
            {'etiqueta': 'Cuadrado', 'valor': _pct(r.get('porcentaje_cuadrado') or 0),
             'detalle': f'{MESES[int(r["mes"]) - 1]} {r.get("anio", "")}' if r.get('mes') else ''},
            {'etiqueta': 'Por explicar', 'valor': str(r.get('quedan_pendientes', 0))},
        ], 'enlace': r.get('enlace', '')}
    if accion == 'pendientes':
        filas = []
        for m in r.get('pendientes') or []:
            if m.get('posible_traspaso_con'):
                detalle, estado = f'con {m["posible_traspaso_con"]["cuenta"]}', 'Posible traspaso'
            elif m.get('candidatos'):
                c = m['candidatos'][0]
                otros = len(m['candidatos']) - 1
                detalle = f'¿folio {c["folio"]} de {c["razon_social"]}?' + (f' · {otros} más' if otros else '')
                estado = 'Mismo monto' if not c.get('diferencia') else f'dif. {_clp(c["diferencia"])}'
            else:
                detalle, estado = m.get('cuenta', ''), 'Sin documento'
            filas.append({'titulo': m['descripcion'], 'detalle': f'{m["fecha"][8:10]}-{m["fecha"][5:7]} · {detalle}',
                          'valor': _clp(m['monto']), 'estado': estado})
        mes = MESES[int(r['mes']) - 1] if r.get('mes') else ''
        pct = r.get('porcentaje_cuadrado')
        return {'tipo': 'lista', 'modulo': 'contabilidad', 'titulo': f'Por conciliar en {mes}'.strip(),
                'subtitulo': f'{_pct(pct)} cuadrado' if pct is not None else '', 'filas': filas[:MAX_FILAS],
                'nota': f'{r.get("cantidad", 0)} en total' if r.get('cantidad', 0) > MAX_FILAS else '',
                'enlace': r.get('enlace', '')}
    return None


# ── Finanzas y Contabilidad ──────────────────────────────────────────────────────

def _finanzas(args, r):
    consulta = args.get('consulta')

    if consulta == 'resumen_mes':
        mes = MESES[int(r['mes']) - 1].capitalize() if r.get('mes') else ''
        return {'tipo': 'cifras', 'modulo': 'contabilidad', 'titulo': f'{mes} {r.get("anio", "")}'.strip(), 'cifras': [
            {'etiqueta': 'Ganancia', 'valor': _clp(r['mes_ganancia']), 'detalle': f'margen {_pct(r.get("mes_margen_pct", 0))}', 'destacado': True},
            {'etiqueta': 'Ingresos', 'valor': _clp(r['mes_ingresos_sin_iva']), 'detalle': 'sin IVA'},
            {'etiqueta': 'Gastos', 'valor': _clp(r['mes_gastos_sin_iva']), 'detalle': 'sin IVA'},
            {'etiqueta': f'Resultado de {r.get("anio", "")}', 'valor': _clp(r['anio_ganancia']), 'detalle': 'acumulado del año'},
        ], 'enlace': '/app/contabilidad'}

    if consulta == 'f29' and r.get('meses'):
        m = r['meses'][-1]
        if args.get('mes'):
            m = next((x for x in r['meses'] if x['mes'] == int(args['mes'])), m)
        return {'tipo': 'cifras', 'modulo': 'contabilidad', 'titulo': f'F29 de {MESES[m["mes"] - 1]}', 'cifras': [
            {'etiqueta': 'A pagar', 'valor': _clp(m['estimado']), 'detalle': f'vence el {m["vence"]}' + (' · pagado' if m.get('pagado') else ''), 'destacado': True},
            {'etiqueta': 'IVA', 'valor': _clp(m['iva_neto']), 'detalle': f'débito {_clp(m["iva_debito"])} − crédito {_clp(m["iva_credito"])}'},
            {'etiqueta': 'PPM', 'valor': _clp(m['ppm'])},
            {'etiqueta': 'Retención de honorarios', 'valor': _clp(m['retencion'])},
        ], 'nota': r.get('nota', ''), 'enlace': '/app/contabilidad/impuestos'}

    if consulta in ('por_cobrar', 'por_pagar'):
        cobrar = consulta == 'por_cobrar'
        filas = (r.get('principales_contrapartes') or [])[:MAX_FILAS]
        mayor = max([f.get('monto') or 0 for f in filas] or [1]) or 1
        return {'tipo': 'barras', 'modulo': 'finanzas', 'titulo': 'Le deben' if cobrar else 'Debe',
                'barras': [{'etiqueta': f['razon_social'], 'valor': _clp(f['monto']), 'proporcion': round((f['monto'] or 0) / mayor, 3),
                            'alerta': bool(f.get('vencido'))} for f in filas],
                'totales': [{'etiqueta': 'Total', 'valor': _clp(r.get('total', 0)), 'destacado': True},
                            {'etiqueta': 'Vencido', 'valor': f'{_clp(r.get("vencido", 0))} · {_pct(r.get("porcentaje_vencido", 0))}'}],
                'enlace': f'/app/finanzas/{"por-cobrar" if cobrar else "por-pagar"}'}

    if consulta == 'caja':
        if r.get('disponible') is None:
            return None
        cifras = [{'etiqueta': 'Disponible en bancos', 'valor': _clp(r['disponible']), 'destacado': True}]
        if r.get('puede_retirar') is not None:
            cifras.append({'etiqueta': 'Puede retirar', 'valor': _clp(r['puede_retirar'])})
        if r.get('saldo_30_dias') is not None:
            cifras.append({'etiqueta': 'Saldo en 30 días', 'valor': _clp(r['saldo_30_dias']),
                           'detalle': f'entran {_clp(r.get("entradas_esperadas", 0))} · salen {_clp(r.get("salidas_comprometidas", 0))}'})
        if r.get('meses_de_caja') is not None:
            cifras.append({'etiqueta': 'Meses de caja', 'valor': str(r['meses_de_caja']).replace('.', ',')})
        return {'tipo': 'cifras', 'modulo': 'finanzas', 'titulo': 'Caja', 'cifras': cifras, 'enlace': '/app/finanzas/caja'}

    if consulta == 'conciliacion':
        mes = MESES[int(r['mes']) - 1] if r.get('mes') else ''
        return {'tipo': 'cifras', 'modulo': 'contabilidad', 'titulo': f'Conciliación de {mes}'.strip(), 'cifras': [
            {'etiqueta': 'Cuadrado con el banco', 'valor': _pct(r.get('porcentaje', 0)), 'destacado': True},
            {'etiqueta': 'Movimientos', 'valor': str(r.get('movimientos', 0)), 'detalle': f'{r.get("cuadraron_solos", 0)} cuadraron solos'},
            {'etiqueta': 'Pendientes', 'valor': str(r.get('pendientes', 0))},
        ], 'enlace': '/app/contabilidad/conciliacion'}

    if consulta == 'gasto_por_categoria':
        g = r.get('gastos') or {}
        filas = (g.get('filas') or [])[:MAX_FILAS]
        mayor = max([f.get('monto') or 0 for f in filas] or [1]) or 1
        return {'tipo': 'barras', 'modulo': 'contabilidad', 'titulo': 'Gasto por categoría',
                'barras': [{'etiqueta': f['categoria'], 'valor': f'{_clp(f["monto"])} · {_pct(f.get("porcentaje", 0))}',
                            'proporcion': round((f['monto'] or 0) / mayor, 3)} for f in filas],
                'totales': [{'etiqueta': 'Total', 'valor': _clp(g.get('total', 0)), 'destacado': True}],
                'enlace': '/app/contabilidad/categorias'}
    return None

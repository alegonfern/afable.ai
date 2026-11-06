"""Lo que hizo hoy el agente de un módulo (25-10-2026): la columna en vivo de su vista "Agente".

Sale de hechos registrados, no de un relato: las órdenes confirmadas y las facturas emitidas hoy,
los cobros y pagos, las entregas y recepciones, los libros del SII y las cartolas cargadas, y las
automatizaciones del módulo que corrieron. Cada cosa con su hora, para que la pantalla la anime a
medida que ocurre ("ver cómo avanza su empresa").
"""
from datetime import datetime, time

from django.utils import timezone

MODULOS = ('ventas', 'compras', 'inventario', 'contabilidad', 'finanzas')


def _clp(n):
    return f'${round(n):,}'.replace(',', '.')


def _inicio_de_hoy():
    hoy = timezone.localdate()
    return timezone.make_aware(datetime.combine(hoy, time.min)), hoy


def _automatizaciones(org, modulo, desde):
    from .models import AutomatizacionModulo
    from . import automatizaciones as fa
    catalogo = dict(fa.POR_CLAVE)
    try:
        from apps.comercial import automatizaciones as ca
        catalogo.update({a['clave']: a for a in ca.CATALOGO})
    except (ImportError, AttributeError):
        pass
    out = []
    for a in AutomatizacionModulo.objects.filter(organization=org, ultima_ejecucion__gte=desde):
        info = catalogo.get(a.clave) or {}
        if info.get('modulo') != modulo:
            continue
        out.append({'hora': a.ultima_ejecucion, 'tipo': 'automatizacion', 'titulo': info.get('nombre', a.clave),
                    'detalle': (a.ultimo_resultado or 'Corrió sin novedades.')[:200], 'enlace': f'/app/{modulo}/automatizaciones'})
    return out


def de_hoy(org, modulo):
    from apps.comercial.models import COMPRA, VENTA, Entrega, PagoPedido, Pedido
    from .models import Cartola, Carga, DocumentoTributario
    desde, hoy = _inicio_de_hoy()
    items = []

    if modulo in ('ventas', 'compras'):
        tipo = VENTA if modulo == 'ventas' else COMPRA
        for p in Pedido.objects.filter(organization=org, tipo=tipo, confirmado_en__gte=desde).select_related('contacto'):
            items.append({'hora': p.confirmado_en, 'tipo': 'orden', 'titulo': f'Confirmó {p.numero}',
                          'detalle': f'{p.contacto.razon_social} · {_clp(p.base_clp)} neto', 'enlace': f'/app/{modulo}/ordenes/{p.id}'})
        for x in PagoPedido.objects.filter(pedido__organization=org, pedido__tipo=tipo, creado_en__gte=desde).select_related('pedido'):
            items.append({'hora': x.creado_en, 'tipo': 'pago', 'titulo': f'Registró {"un cobro" if tipo == VENTA else "un pago"} de {x.pedido.numero}',
                          'detalle': _clp(x.monto), 'enlace': f'/app/{modulo}/ordenes/{x.pedido_id}'})
        for e in Entrega.objects.filter(organization=org, pedido__tipo=tipo, creado_en__gte=desde).select_related('pedido'):
            accion = ('Registró la devolución' if e.tipo == Entrega.DEVOLUCION
                      else 'Registró la entrega' if tipo == VENTA else 'Registró la recepción')
            items.append({'hora': e.creado_en, 'tipo': 'entrega', 'titulo': f'{accion} {e.numero}',
                          'detalle': e.pedido.numero, 'enlace': f'/app/{modulo}/ordenes/{e.pedido_id}'})

    if modulo == 'ventas':
        for d in DocumentoTributario.objects.filter(organization=org, emitido_en_afable=True, creado_en__gte=desde):
            items.append({'hora': d.creado_en, 'tipo': 'factura', 'titulo': f'Emitió la factura N° {d.folio}',
                          'detalle': f'{d.razon_social} · {_clp(d.monto_total)}', 'enlace': '/app/ventas/por-facturar'})
    if modulo == 'compras':
        for d in DocumentoTributario.objects.filter(organization=org, libro='compras', carga__isnull=True, creado_en__gte=desde):
            items.append({'hora': d.creado_en, 'tipo': 'factura', 'titulo': f'Registró la factura {d.folio} de proveedor',
                          'detalle': f'{d.razon_social} · {_clp(d.monto_total)}', 'enlace': '/app/contabilidad/documentos'})
    if modulo == 'inventario':
        from apps.comercial.models import MovimientoStock
        for m in (MovimientoStock.objects.filter(organization=org, creado_en__gte=desde, entrega__isnull=True)
                  .select_related('producto')):
            items.append({'hora': m.creado_en, 'tipo': 'stock', 'titulo': f'Movió stock de {m.producto.nombre}',
                          'detalle': f'{m.get_tipo_display()} · {m.cantidad.normalize():f} {m.producto.unidad}',
                          'enlace': '/app/inventario'})
        for p in Pedido.objects.filter(organization=org, tipo=COMPRA, origen='reposicion', creado_en__gte=desde):
            items.append({'hora': p.creado_en, 'tipo': 'orden', 'titulo': f'Armó la solicitud de reposición {p.numero}',
                          'detalle': p.contacto.razon_social, 'enlace': f'/app/compras/cotizaciones/{p.id}'})
    if modulo == 'contabilidad':
        nombres = {'compras': 'Registro de Compras', 'ventas': 'Registro de Ventas', 'honorarios': 'boletas de honorarios'}
        for c in Carga.objects.filter(organization=org, creada_en__gte=desde, nuevos__gt=0):
            items.append({'hora': c.creada_en, 'tipo': 'carga', 'titulo': f'Cargó el {nombres.get(c.libro, c.libro)}',
                          'detalle': f'{c.nuevos} documentos nuevos', 'enlace': '/app/contabilidad/documentos'})
    if modulo == 'finanzas':
        for c in Cartola.objects.filter(organization=org, creada_en__gte=desde).select_related('cuenta'):
            items.append({'hora': c.creada_en, 'tipo': 'cartola', 'titulo': f'Cruzó la cartola de {c.cuenta}',
                          'detalle': f'{c.nuevos} movimientos nuevos', 'enlace': '/app/contabilidad/conciliacion'})

    items += _automatizaciones(org, modulo, desde)
    items.sort(key=lambda x: x['hora'], reverse=True)
    for x in items:
        x['hora'] = timezone.localtime(x['hora']).strftime('%H:%M')
    return items[:30]

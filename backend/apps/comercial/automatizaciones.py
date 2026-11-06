"""Las automatizaciones de Compras y Ventas. Se suman al catálogo de `finanzas.automatizaciones`
(ver `ComercialConfig.ready`) y corren con el mismo motor: programación, seguidores y canales.
Cada una devuelve None si no hay nada que decir, o (marca, título, detalle, enlace)."""

from datetime import timedelta
from decimal import Decimal

from apps.finanzas.models import DocumentoTributario

from . import facturacion
from .models import COMPRA, VENTA, ConfiguracionComercial, Pedido, PedidoFactura, Producto, stock


def _prog(frecuencia, hora=8, dia_semana=0, dia_mes=1):
    return {'frecuencia': frecuencia, 'hora': hora, 'dia_semana': dia_semana, 'dia_mes': dia_mes}


CATALOGO = [
    {'clave': 'cotizaciones_sin_respuesta', 'modulo': 'ventas',
     'nombre': 'Cotizaciones enviadas sin respuesta',
     'descripcion': 'Las cotizaciones enviadas hace más días de los configurados que el cliente no ha confirmado, para hacerles seguimiento.',
     'programacion': _prog('diaria', hora=9)},
    {'clave': 'ventas_por_facturar', 'modulo': 'ventas',
     'nombre': 'Ventas por facturar',
     'descripcion': 'Órdenes de venta (o entregas, según su política) que todavía no tienen factura en el SII.',
     'programacion': _prog('semanal')},
    {'clave': 'oc_atrasadas', 'modulo': 'compras',
     'nombre': 'Órdenes de compra atrasadas',
     'descripcion': 'Las OC confirmadas cuya fecha de llegada ya pasó y todavía no se reciben completas.',
     'programacion': _prog('diaria')},
    {'clave': 'facturas_compra_con_diferencia', 'modulo': 'compras',
     'nombre': 'Facturas de proveedor que no cuadran',
     'descripcion': 'Facturas de compra sin orden de compra, o que cobran más de lo pedido o recibido.',
     'programacion': _prog('semanal')},
    {'clave': 'stock_bajo', 'modulo': 'inventario',
     'nombre': 'Productos bajo el stock mínimo',
     'descripcion': 'Los productos con menos stock que su mínimo, para reponerlos a tiempo. Requiere inventario activado.',
     'programacion': _prog('diaria')},
    # Las dos que hacen el trabajo, no solo avisan (24-10-2026).
    {'clave': 'recordar_cotizaciones', 'modulo': 'ventas',
     'nombre': 'Recordarle al cliente las cotizaciones sin respuesta',
     'descripcion': 'Le escribe al cliente, con la cotización adjunta, cuando pasan los días configurados sin '
                    'respuesta. Una vez por cotización, y solo a los que tienen correo.',
     'programacion': _prog('diaria', hora=10)},
    {'clave': 'reponer_stock', 'modulo': 'inventario',
     'nombre': 'Armar las solicitudes de compra para reponer stock',
     'descripcion': 'Cuando un producto baja de su mínimo, arma la solicitud de compra al proveedor que lo vende '
                    '(el preferido o el más barato), lista para revisar y enviar. No repite lo que ya está pedido.',
     'programacion': _prog('diaria', hora=7)},
]


def _clp(n):
    return f'${round(n):,}'.replace(',', '.')


def _lista(items, n=5):
    return '; '.join(items[:n]) + (f' y {len(items) - n} más' if len(items) > n else '')


def _cotizaciones_sin_respuesta(org, hoy, forzar):
    cfg = ConfiguracionComercial.de(org)
    limite = hoy - timedelta(days=cfg.dias_sin_respuesta)
    pendientes = list(Pedido.objects.filter(organization=org, tipo=VENTA, estado=Pedido.ENVIADO,
                                            fecha__lte=limite).select_related('contacto').order_by('fecha'))
    if not pendientes:
        return None
    total = sum(p.base_clp for p in pendientes)
    items = [f'{p.numero} {p.contacto.razon_social} {_clp(p.base_clp)} ({(hoy - p.fecha).days} días)' for p in pendientes]
    return (f'cotiz-{hoy.isoformat()}', f'{len(pendientes)} cotizaciones sin respuesta ({_clp(total)})',
            f'Enviadas hace más de {cfg.dias_sin_respuesta} días y sin confirmar: {_lista(items)}.',
            '/app/ventas/cotizaciones')


def _ventas_por_facturar(org, hoy, forzar):
    filas = [(p, e) for p, e in facturacion.por_facturar(org, VENTA) if e['por_facturar_clp'] > 0]
    if not filas:
        return None
    total = sum(e['por_facturar_clp'] for _, e in filas)
    items = [f'{p.numero} {p.contacto.razon_social} {_clp(e["por_facturar_clp"])}' for p, e in filas]
    return (f'porfact-{hoy.isoformat()}', f'Tiene {_clp(total)} vendido sin facturar',
            f'{len(filas)} órdenes sin factura en el SII: {_lista(items)}. Si ya las facturó, cargue el '
            'Registro de Ventas para que se vinculen.', '/app/ventas/por-facturar')


def _oc_atrasadas(org, hoy, forzar):
    atrasadas = []
    for p in (Pedido.objects.filter(organization=org, tipo=COMPRA, estado=Pedido.CONFIRMADO,
                                    fecha_compromiso__lt=hoy).select_related('contacto').prefetch_related('lineas')):
        if any(l.pendiente_entrega > 0 for l in p.lineas.all()):
            atrasadas.append(p)
    if not atrasadas:
        return None
    items = [f'{p.numero} {p.contacto.razon_social} (debía llegar el {p.fecha_compromiso.strftime("%d-%m")})' for p in atrasadas]
    return (f'ocatr-{hoy.isoformat()}', f'{len(atrasadas)} órdenes de compra atrasadas',
            f'Todavía sin recibir completas: {_lista(items)}.', '/app/compras/ordenes')


def _facturas_compra_con_diferencia(org, hoy, forzar):
    cfg = ConfiguracionComercial.de(org)
    hay_oc = Pedido.objects.filter(organization=org, tipo=COMPRA).exists()
    problemas = []
    if hay_oc:
        # Facturas de proveedores con los que se trabaja con OC, de los últimos 60 días, sin OC.
        ruts = set(Pedido.objects.filter(organization=org, tipo=COMPRA).values_list('contacto__rut', flat=True))
        con_oc = set(PedidoFactura.objects.filter(pedido__organization=org).values_list('documento_id', flat=True))
        for d in DocumentoTributario.objects.filter(organization=org, libro='compras', rut__in=ruts,
                                                    fecha__gte=hoy - timedelta(days=60)).exclude(id__in=con_oc):
            if d.signo > 0:
                problemas.append(f'{d.razon_social} folio {d.folio} {_clp(facturacion.base_documento(d))}: sin OC')
    for p in Pedido.objects.filter(organization=org, tipo=COMPRA, estado=Pedido.CONFIRMADO).select_related('contacto'):
        for dif in facturacion.estado(p, cfg)['diferencias']:
            problemas.append(f'{p.numero} {p.contacto.razon_social}: {dif}')
    if not problemas:
        return None
    return (f'difcomp-{hoy.isoformat()}', f'{len(problemas)} facturas de proveedor por revisar',
            f'{_lista(problemas)}.', '/app/compras/por-facturar')


def _stock_bajo(org, hoy, forzar):
    cfg = ConfiguracionComercial.de(org)
    if not cfg.con_inventario:
        return None
    hay = {}
    for (pid, _), cant in stock(org).items():
        hay[pid] = hay.get(pid, Decimal('0')) + cant
    bajos = [p for p in Producto.objects.filter(organization=org, activo=True, tipo=Producto.ALMACENABLE,
                                                stock_minimo__gt=0)
             if hay.get(p.id, Decimal('0')) < p.stock_minimo]
    if not bajos:
        return None
    items = [f'{p.nombre}: {hay.get(p.id, Decimal("0")).normalize()} de mínimo {p.stock_minimo.normalize()} {p.unidad}' for p in bajos]
    # La marca es el conjunto de productos: avisa de nuevo solo si cambia la lista.
    return (f'stock-{"-".join(str(p.id) for p in bajos)}'[:60], f'{len(bajos)} productos bajo el mínimo',
            f'Para reponer: {_lista(items)}.', '/app/inventario')


def _recordar_cotizaciones(org, hoy, forzar):
    """Le escribe al cliente. Con `forzar` (Probar ahora) solo cuenta a quiénes les escribiría."""
    from django.utils import timezone

    from . import correo
    cfg = ConfiguracionComercial.de(org)
    limite = hoy - timedelta(days=cfg.dias_sin_respuesta)
    pendientes = list(Pedido.objects.filter(organization=org, tipo=VENTA, estado=Pedido.ENVIADO, recordado_en=None,
                                            enviado_en__date__lte=limite).select_related('contacto', 'organization'))
    con_correo = [p for p in pendientes if p.contacto.email and '@' in p.contacto.email]
    sin_correo = [p for p in pendientes if p not in con_correo]
    if not pendientes:
        return None
    enviados, fallidos = [], []
    for p in con_correo:
        if forzar:
            enviados.append(p)
            continue
        dias = (hoy - (p.enviado_en.date() if p.enviado_en else p.fecha)).days
        mensaje = (f'Estimado(a):\n\nLe escribimos para saber si pudo revisar la {pdf_titulo(p)} {p.numero} que le '
                   f'enviamos hace {dias} días. La adjuntamos de nuevo por si la necesita.\n\nQuedamos atentos a sus '
                   f'comentarios.\n\nSaludos,\n{org.name}')
        try:
            correo.enviar(p, p.contacto.email, mensaje, titulo=f'Seguimiento: {pdf_titulo(p)} {p.numero} · {org.name}')
        except Exception:
            fallidos.append(p)
            continue
        p.recordado_en = timezone.now()
        p.save(update_fields=['recordado_en'])
        enviados.append(p)
    partes = []
    if enviados:
        verbo = 'Le escribiría a' if forzar else 'Se le escribió a'
        partes.append(f'{verbo}: {_lista([f"{p.contacto.razon_social} ({p.numero})" for p in enviados])}.')
    if sin_correo:
        partes.append(f'Sin correo en la ficha (no se les pudo escribir): {_lista([f"{p.contacto.razon_social} ({p.numero})" for p in sin_correo])}.')
    if fallidos:
        partes.append(f'No se pudo enviar a: {_lista([p.contacto.razon_social for p in fallidos])}.')
    titulo = (f'{len(enviados)} clientes recibirían el recordatorio' if forzar
              else f'Se recordaron {len(enviados)} cotizaciones sin respuesta')
    return (f'recordar-{hoy.isoformat()}', titulo, ' '.join(partes), '/app/ventas/cotizaciones')


def pdf_titulo(p):
    from . import pdf
    return pdf.titulo_de(p).lower()


def _reponer_stock(org, hoy, forzar):
    """Arma las solicitudes. Con `forzar` (Probar ahora) solo dice qué armaría."""
    from . import operaciones as op
    cfg = ConfiguracionComercial.de(org)
    if not cfg.con_inventario:
        return None
    if forzar:
        bajos = op.productos_bajo_minimo(org)
        if not bajos:
            return None
        con = [p for p, _ in bajos if op.proveedor_de(p)]
        sin = [p for p, _ in bajos if not op.proveedor_de(p)]
        detalle = (f'Armaría solicitudes para: {_lista([p.nombre for p in con])}.' if con else '') + \
                  (f' Sin proveedor con precio (agréguelo en la ficha del producto): {_lista([p.nombre for p in sin])}.' if sin else '')
        return (f'reponer-{hoy.isoformat()}', f'{len(bajos)} productos para reponer', detalle.strip(), '/app/inventario')
    creadas, sin_proveedor = op.reponer_stock(org)
    if not creadas and not sin_proveedor:
        return None
    detalle = ''
    if creadas:
        detalle += f'Solicitudes listas para revisar y enviar: {_lista([f"{x.numero} a {x.contacto.razon_social}" for x in creadas])}.'
    if sin_proveedor:
        detalle += f' Sin proveedor con precio (agréguelo en la ficha del producto): {_lista([p.nombre for p in sin_proveedor])}.'
    marca = f'reponer-{"-".join(x.numero for x in creadas)}-{"-".join(str(p.id) for p in sin_proveedor)}'[:60]
    return (marca, f'Se armaron {len(creadas)} solicitudes de compra para reponer stock' if creadas
            else f'{len(sin_proveedor)} productos bajo el mínimo sin proveedor',
            detalle.strip(), '/app/compras/cotizaciones')


FUNCIONES = {
    'cotizaciones_sin_respuesta': _cotizaciones_sin_respuesta,
    'ventas_por_facturar': _ventas_por_facturar,
    'oc_atrasadas': _oc_atrasadas,
    'facturas_compra_con_diferencia': _facturas_compra_con_diferencia,
    'stock_bajo': _stock_bajo,
    'recordar_cotizaciones': _recordar_cotizaciones,
    'reponer_stock': _reponer_stock,
}

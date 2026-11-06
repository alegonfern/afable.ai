"""El puente entre los pedidos y las facturas reales del SII.

Una factura no se crea aquí: llega con el Registro de Compras y Ventas. Lo que hace este módulo
es AMARRARLA a su pedido (`PedidoFactura`) y, con eso, decir qué falta por facturar y dónde no
cuadra lo pedido, lo recibido y lo facturado.

Todo se compara en pesos y sin IVA (neto + exento), que es como vienen las facturas del SII.
Las notas de crédito restan.
"""

from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from apps.finanzas.models import DocumentoTributario

from .models import CERO, CLP, COMPRA, VENTA, ConfiguracionComercial, Pedido, PedidoFactura

LIBRO = {VENTA: 'ventas', COMPRA: 'compras'}
TIPO_DE_LIBRO = {'ventas': VENTA, 'compras': COMPRA}


def base_documento(doc):
    """Lo que vale la factura para comparar: sin IVA, en pesos, con signo (la NC resta)."""
    return doc.signo * (doc.monto_neto + doc.monto_exento)


def asignado_de(doc, excepto=None):
    qs = PedidoFactura.objects.filter(documento=doc)
    if excepto is not None:
        qs = qs.exclude(pedido=excepto)
    return qs.aggregate(t=Sum('monto'))['t'] or 0


def disponible_de(doc):
    """Cuánto de la factura queda sin pedido."""
    return base_documento(doc) - asignado_de(doc)


def facturado(pedido):
    return pedido.facturas.aggregate(t=Sum('monto'))['t'] or 0


def entregado_clp(pedido):
    """Lo entregado (o recibido), valorizado al precio del pedido, sin IVA y en pesos."""
    total = sum((l.subtotal_entregado for l in pedido.lineas.all()), CERO)
    return pedido.a_pesos(total)


def base_facturable(pedido, cfg=None):
    """Lo que se espera ver facturado según la política de la empresa."""
    cfg = cfg or ConfiguracionComercial.de(pedido.organization)
    politica = cfg.facturar_ventas if pedido.tipo == VENTA else cfg.facturar_compras
    return entregado_clp(pedido) if politica == ConfiguracionComercial.ENTREGADO else pedido.base_clp


def tolerancia(pedido, cfg):
    return max(1, round(pedido.base_clp * cfg.tolerancia_pct / Decimal('100')))


def estado(pedido, cfg=None):
    """Cómo va el pedido: entregas, facturas, lo que falta y lo que no cuadra."""
    cfg = cfg or ConfiguracionComercial.de(pedido.organization)
    lineas = list(pedido.lineas.all())
    pedida = sum((l.cantidad for l in lineas), CERO)
    entregada = sum((min(l.cantidad_entregada, l.cantidad) for l in lineas), CERO)
    fact = facturado(pedido)
    base = base_facturable(pedido, cfg)
    tol = tolerancia(pedido, cfg)
    if pedida and entregada >= pedida:
        entrega = 'completa'
    elif entregada > 0:
        entrega = 'parcial'
    else:
        entrega = 'pendiente'
    if fact <= 0:
        factura = 'pendiente'
    elif fact + tol >= pedido.base_clp:
        factura = 'completa'
    else:
        factura = 'parcial'

    diferencias = []
    if fact > pedido.base_clp + tol:
        diferencias.append(f'Facturado {_clp(fact)}, más que lo {"pedido" if pedido.tipo == COMPRA else "vendido"} ({_clp(pedido.base_clp)}).')
    recibido = entregado_clp(pedido)
    if pedido.tipo == COMPRA and fact > recibido + tol and pedido.estado == Pedido.CONFIRMADO:
        diferencias.append(f'Facturado {_clp(fact)}, más que lo recibido ({_clp(recibido)}).')

    por_facturar = max(base - fact, 0) if pedido.estado == Pedido.CONFIRMADO else 0
    if por_facturar <= tol:
        por_facturar = 0
    return {
        'entrega': entrega, 'factura': factura,
        'entregado_pct': round(float(entregada * 100 / pedida)) if pedida else 0,
        'entregado_clp': recibido, 'facturado_clp': fact, 'base_clp': pedido.base_clp,
        'por_facturar_clp': por_facturar, 'diferencias': diferencias,
        'etapa': etapa(pedido, entrega, factura),
    }


def etapa(pedido, entrega=None, factura=None):
    """El nombre de lo que el documento es hoy, como lo diría Odoo."""
    venta = pedido.tipo == VENTA
    if pedido.estado == Pedido.CANCELADO:
        return 'Cancelada' if venta else 'Cancelada'
    if pedido.estado == Pedido.BORRADOR:
        return 'Cotización' if venta else 'Solicitud de cotización'
    if pedido.estado == Pedido.ENVIADO:
        return 'Cotización enviada' if venta else 'Solicitud enviada'
    if factura == 'completa' and entrega in ('completa', None):
        return 'Facturada'
    if factura == 'completa':
        return 'Facturada, falta entregar' if venta else 'Facturada, falta recibir'
    if entrega == 'completa':
        return 'Entregada' if venta else 'Recibida'
    if entrega == 'parcial':
        return 'Entrega parcial' if venta else 'Recepción parcial'
    return 'Orden de venta' if venta else 'Orden de compra'


def _clp(n):
    return f'${round(n):,}'.replace(',', '.')


# ── Vincular ──────────────────────────────────────────────────────────────────

def candidatos(pedido, limite=10):
    """Facturas del SII de ese RUT que podrían ser de este pedido, la más parecida primero."""
    if not pedido.contacto.rut:
        return []
    ya = set(pedido.facturas.values_list('documento_id', flat=True))
    pendiente = max(pedido.base_clp - facturado(pedido), 0)
    filas = []
    for doc in DocumentoTributario.objects.filter(
            organization=pedido.organization, libro=LIBRO[pedido.tipo], rut=pedido.contacto.rut,
            fecha__gte=pedido.fecha.replace(day=1)).exclude(id__in=ya):
        libre = disponible_de(doc)
        if libre == 0:
            continue
        filas.append((abs(libre - pendiente), doc, libre))
    filas.sort(key=lambda f: (f[0], -f[1].fecha.toordinal()))
    return [{'documento': d, 'disponible': libre, 'diferencia': libre - pendiente} for _, d, libre in filas[:limite]]


@transaction.atomic
def vincular(pedido, documento, monto=None, usuario=None, origen=PedidoFactura.MANUAL):
    from .operaciones import ErrorComercial
    if documento.organization_id != pedido.organization_id:
        raise ErrorComercial('La factura no es de esta empresa.')
    if documento.libro != LIBRO[pedido.tipo]:
        raise ErrorComercial('Esa factura es del otro libro (compras/ventas).')
    if pedido.estado != Pedido.CONFIRMADO:
        raise ErrorComercial('Solo se vincula una factura a una orden confirmada.')
    libre = base_documento(documento) - asignado_de(documento, excepto=pedido)
    if monto is None:
        pendiente = max(pedido.base_clp - facturado(pedido), 0)
        # Una factura positiva cubre hasta lo pendiente; una nota de crédito resta entera.
        monto = libre if libre < 0 else min(libre, pendiente or libre)
    monto = int(monto)
    if libre >= 0 and not 0 < monto <= libre:
        raise ErrorComercial(f'De esa factura quedan {_clp(libre)} sin pedido.')
    if libre < 0 and not libre <= monto < 0:
        raise ErrorComercial('Monto no válido para la nota de crédito.')
    vinculo, _ = PedidoFactura.objects.update_or_create(
        pedido=pedido, documento=documento,
        defaults={'monto': monto, 'origen': origen, 'creado_por': usuario})
    return vinculo


def desvincular(pedido, documento_id):
    return PedidoFactura.objects.filter(pedido=pedido, documento_id=documento_id).delete()[0]


def vincular_automatico(documentos):
    """Al importar el RCV: si para una factura hay UN solo pedido de ese RUT cuyo pendiente
    cuadra (dentro de la tolerancia), se amarran solas. Si hay dudas, se deja para la persona.
    Devuelve cuántas se vincularon."""
    n = 0
    for doc in documentos:
        if doc.libro not in TIPO_DE_LIBRO or doc.signo < 0 or PedidoFactura.objects.filter(documento=doc).exists():
            continue
        cfg = ConfiguracionComercial.de(doc.organization)
        base = base_documento(doc)
        posibles = []
        for p in Pedido.objects.filter(organization=doc.organization, tipo=TIPO_DE_LIBRO[doc.libro],
                                       estado=Pedido.CONFIRMADO, contacto__rut=doc.rut,
                                       fecha__lte=doc.fecha):
            pendiente = p.base_clp - facturado(p)
            if pendiente > 0 and abs(pendiente - base) <= tolerancia(p, cfg):
                posibles.append(p)
        if len(posibles) == 1:
            vincular(posibles[0], doc, monto=base, origen=PedidoFactura.AUTOMATICA)
            n += 1
    return n


def por_facturar(org, tipo):
    """Órdenes confirmadas con algo por facturar, según la política de la empresa."""
    cfg = ConfiguracionComercial.de(org)
    filas = []
    for p in (Pedido.objects.filter(organization=org, tipo=tipo, estado=Pedido.CONFIRMADO)
              .select_related('contacto').prefetch_related('lineas')):
        e = estado(p, cfg)
        if e['por_facturar_clp'] > 0 or e['diferencias']:
            filas.append((p, e))
    filas.sort(key=lambda f: f[0].fecha)
    return filas

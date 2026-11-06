"""Emitir la factura electrónica desde Afable (etapa 7).

El proveedor de emisión real (OpenFactura, LibreDTE u otro) sigue sin elegirse: cada uno tiene su
API, sus credenciales y su certificación ante el SII, y no se inventan. Mientras tanto emite el
FACTURADOR SIMULADO (25-10-2026): hace todo lo que haría uno real —folio correlativo, el documento
en el Libro de Ventas amarrado a su orden, el PDF con el formato de una factura chilena— sin
enviar nada al SII. Lo único que lo delata es el PDF, que dice "entorno de prueba" (pdf.py).

Para sumar un proveedor real: una clase con `emitir(pedido, monto, usuario) -> DocumentoTributario`
registrada en PROVEEDORES, y `ConfiguracionComercial.proveedor_dte` con su clave.
"""
from datetime import timedelta

from django.db import transaction
from django.db.models import IntegerField
from django.db.models.functions import Cast
from django.utils import timezone

from apps.finanzas import constantes as fc
from apps.finanzas.models import Contraparte, DocumentoTributario

from . import facturacion
from .models import VENTA, ConfiguracionComercial, Pedido, PedidoFactura, Secuencia
from .operaciones import ErrorComercial

FACTURA = '33'
IVA = 0.19


def _siguiente_folio(org):
    """El correlativo de la empresa para facturas: sigue al mayor folio que ya tenga en el Libro de
    Ventas (las que cargó del SII), así no choca con lo emitido antes en otro sistema."""
    sec = Secuencia.objects.select_for_update().get_or_create(organization=org, prefijo='DTE33')[0]
    mayor = (DocumentoTributario.objects.filter(organization=org, libro=fc.LIBRO_VENTAS, tipo_documento=FACTURA,
                                                folio__regex=r'^\d+$')
             .annotate(n=Cast('folio', IntegerField())).order_by('-n').values_list('n', flat=True).first()) or 0
    folio = max(sec.siguiente, mayor + 1)
    sec.siguiente = folio + 1
    sec.save(update_fields=['siguiente'])
    return folio


class FacturadorSimulado:
    clave = 'simulado'

    def emitir(self, pedido, monto, usuario=None):
        org, cliente = pedido.organization, pedido.contacto
        faltan = ConfiguracionComercial.de(org).emisor_faltan
        if faltan:
            lista = ', '.join(faltan[:-1]) + (' y ' if len(faltan) > 1 else '') + faltan[-1]
            raise ErrorComercial(f'Para emitir facturas falta {lista} de su empresa. Complételo en Ventas › Configuración '
                                 '(el ícono de ajustes, arriba a la derecha), sección Facturación electrónica.')
        if not cliente.rut:
            raise ErrorComercial(f'{cliente.razon_social} no tiene RUT en su ficha: agréguelo para facturarle.')
        neto = int(monto)
        iva = round(neto * IVA)
        return registrar(pedido, FACTURA, _siguiente_folio(org), neto=neto, iva=iva, usuario=usuario)


def registrar(pedido, tipo, folio, neto=0, exento=0, iva=0, fecha=None, usuario=None):
    """Deja una factura emitida desde Afable en el Libro de Ventas, amarrada a su orden. La usan el
    facturador simulado y el nativo (apps/dte)."""
    org, cliente = pedido.organization, pedido.contacto
    cp, _ = Contraparte.objects.get_or_create(organization=org, libro=fc.LIBRO_VENTAS, rut=cliente.rut,
                                              defaults={'razon_social': cliente.razon_social, 'contacto': cliente})
    fecha = fecha or timezone.localdate()
    doc = DocumentoTributario.objects.create(
        organization=org, libro=fc.LIBRO_VENTAS, tipo_documento=str(tipo), folio=str(folio),
        rut=cliente.rut, razon_social=cliente.razon_social, fecha=fecha, fecha_vencimiento=fecha + timedelta(days=cp.plazo),
        monto_neto=neto, monto_exento=exento, monto_iva=iva, monto_total=neto + exento + iva, contraparte=cp,
        categoria=cp.categoria if cp.regla_activa else None,
        estado=DocumentoTributario.CONFIRMADO if cp.regla_activa and cp.categoria else DocumentoTributario.POR_REVISAR,
        emitido_en_afable=True,
    )
    facturacion.vincular(pedido, doc, monto=neto + exento, usuario=usuario, origen=PedidoFactura.MANUAL)
    return doc


PROVEEDORES = {'simulado': FacturadorSimulado}


def disponible(org):
    return True


def por_facturar(pedido):
    return max(facturacion.base_facturable(pedido) - facturacion.facturado(pedido), 0)


def opciones(pedido):
    """Lo que se puede facturar de una orden: lo vendido o lo entregado, menos lo ya facturado.
    Cuando difieren, se le pregunta a la persona cuál (25-10-2026) en vez de imponer la política."""
    ya = facturacion.facturado(pedido)
    return {'vendido': max(int(pedido.base_clp) - ya, 0), 'entregado': max(int(facturacion.entregado_clp(pedido)) - ya, 0)}


@transaction.atomic
def emitir(pedido, monto=None, usuario=None, que=None):
    """Emite la factura de lo que falta facturar de una orden de venta confirmada. `que` elige la
    base ('vendido' o 'entregado'); sin él, manda la política de la empresa."""
    if pedido.tipo != VENTA:
        raise ErrorComercial('Solo se emiten facturas de venta: las de compra las emite el proveedor.')
    if pedido.estado != Pedido.CONFIRMADO:
        raise ErrorComercial('Primero hay que confirmar la orden: una cotización no se factura.')
    if monto is None:
        monto = opciones(pedido)[que] if que in ('vendido', 'entregado') else por_facturar(pedido)
    monto = int(monto)
    if monto <= 0 and que == 'entregado' and facturacion.facturado(pedido) < pedido.base_clp:
        raise ErrorComercial(f'{pedido.numero} no tiene entregas por facturar todavía.')
    if monto <= 0:
        cfg = ConfiguracionComercial.de(pedido.organization)
        if cfg.facturar_ventas == ConfiguracionComercial.ENTREGADO and facturacion.facturado(pedido) < pedido.base_clp:
            raise ErrorComercial(f'{pedido.numero} no tiene entregas por facturar: la empresa factura lo entregado.')
        raise ErrorComercial(f'{pedido.numero} ya está facturada completa.')
    cfg = ConfiguracionComercial.de(pedido.organization)
    proveedor = PROVEEDORES.get(cfg.proveedor_dte) or FacturadorSimulado
    return proveedor().emitir(pedido, monto, usuario)

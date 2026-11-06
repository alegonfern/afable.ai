"""El facturador nativo como proveedor de emisión de Ventas (comercial/emision.py, clave 'sii').

Arma la factura desde la orden de venta con el detalle de lo que falta facturar por línea (lo
vendido o lo entregado, menos lo ya facturado en DTE anteriores de la misma orden). Si el monto
pedido no calza con ese detalle, va una línea con el monto. La orden de compra del cliente va como
referencia (801). Exenta (34) si todo lo de la orden es exento. También emite la guía de despacho
(52) de una entrega.
"""
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from apps.comercial.operaciones import ErrorComercial

from . import servicio
from .nucleo import ErrorDTE, documento as d

OC_CLIENTE = '801'


def _receptor(contacto):
    return d.Receptor(rut=contacto.rut, razon_social=contacto.razon_social, giro=contacto.giro,
                      direccion=contacto.direccion, comuna=contacto.comuna, ciudad=contacto.ciudad,
                      correo=contacto.email)


def _clave(codigo, nombre):
    return ('c', codigo) if codigo else ('n', (nombre or '')[:80])


def _nombre_linea(l):
    return (l.producto.nombre if l.producto_id else l.descripcion)[:80]


def ya_facturado(pedido):
    """Cantidad ya facturada de cada línea, leída de los DTE nativos amarrados a la orden: las
    facturas suman, las notas de crédito restan. {clave: Decimal}."""
    from .nucleo.xmlutil import leer
    # Una línea sin código (por ejemplo, la de una nota escrita a mano) se reconoce por su nombre.
    por_nombre = {_nombre_linea(l): _clave(l.producto.codigo if l.producto_id else '', _nombre_linea(l))
                  for l in pedido.lineas.select_related('producto')}
    total = {}
    for vinculo in pedido.facturas.select_related('documento'):
        emitido = getattr(vinculo.documento, 'emitido', None)
        if emitido is None or emitido.tipo == d.GUIA:
            continue
        signo = -1 if emitido.tipo == d.NOTA_CREDITO else 1
        for linea in d.desde_xml(leer(emitido.xml.encode('iso-8859-1'))).lineas:
            if linea.cantidad is None:
                continue  # notas que corrigen texto: no mueven cantidades
            k = _clave(linea.codigo, linea.nombre) if linea.codigo else por_nombre.get(
                (linea.nombre or '')[:80], _clave('', linea.nombre))
            total[k] = total.get(k, Decimal(0)) + signo * Decimal(linea.cantidad)
    return total


def _lineas_pendientes(pedido, base, todo_exento, facturado):
    """Las líneas de lo que falta facturar según `base` ('vendido' o 'entregado')."""
    lineas = []
    for l in pedido.lineas.all():
        if not l.cantidad or not l.precio_unitario:
            continue
        codigo = l.producto.codigo if l.producto_id else ''
        nombre = _nombre_linea(l)
        tope = l.cantidad if base == 'vendido' else l.cantidad_entregada
        pendiente = Decimal(tope) - facturado.get(_clave(codigo, nombre), Decimal(0))
        if pendiente <= 0:
            continue
        lineas.append(d.Linea(nombre=nombre,
                              descripcion=l.descripcion if l.producto_id and l.descripcion != l.producto.nombre else '',
                              cantidad=pendiente, precio=Decimal(l.precio_unitario) * pedido.tipo_cambio,
                              unidad=(l.unidad or '')[:4], codigo=codigo, descuento_pct=l.descuento_pct or None,
                              exento=l.exento and not todo_exento))
    return lineas


def documento_de(pedido, monto):
    """El nucleo.Documento (sin folio) de facturar `monto` (neto + exento, en pesos) de la orden."""
    lineas_pedido = list(pedido.lineas.all())
    todo_exento = bool(lineas_pedido) and all(l.exento for l in lineas_pedido)
    tipo = d.FACTURA_EXENTA if todo_exento else d.FACTURA
    facturado = ya_facturado(pedido)
    lineas = None
    for base in ('vendido', 'entregado'):
        candidatas = _lineas_pendientes(pedido, base, todo_exento, facturado)
        suma = sum(x.montos()[2] for x in candidatas)
        # Tolerancia de redondeo: el monto de la orden se redondea una vez y el DTE línea a línea.
        if candidatas and abs(suma - int(monto)) <= max(5, len(candidatas)):
            lineas = candidatas
            break
    if lineas is None:
        lineas = [d.Linea(nombre=f'Facturación parcial {pedido.numero}', cantidad=1, precio=int(monto))]
    hoy = timezone.localdate()
    plazo = pedido.plazo_dias
    return d.Documento(tipo=tipo, folio=None, fecha=hoy, emisor=servicio.emisor(pedido.organization),
                       receptor=_receptor(pedido.contacto), lineas=lineas, referencias=_referencias(pedido),
                       forma_pago=2 if plazo else 1, fecha_vencimiento=hoy + timedelta(days=plazo) if plazo else None)


def _referencias(pedido):
    if pedido.referencia:
        return [d.Referencia(OC_CLIENTE, pedido.referencia[:18], pedido.fecha)]
    return []


# ── Guía de despacho (52) de una entrega ──────────────────────────────────────────────────

# IndTraslado: 1 operación constituye venta; 7 guía de devolución.
TRASLADO_VENTA, TRASLADO_DEVOLUCION = 1, 7


def guia_disponible(org):
    from apps.comercial.models import ConfiguracionComercial
    return ConfiguracionComercial.de(org).proveedor_dte == FacturadorSII.clave


def guia_de(entrega):
    """El DocumentoEmitido de la guía de la entrega, si se emitió."""
    from .models import DocumentoEmitido
    if not entrega.folio_guia or not entrega.folio_guia.isdigit():
        return None
    return (DocumentoEmitido.objects.filter(organization=entrega.organization, tipo=d.GUIA,
                                            folio=int(entrega.folio_guia)).order_by('-creado_en').first())


def emitir_guia(entrega, usuario=None, transporte=None):
    """Emite la guía de despacho electrónica de una entrega de venta (o de una devolución del
    cliente) y deja su folio en la entrega."""
    from apps.comercial.models import VENTA, Entrega
    pedido = entrega.pedido
    if pedido.tipo != VENTA:
        raise ErrorComercial('La guía de despacho la emite quien despacha: solo se emite en ventas.')
    if entrega.estado != Entrega.HECHA:
        raise ErrorComercial('La entrega está anulada.')
    if entrega.folio_guia:
        raise ErrorComercial(f'Esa entrega ya tiene la guía N° {entrega.folio_guia}.')
    if not guia_disponible(entrega.organization):
        raise ErrorComercial('Para emitir guías, active el facturador electrónico de Afable en Ajustes.')
    if not pedido.contacto.rut:
        raise ErrorComercial(f'{pedido.contacto.razon_social} no tiene RUT en su ficha: agréguelo para emitirle la guía.')
    lineas = []
    for le in entrega.lineas.select_related('linea__producto'):
        l = le.linea
        if not le.cantidad:
            continue
        lineas.append(d.Linea(nombre=_nombre_linea(l), codigo=l.producto.codigo if l.producto_id else '',
                              cantidad=abs(Decimal(le.cantidad)), unidad=(l.unidad or '')[:4],
                              precio=Decimal(l.precio_unitario) * pedido.tipo_cambio if l.precio_unitario else None,
                              descuento_pct=l.descuento_pct or None, exento=l.exento,
                              monto=None if l.precio_unitario else 0))
    if not lineas:
        raise ErrorComercial('La entrega no tiene líneas con cantidad.')
    t = transporte or {}
    tr = d.Transporte(patente=t.get('patente') or '', rut_transportista=t.get('rut_transportista') or '',
                      direccion_destino=t.get('direccion_destino') or pedido.contacto.direccion or '',
                      comuna_destino=t.get('comuna_destino') or pedido.contacto.comuna or '',
                      ciudad_destino=t.get('ciudad_destino') or pedido.contacto.ciudad or '')
    doc = d.Documento(tipo=d.GUIA, folio=None, fecha=timezone.localdate(), emisor=servicio.emisor(pedido.organization),
                      receptor=_receptor(pedido.contacto), lineas=lineas, referencias=_referencias(pedido),
                      indicador_traslado=TRASLADO_DEVOLUCION if entrega.tipo == Entrega.DEVOLUCION else TRASLADO_VENTA,
                      tipo_despacho=2, transporte=tr)
    try:
        emitido = servicio.emitir(pedido.organization, doc, usuario=usuario)
    except ErrorDTE as e:
        raise ErrorComercial(str(e))
    entrega.folio_guia = str(emitido.folio)
    entrega.save(update_fields=['folio_guia'])
    return emitido


class FacturadorSII:
    clave = 'sii'

    def emitir(self, pedido, monto, usuario=None):
        from apps.comercial.emision import registrar
        if not pedido.contacto.rut:
            raise ErrorComercial(f'{pedido.contacto.razon_social} no tiene RUT en su ficha: agréguelo para facturarle.')
        try:
            emitido = servicio.emitir(pedido.organization, documento_de(pedido, monto), usuario=usuario)
        except ErrorDTE as e:
            raise ErrorComercial(str(e))
        doc = registrar(pedido, emitido.tipo, emitido.folio, neto=emitido.monto_neto, exento=emitido.monto_exento,
                        iva=emitido.monto_iva, fecha=emitido.fecha, usuario=usuario)
        emitido.documento_tributario = doc
        emitido.save(update_fields=['documento_tributario'])
        return doc


def registrar_nota(nota, original, usuario=None):
    """La nota en el Libro de Ventas, amarrada a las mismas órdenes que el documento que corrige
    (una nota de crédito resta de lo facturado; una de débito suma)."""
    from apps.comercial import facturacion
    from apps.finanzas import constantes as fc
    from apps.finanzas.models import Contraparte, DocumentoTributario
    org = nota.organization
    dt_original = original.documento_tributario
    cp = dt_original.contraparte if dt_original else None
    if cp is None:
        cp, _ = Contraparte.objects.get_or_create(organization=org, libro=fc.LIBRO_VENTAS, rut=nota.receptor_rut,
                                                  defaults={'razon_social': nota.receptor_razon_social})
    doc = DocumentoTributario.objects.create(
        organization=org, libro=fc.LIBRO_VENTAS, tipo_documento=str(nota.tipo), folio=str(nota.folio),
        rut=nota.receptor_rut, razon_social=nota.receptor_razon_social, fecha=nota.fecha,
        monto_neto=nota.monto_neto, monto_exento=nota.monto_exento, monto_iva=nota.monto_iva,
        monto_total=nota.monto_total, contraparte=cp, categoria=dt_original.categoria if dt_original else None,
        estado=dt_original.estado if dt_original else DocumentoTributario.POR_REVISAR, emitido_en_afable=True)
    nota.documento_tributario = doc
    nota.save(update_fields=['documento_tributario'])
    if dt_original and nota.monto_neto + nota.monto_exento:
        for vinculo in dt_original.pedidos.select_related('pedido'):
            try:
                facturacion.vincular(vinculo.pedido, doc, usuario=usuario)
            except ErrorComercial:
                pass  # la nota queda en el libro aunque no calce con la orden; se amarra a mano
    return doc

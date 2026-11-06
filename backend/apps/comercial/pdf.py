"""El PDF de una cotización u orden (de venta o de compra), para descargar o mandar por correo."""

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .facturacion import etapa
from .models import CLP, VENTA
from .operaciones import formato

TINTA = colors.HexColor('#1f2328')
SUAVE = colors.HexColor('#6b7280')
LINEA = colors.HexColor('#e5e7eb')


def logo_de(org, alto=16 * mm, ancho=50 * mm):
    """El logo de la empresa (Ajustes › Datos y logo, el mismo de la barra lateral) para la cabecera
    de sus documentos: cotizaciones, órdenes y facturas. Cabe en `ancho` x `alto` sin deformarse.
    None si no tiene o no se puede leer: el documento sale igual, solo con el nombre."""
    if not getattr(org, 'logo', None):
        return None
    try:
        from PIL import Image as Imagen
        with org.logo.open('rb') as f:
            datos = BytesIO(f.read())
        with Imagen.open(datos) as im:
            w, h = im.size
        escala = min(ancho / w, alto / h)
        datos.seek(0)
        logo = Image(datos, width=w * escala, height=h * escala)
        logo.hAlign = 'LEFT'
        return logo
    except Exception:
        return None


def titulo_de(pedido):
    venta = pedido.tipo == VENTA
    if pedido.es_orden:
        return 'Orden de venta' if venta else 'Orden de compra'
    return 'Cotización' if venta else 'Solicitud de cotización'


def _cant(d):
    texto = f'{d.normalize():f}'
    return texto.replace('.', ',')


def generar(pedido):
    org = pedido.organization
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f'{titulo_de(pedido)} {pedido.numero}', author=org.name)
    base = getSampleStyleSheet()['Normal']
    normal = ParagraphStyle('n', parent=base, fontName='Helvetica', fontSize=9, leading=12, textColor=TINTA)
    suave = ParagraphStyle('s', parent=normal, textColor=SUAVE, fontSize=8.5)
    grande = ParagraphStyle('g', parent=normal, fontName='Helvetica-Bold', fontSize=16, leading=20)
    derecha = ParagraphStyle('d', parent=normal, alignment=TA_RIGHT)
    negrita = ParagraphStyle('b', parent=normal, fontName='Helvetica-Bold')

    def p(texto, estilo=normal):
        return Paragraph(str(texto).replace('&', '&amp;').replace('<', '&lt;').replace('\n', '<br/>'), estilo)

    contacto = pedido.contacto
    venta = pedido.tipo == VENTA
    logo = logo_de(org)
    emisor = ([logo, Spacer(1, 2 * mm)] if logo else []) + [p(org.name, negrita)] + ([p(f'RUT {org.rut}', suave)] if org.rut else [])
    cabecera = Table([[emisor, [p(titulo_de(pedido), grande), p(f'N° {pedido.numero}', derecha)]]],
                     colWidths=[95 * mm, 85 * mm])
    cabecera.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('ALIGN', (1, 0), (1, 0), 'RIGHT')]))

    datos_contacto = [p('CLIENTE' if venta else 'PROVEEDOR', suave), p(contacto.razon_social, negrita)]
    for linea in (f'RUT {contacto.rut}' if contacto.rut else '', contacto.giro,
                  ', '.join(x for x in (contacto.direccion, contacto.comuna, contacto.ciudad) if x),
                  contacto.persona_contacto, contacto.email, contacto.telefono):
        if linea:
            datos_contacto.append(p(linea))
    fechas = [p('Fecha', suave), p(pedido.fecha.strftime('%d-%m-%Y'))]
    if pedido.valida_hasta and not pedido.es_orden:
        fechas += [p('Válida hasta', suave), p(pedido.valida_hasta.strftime('%d-%m-%Y'))]
    if pedido.fecha_compromiso:
        fechas += [p('Entrega' if venta else 'Llegada esperada', suave), p(pedido.fecha_compromiso.strftime('%d-%m-%Y'))]
    if pedido.plazo_dias is not None:
        fechas += [p('Plazo de pago', suave), p(f'{pedido.plazo_dias} días')]
    if pedido.referencia:
        fechas += [p('Su referencia' if venta else 'Cotización del proveedor', suave), p(pedido.referencia)]
    if pedido.moneda != CLP:
        fechas += [p('Moneda', suave), p(f'{pedido.get_moneda_display()} (1 = {formato(pedido.tipo_cambio, CLP)})')]
    bloque = Table([[datos_contacto, fechas]], colWidths=[110 * mm, 70 * mm])
    bloque.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))

    filas = [[p('Descripción', suave), p('Cantidad', suave), p('Precio', suave), p('Desc.', suave), p('Total', suave)]]
    for l in pedido.lineas.all():
        filas.append([
            p(l.descripcion + (' (exento)' if l.exento else '')),
            p(f'{_cant(l.cantidad)} {l.unidad}', derecha),
            p(formato(l.precio_unitario, pedido.moneda), derecha),
            p(f'{_cant(l.descuento_pct)}%' if l.descuento_pct else '', derecha),
            p(formato(l.subtotal, pedido.moneda), derecha),
        ])
    tabla = Table(filas, colWidths=[78 * mm, 24 * mm, 28 * mm, 16 * mm, 34 * mm], repeatRows=1)
    tabla.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, 0), 0.8, TINTA), ('LINEBELOW', (0, 1), (-1, -1), 0.4, LINEA),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))

    totales = [[p('Neto', suave), p(formato(pedido.neto, pedido.moneda), derecha)]]
    if pedido.exento:
        totales.append([p('Exento', suave), p(formato(pedido.exento, pedido.moneda), derecha)])
    totales += [[p('IVA 19%', suave), p(formato(pedido.iva, pedido.moneda), derecha)],
                [p('Total', negrita), p(formato(pedido.total, pedido.moneda), ParagraphStyle('t', parent=derecha, fontName='Helvetica-Bold'))]]
    if pedido.moneda != CLP:
        totales.append([p('Total en pesos (referencial)', suave), p(formato(pedido.a_pesos(pedido.total), CLP), derecha)])
    caja = Table(totales, colWidths=[45 * mm, 35 * mm], hAlign='RIGHT')
    caja.setStyle(TableStyle([('LINEABOVE', (0, -1 if pedido.moneda == CLP else -2), (-1, -1 if pedido.moneda == CLP else -2), 0.8, TINTA)]))

    historia = [cabecera, Spacer(1, 8 * mm), bloque, Spacer(1, 8 * mm), tabla, Spacer(1, 5 * mm), caja]
    if pedido.condiciones:
        historia += [Spacer(1, 8 * mm), p('Condiciones', suave), p(pedido.condiciones)]
    if pedido.notas:
        historia += [Spacer(1, 4 * mm), p('Notas', suave), p(pedido.notas)]
    historia += [Spacer(1, 10 * mm), p(f'{etapa(pedido)} · generado con Afable', suave)]
    doc.build(historia)
    return buf.getvalue()

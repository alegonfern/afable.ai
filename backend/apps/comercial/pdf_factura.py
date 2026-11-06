"""El PDF de una factura electrónica emitida desde Afable (25-10-2026).

Con el formato de una factura chilena: el recuadro rojo con el RUT del emisor, "FACTURA
ELECTRÓNICA" y el folio; los datos del receptor; el detalle; los totales y el timbre. Como la emite
el facturador simulado (emision.py), es lo único que dice que es un ENTORNO DE PRUEBA: una franja
arriba y una marca de agua cruzada. Todo lo demás es como sería con un proveedor real.
"""
import hashlib
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Flowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .operaciones import formato
from .pdf import LINEA, SUAVE, TINTA, _cant

ROJO = colors.HexColor('#c8102e')
MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre',
         'octubre', 'noviembre', 'diciembre']


def _rut(rut):
    """76123456-7 → 76.123.456-7"""
    cuerpo, _, dv = str(rut or '').replace('.', '').partition('-')
    if not cuerpo.isdigit():
        return rut or ''
    return f'{int(cuerpo):,}'.replace(',', '.') + (f'-{dv}' if dv else '')


def _pesos(n):
    return f'${round(n):,}'.replace(',', '.')


class Timbre(Flowable):
    """El timbre electrónico: un bloque de barras al estilo del PDF417, sacado de los datos del
    documento (siempre el mismo dibujo para la misma factura)."""

    def __init__(self, semilla, ancho=62 * mm, alto=22 * mm):
        super().__init__()
        self.semilla, self.width, self.height = semilla, ancho, alto

    def draw(self):
        c = self.canv
        bits = ''.join(f'{b:08b}' for b in hashlib.sha512(self.semilla.encode()).digest() * 6)
        filas, cols = 18, 80
        alto_fila, ancho_col = self.height / filas, self.width / cols
        c.setFillColor(colors.black)
        for f in range(filas):
            for k in range(cols):
                if k < 3 or k >= cols - 3 or bits[(f * cols + k) % len(bits)] == '1':
                    c.rect(k * ancho_col, f * alto_fila, ancho_col, alto_fila, stroke=0, fill=1)


def _marca_de_agua(canvas, doc):
    canvas.saveState()
    ancho, alto = LETTER
    canvas.setFillColor(ROJO)
    canvas.rect(0, alto - 9 * mm, ancho, 9 * mm, stroke=0, fill=1)
    canvas.setFillColor(colors.white)
    canvas.setFont('Helvetica-Bold', 9)
    canvas.drawCentredString(ancho / 2, alto - 6 * mm, 'ENTORNO DE PRUEBA · DOCUMENTO SIN VALIDEZ TRIBUTARIA')
    canvas.translate(ancho / 2, alto / 2)
    canvas.rotate(35)
    canvas.setFillColor(colors.Color(0.78, 0.06, 0.18, alpha=0.08))
    canvas.setFont('Helvetica-Bold', 54)
    canvas.drawCentredString(0, 0, 'ENTORNO DE PRUEBA')
    canvas.restoreState()


def generar(documento):
    org = documento.organization
    vinculo = documento.pedidos.select_related('pedido__contacto').first()
    pedido = vinculo.pedido if vinculo else None
    cliente = pedido.contacto if pedido else None

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER, leftMargin=16 * mm, rightMargin=16 * mm,
                            topMargin=18 * mm, bottomMargin=14 * mm,
                            title=f'Factura electrónica N° {documento.folio}', author=org.name)
    base = getSampleStyleSheet()['Normal']
    normal = ParagraphStyle('n', parent=base, fontName='Helvetica', fontSize=8.5, leading=11.5, textColor=TINTA)
    suave = ParagraphStyle('s', parent=normal, textColor=SUAVE, fontSize=8)
    negrita = ParagraphStyle('b', parent=normal, fontName='Helvetica-Bold')
    emisor_st = ParagraphStyle('e', parent=normal, fontName='Helvetica-Bold', fontSize=13, leading=16)
    derecha = ParagraphStyle('d', parent=normal, alignment=TA_RIGHT)
    rojo = ParagraphStyle('r', parent=normal, fontName='Helvetica-Bold', fontSize=11.5, leading=16,
                          textColor=ROJO, alignment=TA_CENTER)
    centro = ParagraphStyle('c', parent=suave, alignment=TA_CENTER)

    def p(texto, estilo=normal):
        return Paragraph(str(texto).replace('&', '&amp;').replace('<', '&lt;'), estilo)

    # Emisor (con el logo de la empresa) y el recuadro rojo del SII.
    from .models import ConfiguracionComercial
    from .pdf import logo_de
    e = ConfiguracionComercial.de(org).emisor
    logo = logo_de(org)
    emisor = ([logo, Spacer(1, 2 * mm)] if logo else []) + [p(e['razon_social'], emisor_st)]
    for linea in (e['giro'], e['direccion'], ', '.join(x for x in (e['comuna'], e['ciudad']) if x)):
        if linea:
            emisor.append(p(linea, suave))
    recuadro = Table([[p(f'R.U.T.: {_rut(org.rut) or "—"}', rojo)], [p('FACTURA ELECTRÓNICA', rojo)],
                      [p(f'N° {documento.folio}', rojo)]], colWidths=[66 * mm])
    recuadro.setStyle(TableStyle([('BOX', (0, 0), (-1, -1), 1.6, ROJO), ('TOPPADDING', (0, 0), (-1, -1), 3),
                                  ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]))
    cabecera = Table([[emisor, [recuadro, Spacer(1, 2 * mm), p(f'S.I.I. - {(e["ciudad"] or "Santiago").upper()}', centro)]]],
                     colWidths=[112 * mm, 72 * mm])
    cabecera.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('ALIGN', (1, 0), (1, 0), 'CENTER')]))

    # Receptor.
    f = documento.fecha
    def fila(etiqueta, valor):
        return [p(etiqueta, suave), p(valor or '—')]
    receptor = [
        fila('Señor(es)', documento.razon_social), fila('R.U.T.', _rut(documento.rut)),
        fila('Giro', cliente.giro if cliente else ''),
        fila('Dirección', ', '.join(x for x in ((cliente.direccion, cliente.comuna, cliente.ciudad) if cliente else ()) if x)),
    ]
    fechas = [fila('Fecha de emisión', f'{f.day} de {MESES[f.month - 1]} de {f.year}'),
              fila('Vencimiento', documento.fecha_vencimiento.strftime('%d-%m-%Y') if documento.fecha_vencimiento else ''),
              fila('Referencia', pedido.numero if pedido else '')]
    datos = Table([[Table(receptor, colWidths=[22 * mm, 88 * mm]), Table(fechas, colWidths=[28 * mm, 44 * mm])]],
                  colWidths=[112 * mm, 72 * mm])
    datos.setStyle(TableStyle([('BOX', (0, 0), (-1, -1), 0.6, TINTA), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                               ('TOPPADDING', (0, 0), (-1, -1), 4)]))

    # Detalle: las líneas del pedido si la factura lo cubre entero; si es parcial, una línea.
    filas = [[p('Descripción', suave), p('Cantidad', suave), p('Precio unitario', suave), p('Valor', suave)]]
    lineas = list(pedido.lineas.all()) if pedido else []
    if lineas and pedido.moneda == 'CLP' and abs(pedido.base_clp - documento.monto_neto) <= 1:
        for l in lineas:
            filas.append([p(l.descripcion), p(f'{_cant(l.cantidad)} {l.unidad}', derecha),
                          p(formato(l.precio_unitario, 'CLP'), derecha), p(formato(l.subtotal, 'CLP'), derecha)])
    else:
        filas.append([p(f'Facturación de {pedido.numero}' if pedido else 'Servicios'), p('1', derecha),
                      p(_pesos(documento.monto_neto), derecha), p(_pesos(documento.monto_neto), derecha)])
    detalle = Table(filas, colWidths=[100 * mm, 24 * mm, 30 * mm, 30 * mm], repeatRows=1)
    detalle.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, 0), 0.8, TINTA), ('LINEBELOW', (0, 1), (-1, -1), 0.4, LINEA),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))

    totales = Table([[p('Monto neto', suave), p(_pesos(documento.monto_neto), derecha)],
                     [p('I.V.A. 19%', suave), p(_pesos(documento.monto_iva), derecha)],
                     [p('Total', negrita), p(_pesos(documento.monto_total), ParagraphStyle('t', parent=derecha, fontName='Helvetica-Bold'))]],
                    colWidths=[34 * mm, 34 * mm])
    totales.setStyle(TableStyle([('BOX', (0, 0), (-1, -1), 0.6, TINTA), ('LINEABOVE', (0, -1), (-1, -1), 0.6, TINTA)]))

    semilla = f'{org.rut}|33|{documento.folio}|{documento.fecha}|{documento.rut}|{documento.monto_total}'
    timbre = [Timbre(semilla), Spacer(1, 1.5 * mm), p('Timbre Electrónico SII', centro),
              p(f'Res. 0 de {documento.fecha.year} · Verifique documento: www.sii.cl', centro)]
    pie = Table([[timbre, totales]], colWidths=[112 * mm, 72 * mm])
    pie.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('ALIGN', (1, 0), (1, 0), 'RIGHT')]))

    doc.build([cabecera, Spacer(1, 6 * mm), datos, Spacer(1, 6 * mm), detalle, Spacer(1, 8 * mm), pie],
              onFirstPage=_marca_de_agua, onLaterPages=_marca_de_agua)
    return buf.getvalue()

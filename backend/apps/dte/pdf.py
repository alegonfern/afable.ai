"""El PDF de un DTE emitido por el facturador nativo (ESPEC_SII.md §5.3 y §9.6).

Sale del XML firmado que se guardó (no de la orden): lo impreso dice exactamente lo que recibió el
SII. Sigue el manual de muestras impresas: recuadro rojo arriba a la derecha con el RUT, el nombre
del documento y el folio; "S.I.I. - <oficina>" bajo el recuadro; el timbre PDF417 abajo a la
izquierda con sus leyendas; y en la copia cedible, el acuse de recibo de la Ley 19.983.
"""
import re
from io import BytesIO

import pdf417gen
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Flowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.comercial.pdf import LINEA, SUAVE, TINTA
from apps.comercial.pdf_factura import MESES, ROJO, _rut

from .nucleo import documento as d
from .nucleo.xmlutil import SII, leer
from .sii import CERTIFICACION

NOMBRES = {d.FACTURA: 'FACTURA ELECTRÓNICA', d.FACTURA_EXENTA: 'FACTURA NO AFECTA O EXENTA ELECTRÓNICA',
           d.GUIA: 'GUÍA DE DESPACHO ELECTRÓNICA', d.NOTA_DEBITO: 'NOTA DE DÉBITO ELECTRÓNICA',
           d.NOTA_CREDITO: 'NOTA DE CRÉDITO ELECTRÓNICA'}
# Los documentos de referencia, en palabras (el manual pide el tipo escrito, no el código).
REFERENCIAS = {'33': 'Factura electrónica', '34': 'Factura exenta electrónica', '52': 'Guía de despacho electrónica',
               '56': 'Nota de débito electrónica', '61': 'Nota de crédito electrónica', '801': 'Orden de compra',
               '802': 'Nota de pedido', '803': 'Contrato', 'SET': 'Set de pruebas', '30': 'Factura',
               '39': 'Boleta electrónica', '46': 'Factura de compra electrónica'}
COD_REF = {'1': 'Anula documento', '2': 'Corrige texto', '3': 'Corrige montos'}
TRASLADOS = {'1': 'Operación constituye venta', '2': 'Ventas por efectuar', '3': 'Consignaciones',
             '4': 'Entrega gratuita', '5': 'Traslados internos', '6': 'Otros traslados no venta',
             '7': 'Guía de devolución', '8': 'Traslado para exportación', '9': 'Venta para exportación'}
FORMAS_PAGO = {'1': 'Contado', '2': 'Crédito', '3': 'Sin costo'}
ACUSE = ('El acuse de recibo que se declara en este acto, de acuerdo a lo dispuesto en la letra b) del Art. 4°, '
         'y la letra c) del Art. 5° de la Ley 19.983, acredita que la entrega de mercaderías o servicio(s) '
         'prestado(s) ha(n) sido recibido(s).')


def admite_cedible(tipo, indicador_traslado=None):
    """Llevan copia cedible las facturas y la guía que es venta; no las notas ni la guía de traslado."""
    if tipo in (d.FACTURA, d.FACTURA_EXENTA):
        return True
    return tipo == d.GUIA and str(indicador_traslado or '') in ('1', '2', '3', '9')


def _t(nodo, ruta):
    return (nodo.findtext(ruta, namespaces={'s': SII}) or '').strip()


def _pesos(n):
    return f'${int(n or 0):,}'.replace(',', '.')


def _num(texto):
    """'4500.5' -> '4.500,5' (formato chileno, sin ceros de más)."""
    if not texto:
        return ''
    entero, _, dec = texto.partition('.')
    entero = f'{int(entero):,}'.replace(',', '.') if entero.lstrip('-').isdigit() else entero
    return entero + (',' + dec if dec else '')


def ted_plano(raiz):
    """El TED sin espacios entre tags ni namespaces, en ISO-8859-1: lo que va en el PDF417."""
    from lxml import etree
    ted = raiz.find('.//s:TED', namespaces={'s': SII})
    s = etree.tostring(ted, encoding='unicode', with_tail=False)
    s = re.sub(r'\s+xmlns(:\w+)?="[^"]*"', '', s)
    return re.sub(r'>\s+<', '><', s).encode('iso-8859-1')


class Timbre(Flowable):
    """El PDF417 del TED (nivel de seguridad 5, proporción 3:1) como imagen PNG. Las columnas se
    eligen para que el timbre quede dentro de lo que pide el manual: 2 a 4 cm de alto, 9 cm de ancho
    como máximo."""

    def __init__(self, datos, ancho=80 * mm, alto_maximo=38 * mm):
        super().__init__()
        for columnas in range(10, 31):
            codigos = pdf417gen.encode(datos, columns=columnas, security_level=5)
            self.imagen = pdf417gen.render_image(codigos, scale=4, ratio=3, padding=8)
            w, h = self.imagen.size
            if ancho * h / w <= alto_maximo:
                break
        self.width, self.height = ancho, max(ancho * h / w, 20 * mm)

    def draw(self):
        buf = BytesIO()
        self.imagen.save(buf, format='PNG')
        buf.seek(0)
        self.canv.drawImage(ImageReader(buf), 0, 0, self.width, self.height)


def generar(emitido, cedible=False, oficina=None):
    """El PDF del DocumentoEmitido. `oficina` es la del SII que va bajo el recuadro ("S.I.I. -
    SANTIAGO CENTRO"); si no se indica, la de la configuración de la empresa (oficina_sii) y, si
    tampoco está, la comuna del emisor."""
    from .models import ConfiguracionDTE
    raiz = leer(emitido.xml.encode('iso-8859-1'))
    doc = raiz.find('.//s:Documento', namespaces={'s': SII})
    enc = doc.find('s:Encabezado', namespaces={'s': SII})
    tipo, folio = int(_t(enc, 's:IdDoc/s:TipoDTE')), _t(enc, 's:IdDoc/s:Folio')
    traslado = _t(enc, 's:IdDoc/s:IndTraslado')
    cedible = cedible and admite_cedible(tipo, traslado)
    cfg = ConfiguracionDTE.de(emitido.organization)
    fecha_res, numero_res = cfg.resolucion(emitido.ambiente)

    buf = BytesIO()
    pdf = SimpleDocTemplate(buf, pagesize=LETTER, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=14 * mm,
                            bottomMargin=12 * mm, title=f'{NOMBRES.get(tipo, tipo)} N° {folio}',
                            author=_t(enc, 's:Emisor/s:RznSoc'))
    base = getSampleStyleSheet()['Normal']
    normal = ParagraphStyle('n', parent=base, fontName='Helvetica', fontSize=8.5, leading=11, textColor=TINTA)
    suave = ParagraphStyle('s', parent=normal, textColor=SUAVE, fontSize=8)
    negrita = ParagraphStyle('b', parent=normal, fontName='Helvetica-Bold')
    emisor_st = ParagraphStyle('e', parent=normal, fontName='Helvetica-Bold', fontSize=13, leading=16)
    derecha = ParagraphStyle('d', parent=normal, alignment=TA_RIGHT)
    derecha_b = ParagraphStyle('db', parent=derecha, fontName='Helvetica-Bold')
    rojo = ParagraphStyle('r', parent=normal, fontName='Helvetica-Bold', fontSize=11, leading=15,
                          textColor=ROJO, alignment=TA_CENTER)
    centro = ParagraphStyle('c', parent=normal, fontSize=7, leading=9, alignment=TA_CENTER)
    centro_b = ParagraphStyle('cb', parent=centro, fontName='Helvetica-Bold', fontSize=8, textColor=ROJO)
    chico = ParagraphStyle('ch', parent=normal, fontSize=7, leading=9)

    def p(texto, estilo=normal):
        return Paragraph(str(texto).replace('&', '&amp;').replace('<', '&lt;'), estilo)

    # Emisor (con el logo que la empresa eligió en Ajustes) y recuadro del SII.
    from apps.comercial.pdf import logo_de
    em = enc.find('s:Emisor', namespaces={'s': SII})
    logo = logo_de(emitido.organization)
    emisor = ([logo, Spacer(1, 2 * mm)] if logo else []) + [p(_t(em, 's:RznSoc'), emisor_st), p(_t(em, 's:GiroEmis'), suave)]
    casa = ', '.join(x for x in (_t(em, 's:DirOrigen'), _t(em, 's:CmnaOrigen'), _t(em, 's:CiudadOrigen')) if x)
    if casa:
        emisor.append(p(f'Casa matriz: {casa}', suave))
    if _t(em, 's:Sucursal'):
        emisor.append(p(f'Sucursal: {_t(em, "s:Sucursal")}', suave))
    contacto = ' · '.join(x for x in (_t(em, 's:Telefono'), _t(em, 's:CorreoEmisor')) if x)
    if contacto:
        emisor.append(p(contacto, suave))
    recuadro = Table([[p(f'R.U.T.: {_rut(_t(em, "s:RUTEmisor"))}', rojo)], [p(NOMBRES.get(tipo, str(tipo)), rojo)],
                      [p(f'N° {folio}', rojo)]], colWidths=[70 * mm])
    recuadro.setStyle(TableStyle([('BOX', (0, 0), (-1, -1), 2, ROJO), ('TOPPADDING', (0, 0), (-1, -1), 3),
                                  ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]))
    oficina = (oficina or cfg.oficina_sii or _t(em, 's:CmnaOrigen') or 'Santiago').upper()
    cabecera = Table([[emisor, [recuadro, Spacer(1, 1.5 * mm), p(f'S.I.I. - {oficina}', centro_b)]]],
                     colWidths=[108 * mm, 76 * mm])
    cabecera.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('ALIGN', (1, 0), (1, 0), 'CENTER'),
                                  ('LEFTPADDING', (0, 0), (0, 0), 0)]))

    # Receptor y fechas.
    rc = enc.find('s:Receptor', namespaces={'s': SII})
    iddoc = enc.find('s:IdDoc', namespaces={'s': SII})
    fe = _t(iddoc, 's:FchEmis')
    anio, mes, dia = (int(x) for x in fe.split('-'))

    def fila(etiqueta, valor):
        return [p(etiqueta, suave), p(valor or '—')]

    receptor = [fila('Señor(es)', _t(rc, 's:RznSocRecep')), fila('R.U.T.', _rut(_t(rc, 's:RUTRecep'))),
                fila('Giro', _t(rc, 's:GiroRecep')),
                fila('Dirección', ', '.join(x for x in (_t(rc, 's:DirRecep'), _t(rc, 's:CmnaRecep'),
                                                       _t(rc, 's:CiudadRecep')) if x))]
    if _t(rc, 's:Contacto'):
        receptor.append(fila('Contacto', _t(rc, 's:Contacto')))
    fechas = [fila('Fecha de emisión', f'{dia} de {MESES[mes - 1]} de {anio}')]
    if _t(iddoc, 's:FchVenc'):
        fechas.append(fila('Vencimiento', '-'.join(reversed(_t(iddoc, 's:FchVenc').split('-')))))
    if _t(iddoc, 's:FmaPago'):
        fechas.append(fila('Forma de pago', FORMAS_PAGO.get(_t(iddoc, 's:FmaPago'), '')))
    if traslado:
        fechas.append(fila('Tipo de traslado', TRASLADOS.get(traslado, traslado)))
    datos = Table([[Table(receptor, colWidths=[20 * mm, 86 * mm]), Table(fechas, colWidths=[26 * mm, 48 * mm])]],
                  colWidths=[108 * mm, 76 * mm])
    datos.setStyle(TableStyle([('BOX', (0, 0), (-1, -1), 0.6, TINTA), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                               ('TOPPADDING', (0, 0), (-1, -1), 4)]))
    cuerpo = [cabecera, Spacer(1, 5 * mm), datos]

    # Transporte (guías).
    tr = enc.find('s:Transporte', namespaces={'s': SII})
    if tr is not None:
        partes = [f'Patente: {_t(tr, "s:Patente")}' if _t(tr, 's:Patente') else '',
                  f'Transportista: {_rut(_t(tr, "s:RUTTrans"))}' if _t(tr, 's:RUTTrans') else '',
                  f'Chofer: {_t(tr, "s:Chofer/s:NombreChofer")} ({_rut(_t(tr, "s:Chofer/s:RUTChofer"))})'
                  if _t(tr, 's:Chofer/s:RUTChofer') else '',
                  'Destino: ' + ', '.join(x for x in (_t(tr, 's:DirDest'), _t(tr, 's:CmnaDest'), _t(tr, 's:CiudadDest')) if x)
                  if _t(tr, 's:DirDest') or _t(tr, 's:CmnaDest') else '']
        cuerpo += [Spacer(1, 2 * mm), p(' · '.join(x for x in partes if x), suave)]

    # Referencias.
    refs = doc.findall('s:Referencia', namespaces={'s': SII})
    if refs:
        filas = [[p('Referencia', suave), p('Folio', suave), p('Fecha', suave), p('Motivo', suave)]]
        for r in refs:
            motivo = ' · '.join(x for x in (COD_REF.get(_t(r, 's:CodRef'), ''), _t(r, 's:RazonRef')) if x)
            filas.append([p(REFERENCIAS.get(_t(r, 's:TpoDocRef'), f'Documento {_t(r, "s:TpoDocRef")}')),
                          p(_t(r, 's:FolioRef')), p('-'.join(reversed(_t(r, 's:FchRef').split('-')))), p(motivo)])
        tabla = Table(filas, colWidths=[46 * mm, 26 * mm, 24 * mm, 88 * mm])
        tabla.setStyle(TableStyle([('LINEBELOW', (0, 0), (-1, 0), 0.6, TINTA), ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
        cuerpo += [Spacer(1, 4 * mm), tabla]

    # Detalle: el descuento va en monto (el % solo como dato adicional).
    filas = [[p('Código', suave), p('Descripción', suave), p('Cantidad', suave), p('Precio unit.', suave),
              p('Dscto.', suave), p('Valor', suave)]]
    for det in doc.findall('s:Detalle', namespaces={'s': SII}):
        nombre = [p(_t(det, 's:NmbItem'))]
        if _t(det, 's:DscItem'):
            nombre.append(p(_t(det, 's:DscItem'), suave))
        if _t(det, 's:IndExe') == '1':
            nombre.append(p('Exento', suave))
        dscto = _t(det, 's:DescuentoMonto')
        if dscto and _t(det, 's:DescuentoPct'):
            dscto_txt = f'{_pesos(dscto)} ({_num(_t(det, "s:DescuentoPct"))}%)'
        else:
            dscto_txt = _pesos(dscto) if dscto else ''
        cantidad = ' '.join(x for x in (_num(_t(det, 's:QtyItem')), _t(det, 's:UnmdItem')) if x)
        filas.append([p(_t(det, 's:CdgItem/s:VlrCodigo'), suave), nombre, p(cantidad, derecha),
                      p('$' + _num(_t(det, 's:PrcItem')) if _t(det, 's:PrcItem') else '', derecha),
                      p(dscto_txt, derecha), p(_pesos(_t(det, 's:MontoItem')), derecha)])
    detalle = Table(filas, colWidths=[18 * mm, 76 * mm, 20 * mm, 24 * mm, 20 * mm, 26 * mm], repeatRows=1)
    detalle.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, 0), 0.8, TINTA), ('LINEBELOW', (0, 1), (-1, -1), 0.4, LINEA),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    cuerpo += [Spacer(1, 5 * mm), detalle]

    # Descuentos y recargos globales.
    for dr in doc.findall('s:DscRcgGlobal', namespaces={'s': SII}):
        valor = _t(dr, 's:ValorDR')
        texto = ('Descuento' if _t(dr, 's:TpoMov') == 'D' else 'Recargo') + ' global'
        if _t(dr, 's:GlosaDR'):
            texto += f' ({_t(dr, "s:GlosaDR")})'
        texto += f': {_num(valor)}%' if _t(dr, 's:TpoValor') == '%' else f': {_pesos(valor)}'
        cuerpo += [Spacer(1, 1 * mm), p(texto, suave)]

    # Totales: en la exenta, solo el monto exento y el total.
    tot = enc.find('s:Totales', namespaces={'s': SII})
    filas = []
    if tipo != d.FACTURA_EXENTA and _t(tot, 's:MntNeto'):
        filas.append([p('Monto neto', suave), p(_pesos(_t(tot, 's:MntNeto')), derecha)])
    if _t(tot, 's:MntExe'):
        filas.append([p('Monto exento', suave), p(_pesos(_t(tot, 's:MntExe')), derecha)])
    if tipo != d.FACTURA_EXENTA and _t(tot, 's:IVA'):
        filas.append([p(f'I.V.A. {_num(_t(tot, "s:TasaIVA"))}%', suave), p(_pesos(_t(tot, 's:IVA')), derecha)])
    filas.append([p('Total', negrita), p(_pesos(_t(tot, 's:MntTotal')), derecha_b)])
    totales = Table(filas, colWidths=[36 * mm, 36 * mm])
    totales.setStyle(TableStyle([('BOX', (0, 0), (-1, -1), 0.6, TINTA), ('LINEABOVE', (0, -1), (-1, -1), 0.6, TINTA)]))

    # Timbre: abajo a la izquierda, con sus leyendas.
    numero = 0 if emitido.ambiente == CERTIFICACION else (numero_res or 0)
    anio_res = fecha_res.year if fecha_res else anio
    timbre = [Timbre(ted_plano(raiz)), Spacer(1, 1 * mm), p('Timbre Electrónico SII', centro),
              p(f'Res. {numero} de {anio_res} - Verifique documento: www.sii.cl', centro)]
    derecha_pie = [totales]
    if cedible:
        acuse = Table([[p('Nombre:', chico), ''], [p('R.U.T.:', chico), ''], [p('Fecha:', chico), ''],
                       [p('Recinto:', chico), ''], [p('Firma:', chico), ''], [p(ACUSE, chico), '']],
                      colWidths=[18 * mm, 54 * mm])
        acuse.setStyle(TableStyle([('BOX', (0, 0), (-1, -1), 0.6, TINTA), ('SPAN', (0, -1), (-1, -1)),
                                   ('LINEBELOW', (1, 0), (1, 4), 0.4, SUAVE), ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
                                   ('TOPPADDING', (0, 0), (-1, -1), 4)]))
        leyenda = 'CEDIBLE CON SU FACTURA' if tipo == d.GUIA else 'CEDIBLE'
        derecha_pie += [Spacer(1, 4 * mm), acuse, Spacer(1, 2 * mm),
                        p(leyenda, ParagraphStyle('ced', parent=derecha_b, fontSize=12, leading=14))]
    pie = Table([[timbre, derecha_pie]], colWidths=[100 * mm, 84 * mm])
    pie.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                             ('LEFTPADDING', (0, 0), (0, 0), 6 * mm)]))
    # El timbre y los totales van juntos y enteros: si no caben, pasan a la página siguiente.
    final = [Spacer(1, 8 * mm), pie]
    if emitido.ambiente == CERTIFICACION:
        final += [Spacer(1, 3 * mm), p('Documento del ambiente de certificación del SII: sin validez tributaria.', suave)]
    cuerpo.append(KeepTogether(final))

    titulo = f'{NOMBRES.get(tipo, tipo)} N° {folio}'

    def siguientes(canvas, documento):
        # Desde la segunda página: de qué documento es y qué página, arriba a la derecha.
        canvas.saveState()
        canvas.setFont('Helvetica', 7.5)
        canvas.setFillColor(SUAVE)
        canvas.drawRightString(LETTER[0] - 16 * mm, LETTER[1] - 9 * mm, f'{titulo} · página {documento.page}')
        canvas.restoreState()

    pdf.build(cuerpo, onLaterPages=siguientes)
    return buf.getvalue()

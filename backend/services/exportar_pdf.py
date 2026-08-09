"""Convertir un documento en un PDF con formato, listo para mandar.

⭐ **Es lo inverso de "editar un PDF", y a propósito.** Modificar un PDF existente
conservando su diseño sale mal casi siempre: el resultado tiene tipografías que no calzan y
párrafos corridos, y quien lo recibe lo nota. Generar uno nuevo desde el contenido sí sale
bien — y además resuelve algo que el producto no tenía: **un artefacto que sale de Afable**
y se le manda al cliente.

Entiende Markdown simple porque es lo que escriben los agentes: `#` para títulos, `-` para
listas, `**negrita**`. Nada más elaborado: un conversor completo de Markdown a PDF es un
proyecto en sí, y lo que hace falta acá es que una propuesta o un informe se vean prolijos.
"""

import io
import re

from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

# El índigo de la marca, para los títulos. Un PDF que sale de Afable tiene que parecerse a
# Afable: es lo que se le manda a un cliente.
INDIGO = '#586AD0'


def _estilos():
    base = getSampleStyleSheet()
    return {
        'titulo': ParagraphStyle(
            'TituloAfable', parent=base['Title'], fontSize=20, leading=25,
            textColor=INDIGO, spaceAfter=18, alignment=0,
        ),
        'h2': ParagraphStyle(
            'H2Afable', parent=base['Heading2'], fontSize=13, leading=17,
            textColor=INDIGO, spaceBefore=14, spaceAfter=6,
        ),
        'cuerpo': ParagraphStyle(
            'CuerpoAfable', parent=base['BodyText'], fontSize=10.5, leading=15.5,
            alignment=TA_JUSTIFY, spaceAfter=8,
        ),
        'pie': ParagraphStyle(
            'PieAfable', parent=base['Normal'], fontSize=8, textColor='#888888',
        ),
    }


def _inline(texto):
    """Markdown en línea → las etiquetas que entiende reportlab."""
    texto = (texto
             .replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))
    texto = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', texto)
    texto = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', texto)
    return texto


def desde_texto(titulo, contenido, *, pie=''):
    """Devuelve los bytes de un PDF con ese título y ese contenido."""
    estilos = _estilos()
    buffer = io.BytesIO()
    documento = SimpleDocTemplate(
        buffer, pagesize=letter,
        leftMargin=2.2 * cm, rightMargin=2.2 * cm,
        topMargin=2.2 * cm, bottomMargin=2 * cm,
        title=titulo,
    )

    piezas = [Paragraph(_inline(titulo), estilos['titulo'])]
    vinetas = []

    def cerrar_lista():
        if vinetas:
            piezas.append(ListFlowable(list(vinetas), bulletType='bullet', leftIndent=14))
            piezas.append(Spacer(1, 6))
            vinetas.clear()

    for linea in (contenido or '').split('\n'):
        limpia = linea.rstrip()
        if not limpia.strip():
            cerrar_lista()
            continue
        if limpia.startswith('#'):
            cerrar_lista()
            piezas.append(Paragraph(_inline(limpia.lstrip('# ').strip()), estilos['h2']))
        elif limpia.lstrip().startswith(('- ', '* ')):
            vinetas.append(ListItem(
                Paragraph(_inline(limpia.lstrip()[2:]), estilos['cuerpo']), leftIndent=10,
            ))
        else:
            cerrar_lista()
            piezas.append(Paragraph(_inline(limpia.strip()), estilos['cuerpo']))
    cerrar_lista()

    if pie:
        piezas.append(Spacer(1, 18))
        piezas.append(Paragraph(_inline(pie), estilos['pie']))

    documento.build(piezas)
    return buffer.getvalue()


def desde_documento(doc):
    """El PDF de un documento de la empresa, con su título y su contenido."""
    return desde_texto(
        doc.title,
        doc.extracted_text or '',
        pie='Generado con Afable',
    )

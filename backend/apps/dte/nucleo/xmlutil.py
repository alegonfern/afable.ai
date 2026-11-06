"""Lo común del XML del SII: namespaces, textos en ISO-8859-1, números y base64."""
import base64
import re
import unicodedata
from decimal import Decimal

from lxml import etree

SII = 'http://www.sii.cl/SiiDte'
XSI = 'http://www.w3.org/2001/XMLSchema-instance'
DS = 'http://www.w3.org/2000/09/xmldsig#'
# Todo DTE vive con estos dos namespaces en alcance, esté suelto o dentro de un EnvioDTE: la firma
# usa C14N inclusivo, que incluye los namespaces heredados, y así el digest es siempre el mismo.
NSMAP = {None: SII, 'xsi': XSI}
DECLARACION = b'<?xml version="1.0" encoding="ISO-8859-1"?>\n'

# Lo que suele llegar pegado desde Word o el teléfono y no existe en ISO-8859-1.
_REEMPLAZOS = {'‘': "'", '’': "'", '“': '"', '”': '"', '–': '-', '—': '-',
               '…': '...', ' ': ' ', '•': '-', '€': 'EUR'}


def texto(valor, largo=None):
    """Un texto listo para el SII: solo caracteres ISO-8859-1, sin espacios de sobra, cortado al
    largo que admite el campo. Lo que no cabe en ISO-8859-1 se translitera o se quita."""
    s = str(valor or '')
    s = ''.join(_REEMPLAZOS.get(c, c) for c in s)
    salida = []
    for c in s:
        try:
            c.encode('iso-8859-1')
            salida.append(c)
        except UnicodeEncodeError:
            base = unicodedata.normalize('NFKD', c).encode('ascii', 'ignore').decode()
            salida.append(base)
    # Saltos y tabs a espacio; los espacios dobles se respetan: el nombre va tal cual al timbre.
    s = re.sub(r'[\t\r\n]+', ' ', ''.join(salida)).strip()
    return s[:largo].rstrip() if largo else s


def numero(valor):
    """Decimal sin ceros de sobra ni notación científica: 20, 4500.5, 0.000001."""
    d = Decimal(str(valor))
    if d == d.to_integral_value():
        return str(d.quantize(Decimal(1)))
    return format(d.normalize(), 'f')


def b64(datos, ancho=76):
    """Base64 en líneas de 76 caracteres, como lo pide el SII para firmas y certificados."""
    s = base64.b64encode(datos).decode('ascii')
    return '\n'.join(s[i:i + ancho] for i in range(0, len(s), ancho))


def entero_b64(n):
    return b64(n.to_bytes((n.bit_length() + 7) // 8, 'big'))


def sub(padre, tag, valor=None, **attrs):
    """Un hijo en el namespace del SII. Con valor None no se crea (los opcionales vacíos no van)."""
    el = etree.SubElement(padre, f'{{{SII}}}{tag}', **attrs)
    if valor is not None:
        el.text = str(valor)
    return el


def opcional(padre, tag, valor):
    if valor not in (None, ''):
        sub(padre, tag, valor)


def serializar(raiz):
    """El archivo final en ISO-8859-1, con la declaración exacta que valida el SII (comillas dobles)."""
    return DECLARACION + etree.tostring(raiz, encoding='ISO-8859-1', xml_declaration=False)


def leer(datos):
    parser = etree.XMLParser(remove_blank_text=False, resolve_entities=False, no_network=True)
    return etree.fromstring(datos, parser)

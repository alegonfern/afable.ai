"""Los XSD oficiales del SII y la validación contra ellos.

    dte/    DTE_v10, EnvioDTE_v10 (versión publicada el 06-02-2026)
    ic/     RespuestaEnvioDTE_v10 (respuesta de intercambio)
    19983/  EnvioRecibos_v10 (acuse de recibo de mercaderías, Ley 19.983)
    iecv/   LibroCV_v10 (libros de compra y venta, para la certificación)
    resp/   RespSII_v10 (la respuesta del SII por correo)
"""
from functools import lru_cache
from pathlib import Path

from lxml import etree

CARPETA = Path(__file__).parent
ESQUEMAS = {
    'EnvioDTE': 'dte/EnvioDTE_v10.xsd',
    'DTE': 'dte/DTE_v10.xsd',
    'RespuestaDTE': 'ic/RespuestaEnvioDTE_v10.xsd',
    'EnvioRecibos': '19983/EnvioRecibos_v10.xsd',
    'LibroCompraVenta': 'iecv/LibroCV_v10.xsd',
    'LibroGuia': 'lgd/LibroGuia_v10.xsd',
    'RespSII': 'resp/RespSII_v10.xsd',
}


@lru_cache(maxsize=None)
def esquema(nombre):
    return etree.XMLSchema(etree.parse(str(CARPETA / ESQUEMAS[nombre])))


def validar(xml, nombre):
    """Lista de errores (vacía si el XML cumple). `xml` puede ser bytes o un elemento."""
    if isinstance(xml, (bytes, str)):
        xml = etree.fromstring(xml.encode('iso-8859-1') if isinstance(xml, str) else xml)
    s = esquema(nombre)
    if s.validate(xml):
        return []
    return [f'línea {e.line}: {e.message}' for e in s.error_log]

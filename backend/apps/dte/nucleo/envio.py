"""El EnvioDTE: la carátula, los DTE y las firmas, listo para subir al SII (ESPEC_SII.md §7).

Cada <Documento> se firma ya puesto dentro del EnvioDTE (mismos namespaces en alcance que verá el
SII) y al final se firma el SetDTE. Después de firmar no se toca el formato: cualquier cambio de
espacios rompe los digest.
"""
import re
from dataclasses import dataclass
from datetime import date, datetime

from lxml import etree

from . import ErrorDTE, firma
from . import rut as ruts
from .xmlutil import NSMAP, SII, XSI, leer, serializar, sub

RUT_SII = '60803000-K'


@dataclass
class Caratula:
    rut_emisor: str
    rut_envia: str  # el titular del certificado que firma el envío
    fecha_resolucion: date
    numero_resolucion: int  # 0 en el ambiente de certificación
    rut_receptor: str = RUT_SII  # el SII; en el intercambio, el RUT del cliente


def armar(dtes, caratula, certificado, momento=None, validar_esquema=True):
    """Arma y firma el EnvioDTE con los <DTE> de documento.construir(). Devuelve los bytes en
    ISO-8859-1. Comprueba antes de devolver: esquema oficial, firmas y timbres."""
    if not dtes:
        raise ErrorDTE('El envío no tiene documentos.')
    if len(dtes) > 2000:
        raise ErrorDTE('Un envío al SII admite hasta 2.000 documentos.')
    rut_envia = ruts.normalizar(caratula.rut_envia)
    if certificado.rut and certificado.rut != rut_envia:
        raise ErrorDTE(f'El certificado es de {certificado.rut} y el envío lo firma {rut_envia}.')
    momento = (momento or datetime.now()).replace(microsecond=0)

    # La línea 2 igual a la del ejemplo oficial (el SII la valida): schemaLocation antes de version.
    raiz = etree.Element(f'{{{SII}}}EnvioDTE', nsmap=NSMAP)
    raiz.set(f'{{{XSI}}}schemaLocation', 'http://www.sii.cl/SiiDte EnvioDTE_v10.xsd')
    raiz.set('version', '1.0')
    setdte = sub(raiz, 'SetDTE', ID='SetDoc')
    car = sub(setdte, 'Caratula', version='1.0')
    sub(car, 'RutEmisor', ruts.normalizar(caratula.rut_emisor))
    sub(car, 'RutEnvia', rut_envia)
    sub(car, 'RutReceptor', ruts.normalizar(caratula.rut_receptor))
    sub(car, 'FchResol', caratula.fecha_resolucion.isoformat())
    sub(car, 'NroResol', int(caratula.numero_resolucion))
    sub(car, 'TmstFirmaEnv', momento.strftime('%Y-%m-%dT%H:%M:%S'))
    conteo = {}
    for dte in dtes:
        tipo = dte.findtext(f'{{{SII}}}Documento/{{{SII}}}Encabezado/{{{SII}}}IdDoc/{{{SII}}}TipoDTE')
        conteo[tipo] = conteo.get(tipo, 0) + 1
    for tipo, n in conteo.items():  # en el orden en que aparecen, como los entregó el set
        st = sub(car, 'SubTotDTE')
        sub(st, 'TpoDTE', tipo)
        sub(st, 'NroDTE', n)
    for dte in dtes:
        setdte.append(dte)
    # Las declaraciones repetidas de los DTE sueltos se suben a la raíz; no cambian el C14N.
    etree.cleanup_namespaces(raiz, top_nsmap=NSMAP, keep_ns_prefixes=['xsi'])
    # Un salto de línea después de cada tag (lo pide el SII). Los DTE ya firmados (los que se
    # reenvían, por ejemplo al cliente) no se tocan: cualquier espacio de más rompe su firma.
    firmados = [dte.find(f'{{{firma.DS}}}Signature') is not None for dte in setdte.iterfind(f'{{{SII}}}DTE')]
    raiz.text, setdte.text, setdte.tail = '\n', '\n', '\n'
    etree.indent(car, space=' ', level=1)
    car.tail = '\n'
    for dte, firmado in zip(setdte.iterfind(f'{{{SII}}}DTE'), firmados):
        if not firmado:
            etree.indent(dte, space=' ', level=1)
        dte.tail = '\n'

    for dte, firmado in zip(setdte.iterfind(f'{{{SII}}}DTE'), firmados):
        if not firmado:
            firma.firmar(dte.find(f'{{{SII}}}Documento'), certificado)
    firma.firmar(setdte, certificado)

    datos = serializar(raiz)
    revisar(datos, validar_esquema=validar_esquema)
    return datos


def revisar(datos, validar_esquema=True, cafs=None):
    """Valida un EnvioDTE ya armado: esquema, firmas y (si se pasan los CAF) timbres.
    Lanza ErrorDTE con el detalle de lo que falle."""
    from . import ted
    from .esquemas import validar

    raiz = leer(datos)
    if validar_esquema:
        errores = validar(raiz, 'EnvioDTE')
        if errores:
            raise ErrorDTE('El XML no cumple el esquema del SII: ' + '; '.join(errores[:5]))
    malas = [f'{uri}: {motivo}' for uri, ok, motivo in firma.verificar(raiz) if not ok]
    if malas:
        raise ErrorDTE('Firma inválida en ' + '; '.join(malas))
    for t in raiz.iter(f'{{{SII}}}TED'):
        dd = t.find(f'{{{SII}}}DD')
        clave = (dd.findtext(f'{{{SII}}}RE'), int(dd.findtext(f'{{{SII}}}TD')))
        caf = (cafs or {}).get(clave)
        if caf and not ted.verificar(t, caf):
            raise ErrorDTE(f'El timbre del folio {dd.findtext(f"{{{SII}}}F")} no corresponde a su CAF.')
    return raiz


def dtes_de(datos):
    """Los <DTE> de un EnvioDTE, como elementos listos para volver a enviarse en otro (por ejemplo
    al cliente, en el intercambio). Conservan sus firmas: el contexto de namespaces es el mismo."""
    raiz = leer(datos)
    return list(raiz.iter(f'{{{SII}}}DTE'))


def dte_suelto(dte):
    """Un DTE firmado como archivo propio, con los mismos namespaces en alcance que dentro del
    EnvioDTE: así su firma se puede verificar suelta."""
    s = etree.tostring(dte, encoding='unicode')
    s = re.sub(r'^<DTE\b[^>]*>', f'<DTE xmlns="{SII}" xmlns:xsi="{XSI}" version="1.0">', s, count=1)
    return serializar(leer(s.encode('utf-8')))  # sin declaración, lxml lee UTF-8

"""Las respuestas del intercambio entre contribuyentes (ESPEC_SII.md §8.2 y §8.3).

    recepcion()  RespuestaDTE con RecepcionEnvio: el acuse de recibo de un EnvioDTE, con el
                 estado de cada documento.
    resultado()  RespuestaDTE con ResultadoDTE: la aceptación o el rechazo comercial.
    recibos()    EnvioRecibos (Ley 19.983): el recibo de las mercaderías o servicios, con doble
                 firma (cada Recibo y el SetRecibos).

Un mensaje lleva acuse o resultado, nunca los dos. Se firman ya puestos en su árbol final (firma.py)
y se validan contra los XSD oficiales antes de devolverlos.
"""
from dataclasses import dataclass
from datetime import date, datetime

from lxml import etree

from . import ErrorDTE, firma
from . import rut as ruts
from .xmlutil import NSMAP, SII, XSI, serializar, sub, texto

# EstadoRecepEnv (el envío completo).
ENVIO_OK, ENVIO_ESQUEMA, ENVIO_FIRMA, ENVIO_RUT_RECEPTOR, ENVIO_REPETIDO, ENVIO_ILEGIBLE, ENVIO_OTRO = (
    0, 1, 2, 3, 90, 91, 99)
GLOSAS_ENVIO = {0: 'Envio Recibido Conforme', 1: 'Envio Rechazado - Error de Schema',
                2: 'Envio Rechazado - Error de Firma', 3: 'Envio Rechazado - RUT Receptor No Corresponde',
                90: 'Envio Rechazado - Archivo Repetido', 91: 'Envio Rechazado - Archivo Ilegible',
                99: 'Envio Rechazado - Otros'}
# EstadoRecepDTE (cada documento).
DTE_OK, DTE_FIRMA, DTE_RUT_EMISOR, DTE_RUT_RECEPTOR, DTE_REPETIDO, DTE_OTRO = 0, 1, 2, 3, 4, 99
GLOSAS_DTE = {0: 'DTE Recibido OK', 1: 'DTE No Recibido - Error de Firma', 2: 'DTE No Recibido - Error en RUT Emisor',
              3: 'DTE No Recibido - Error en RUT Receptor', 4: 'DTE No Recibido - DTE Repetido',
              99: 'DTE No Recibido - Otros'}
# EstadoDTE del resultado comercial.
ACEPTADO, ACEPTADO_CON_DISCREPANCIAS, RECHAZADO = 0, 1, 2
# El texto que fija el XSD de Recibos (sin tildes ni símbolo de grado: así lo publica el SII).
DECLARACION = ('El acuse de recibo que se declara en este acto, de acuerdo a lo dispuesto en la letra b) del '
               'Art. 4, y la letra c) del Art. 5 de la Ley 19.983, acredita que la entrega de mercaderias o '
               'servicio(s) prestado(s) ha(n) sido recibido(s).')


@dataclass
class Referencia:
    """Los datos con que se nombra un DTE en las respuestas."""
    tipo: int
    folio: int
    fecha: date
    rut_emisor: str
    rut_receptor: str
    monto_total: int


@dataclass
class Contacto:
    nombre: str = ''
    telefono: str = ''
    correo: str = ''


def _ahora(momento):
    return (momento or datetime.now()).replace(microsecond=0).strftime('%Y-%m-%dT%H:%M:%S')


def _raiz(tag, xsd):
    raiz = etree.Element(f'{{{SII}}}{tag}', nsmap=NSMAP)
    raiz.set(f'{{{XSI}}}schemaLocation', f'http://www.sii.cl/SiiDte {xsd}')
    raiz.set('version', '1.0')
    return raiz


def _contacto(car, contacto):
    if not contacto:
        return
    if contacto.nombre:
        sub(car, 'NmbContacto', texto(contacto.nombre, 40))
    if contacto.telefono:
        sub(car, 'FonoContacto', texto(contacto.telefono, 40))
    if contacto.correo:
        sub(car, 'MailContacto', texto(contacto.correo, 80))


def _ref(padre, r, tipo_tag='TipoDTE'):
    sub(padre, tipo_tag, int(r.tipo))
    sub(padre, 'Folio', int(r.folio))
    sub(padre, 'FchEmis', r.fecha.isoformat())
    sub(padre, 'RUTEmisor', ruts.normalizar(r.rut_emisor))
    sub(padre, 'RUTRecep', ruts.normalizar(r.rut_receptor))
    sub(padre, 'MntTotal', int(r.monto_total))


def _cerrar(raiz, firmables, certificado, esquema):
    """Formatea, firma en orden (de adentro hacia afuera) y valida. Devuelve los bytes."""
    from .esquemas import validar
    etree.indent(raiz, space=' ')
    for nodo in firmables:
        firma.firmar(nodo, certificado)
    datos = serializar(raiz)
    from .xmlutil import leer
    final = leer(datos)
    errores = validar(final, esquema)
    if errores:
        raise ErrorDTE('La respuesta no cumple el esquema del SII: ' + '; '.join(errores[:5]))
    malas = [uri for uri, ok, _ in firma.verificar(final) if not ok]
    if malas:
        raise ErrorDTE('No se pudo firmar la respuesta: ' + ', '.join(malas))
    return datos


def _caratula(resultado, rut_responde, rut_recibe, id_respuesta, n, contacto, momento):
    car = sub(resultado, 'Caratula', version='1.0')
    sub(car, 'RutResponde', ruts.normalizar(rut_responde))
    sub(car, 'RutRecibe', ruts.normalizar(rut_recibe))
    sub(car, 'IdRespuesta', int(id_respuesta))
    sub(car, 'NroDetalles', n)
    _contacto(car, contacto)
    sub(car, 'TmstFirmaResp', _ahora(momento))


def recepcion(rut_responde, rut_recibe, nombre_envio, fecha_recepcion, envio_id, estado_envio, detalles,
              certificado, digest='', cod_envio=1, id_respuesta=1, contacto=None, momento=None):
    """El acuse de recibo de un EnvioDTE. `detalles` es [(Referencia, estado, glosa|None)], uno
    por DTE; con el envío rechazado (estado distinto de 0) puede ir vacío."""
    raiz = _raiz('RespuestaDTE', 'RespuestaEnvioDTE_v10.xsd')
    res = sub(raiz, 'Resultado', ID=f'R{int(id_respuesta)}')
    _caratula(res, rut_responde, rut_recibe, id_respuesta, 1, contacto, momento)
    rec = sub(res, 'RecepcionEnvio')
    sub(rec, 'NmbEnvio', texto(nombre_envio, 80) or 'EnvioDTE.xml')
    sub(rec, 'FchRecep', _ahora(fecha_recepcion))
    sub(rec, 'CodEnvio', int(cod_envio))
    sub(rec, 'EnvioDTEID', texto(envio_id, 80) or 'SetDoc')
    if digest:
        sub(rec, 'Digest', digest)
    sub(rec, 'RutEmisor', ruts.normalizar(rut_recibe))
    sub(rec, 'RutReceptor', ruts.normalizar(rut_responde))
    sub(rec, 'EstadoRecepEnv', int(estado_envio))
    sub(rec, 'RecepEnvGlosa', GLOSAS_ENVIO.get(int(estado_envio), GLOSAS_ENVIO[ENVIO_OTRO]))
    if detalles:
        sub(rec, 'NroDTE', len(detalles))
    for r, estado, glosa in detalles:
        d = sub(rec, 'RecepcionDTE')
        _ref(d, r)
        sub(d, 'EstadoRecepDTE', int(estado))
        sub(d, 'RecepDTEGlosa', texto(glosa or GLOSAS_DTE.get(int(estado), GLOSAS_DTE[DTE_OTRO]), 256))
    return _cerrar(raiz, [res], certificado, 'RespuestaDTE')


def resultado(rut_responde, rut_recibe, resultados, certificado, cod_envio=1, id_respuesta=1, contacto=None,
              momento=None):
    """La aceptación o el rechazo comercial. `resultados` es [(Referencia, estado, glosa)] con
    estado ACEPTADO, ACEPTADO_CON_DISCREPANCIAS o RECHAZADO."""
    if not resultados:
        raise ErrorDTE('La respuesta comercial no tiene documentos.')
    raiz = _raiz('RespuestaDTE', 'RespuestaEnvioDTE_v10.xsd')
    res = sub(raiz, 'Resultado', ID=f'R{int(id_respuesta)}')
    _caratula(res, rut_responde, rut_recibe, id_respuesta, len(resultados), contacto, momento)
    for r, estado, glosa in resultados:
        d = sub(res, 'ResultadoDTE')
        _ref(d, r)
        sub(d, 'CodEnvio', int(cod_envio))
        sub(d, 'EstadoDTE', int(estado))
        sub(d, 'EstadoDTEGlosa', texto(glosa or ('ACEPTADO OK' if estado == ACEPTADO else 'RECHAZADO'), 256))
        if estado != ACEPTADO:
            sub(d, 'CodRchDsc', -1)
    return _cerrar(raiz, [res], certificado, 'RespuestaDTE')


def recibos(rut_responde, rut_recibe, documentos, recinto, rut_firma, certificado, contacto=None, momento=None):
    """El recibo de mercaderías o servicios (Ley 19.983) de `documentos` [Referencia]. Firma cada
    DocumentoRecibo con el certificado de `rut_firma` y luego el SetRecibos."""
    if not documentos:
        raise ErrorDTE('El recibo no tiene documentos.')
    raiz = _raiz('EnvioRecibos', 'EnvioRecibos_v10.xsd')
    setr = sub(raiz, 'SetRecibos', ID='SetRec')
    car = sub(setr, 'Caratula', version='1.0')
    sub(car, 'RutResponde', ruts.normalizar(rut_responde))
    sub(car, 'RutRecibe', ruts.normalizar(rut_recibe))
    _contacto(car, contacto)
    sub(car, 'TmstFirmaEnv', _ahora(momento))
    firmables = []
    for i, r in enumerate(documentos, 1):
        rec = sub(setr, 'Recibo', version='1.0')
        doc = sub(rec, 'DocumentoRecibo', ID=f'T{int(r.tipo)}F{int(r.folio)}R{i}')
        _ref(doc, r, tipo_tag='TipoDoc')
        sub(doc, 'Recinto', texto(recinto, 80) or 'Oficina')
        sub(doc, 'RutFirma', ruts.normalizar(rut_firma))
        sub(doc, 'Declaracion', DECLARACION)
        sub(doc, 'TmstFirmaRecibo', _ahora(momento))
        firmables.append(doc)
    firmables.append(setr)
    return _cerrar(raiz, firmables, certificado, 'EnvioRecibos')

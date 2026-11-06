"""La conexión con el SII: autenticación, envío y consultas (ESPEC_SII.md §1-3 y §8.4).

Python puro (requests), sin Django: recibe el certificado y devuelve datos. Dos ambientes que no
se mezclan: certificación (maullin) y producción (palena); el token de uno no sirve en el otro.

    cliente = ClienteSII(certificado, CERTIFICACION)
    r = cliente.enviar(xml, rut_empresa='76123456-7')      # -> RespuestaEnvio(trackid=...)
    cliente.estado_envio('76123456-7', r.trackid)          # -> EstadoEnvio(estado='EPR', ...)
"""
import html
import logging
import re
import time
from dataclasses import dataclass, field

import requests
from lxml import etree

from .nucleo import ErrorDTE, firma
from .nucleo import rut as ruts

logger = logging.getLogger(__name__)

CERTIFICACION, PRODUCCION = 'certificacion', 'produccion'
HOSTS = {CERTIFICACION: 'maullin.sii.cl', PRODUCCION: 'palena.sii.cl'}
RECLAMO = {CERTIFICACION: 'https://ws2.sii.cl/WSREGISTRORECLAMODTECERT/registroreclamodteservice',
           PRODUCCION: 'https://ws1.sii.cl/WSREGISTRORECLAMODTE/registroreclamodteservice'}
NS_RECLAMO = 'http://ws.registroreclamodte.diii.sdi.sii.cl'
# "PROG 1.0" en el User-Agent hace que el upload responda XML y no HTML (manual de envío v1.2).
USER_AGENT = 'Mozilla/4.0 (compatible; PROG 1.0; Windows NT 5.0; YComp 5.0.2.4)'
TIMEOUT = 60

STATUS_UPLOAD = {
    1: 'El usuario que envía no tiene permiso para enviar documentos de esta empresa.',
    2: 'El archivo tiene un tamaño que el SII no acepta.',
    3: 'El archivo llegó cortado.',
    5: 'La sesión con el SII no es válida (token).',
    6: 'La empresa no está autorizada para enviar documentos electrónicos.',
    7: 'El SII rechazó el archivo: no cumple el esquema.',
    8: 'El SII rechazó la firma del archivo.',
    9: 'El sistema del SII está bloqueado.',
}
ESTADOS_ENVIO = {
    'RSC': 'Rechazado por error en el esquema', 'SOK': 'Esquema validado', 'CRT': 'Carátula aceptada',
    'RCT': 'Rechazado por error en la carátula', 'RFR': 'Rechazado por error en la firma',
    'FOK': 'Firma del envío validada', 'PDR': 'Envío en proceso', 'EPR': 'Envío procesado',
    'RPR': 'Aceptado con reparos', 'RLV': 'Aceptado con reparos leves', 'RPT': 'Rechazado',
    'RCH': 'Rechazado',
}
ENVIO_FINAL = {'RSC', 'RCT', 'RFR', 'EPR', 'RPR', 'RLV', 'RPT', 'RCH'}
ENVIO_RECHAZADO = {'RSC', 'RCT', 'RFR', 'RPT', 'RCH'}
ESTADOS_DTE = {
    'DOK': 'Recibido por el SII, los datos coinciden', 'DNK': 'Recibido por el SII, pero los datos no coinciden',
    'FAU': 'No recibido por el SII', 'FNA': 'No autorizado', 'FAN': 'Anulado',
    'EMP': 'Empresa no autorizada a emitir documentos electrónicos', 'TMD': 'Una nota de débito modifica su texto',
    'TMC': 'Una nota de crédito modifica su texto', 'MMD': 'Una nota de débito modifica sus montos',
    'MMC': 'Una nota de crédito modifica sus montos', 'AND': 'Una nota de débito lo anula',
    'ANC': 'Una nota de crédito lo anula',
}
TOKEN_INVALIDO = {'001', '002', '003'}
# Registro de aceptación o reclamo (Ley 20.956): solo 33, 34 y 43, dentro de 8 días.
ACEPTA_CONTENIDO, RECLAMA_CONTENIDO, RECIBO_MERCADERIAS = 'ACD', 'RCD', 'ERM'
RECLAMO_FALTA_PARCIAL, RECLAMO_FALTA_TOTAL = 'RFP', 'RFT'


class ErrorSII(ErrorDTE):
    def __init__(self, mensaje, codigo=None, detalle=''):
        super().__init__(mensaje)
        self.codigo, self.detalle = codigo, detalle


@dataclass
class RespuestaEnvio:
    status: int
    trackid: str = ''
    detalle: list = field(default_factory=list)
    xml: str = ''

    @property
    def ok(self):
        return self.status == 0 and bool(self.trackid)


@dataclass
class EstadoEnvio:
    estado: str
    glosa: str = ''
    resumen: list = field(default_factory=list)  # [{tipo, informados, aceptados, rechazados, reparos}]
    xml: str = ''

    @property
    def final(self):
        return self.estado in ENVIO_FINAL

    @property
    def rechazado(self):
        return self.estado in ENVIO_RECHAZADO or any(r['rechazados'] for r in self.resumen)

    @property
    def descripcion(self):
        return ESTADOS_ENVIO.get(self.estado, self.glosa or self.estado)


def _soap(metodo, ns, params):
    """Un sobre SOAP 1.1 RPC/encoded como el que esperan los .jws (Apache Axis) del SII."""
    args = ''.join(f'<{k} xsi:type="xsd:string">{html.escape(str(v), quote=False)}</{k}>' for k, v in params)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" '
        'xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f'<SOAP-ENV:Body><m:{metodo} xmlns:m="{ns}">{args}</m:{metodo}></SOAP-ENV:Body></SOAP-ENV:Envelope>'
    ).encode('utf-8')


def _retorno(respuesta, metodo):
    """El XML que viene escapado dentro de <metodoReturn>, ya parseado."""
    try:
        sobre = etree.fromstring(respuesta.content)
    except etree.XMLSyntaxError:
        raise ErrorSII(f'El SII respondió algo que no es XML ({respuesta.status_code}).', detalle=respuesta.text[:500])
    falla = sobre.find('.//{http://schemas.xmlsoap.org/soap/envelope/}Fault')
    if falla is not None:
        raise ErrorSII(f'El SII respondió con error: {falla.findtext("faultstring") or "sin detalle"}.')
    nodo = next((e for e in sobre.iter() if isinstance(e.tag, str) and etree.QName(e).localname == f'{metodo}Return'), None)
    if nodo is None or not (nodo.text or '').strip():
        raise ErrorSII('El SII respondió sin datos.', detalle=respuesta.text[:500])
    # El XML interno trae su propia declaración (a veces ISO-8859-1), pero ya viene decodificado
    # dentro del sobre: se parsea como texto, sin la declaración, para no decodificarlo dos veces.
    interno = re.sub(r'^\s*<\?xml[^>]*\?>', '', nodo.text.strip())
    try:
        return etree.fromstring(interno)
    except etree.XMLSyntaxError:
        return etree.fromstring(html.unescape(interno))


def _texto(raiz, nombre):
    """El texto del primer elemento con ese nombre local, sin importar el prefijo (SII:, sin prefijo).
    Las glosas del SII llegan a veces con las tildes ya perdidas en su lado ("Invï¿½lido"):
    se deja un "?" en vez del garabato."""
    for e in raiz.iter():
        if isinstance(e.tag, str) and etree.QName(e).localname == nombre:
            return (e.text or '').strip().replace('ï¿½', '?').replace('�', '?')
    return ''


class ClienteSII:
    def __init__(self, certificado, ambiente=CERTIFICACION, sesion=None):
        if ambiente not in HOSTS:
            raise ValueError(f'Ambiente desconocido: {ambiente}')
        self.certificado, self.ambiente = certificado, ambiente
        self.host = HOSTS[ambiente]
        self.sesion = sesion or requests.Session()
        self._token, self._token_en = None, 0

    # ── Autenticación ──────────────────────────────────────────────────────────────────────

    def _ws(self, servicio, metodo, params=()):
        url = f'https://{self.host}/DTEWS/{servicio}.jws'
        r = self.sesion.post(url, data=_soap(metodo, 'http://DefaultNamespace', params), timeout=TIMEOUT,
                             headers={'Content-Type': 'text/xml; charset=utf-8', 'SOAPAction': '""'})
        return _retorno(r, metodo)

    def semilla(self):
        resp = self._ws('CrSeed', 'getSeed')
        estado = _texto(resp, 'ESTADO')
        semilla = _texto(resp, 'SEMILLA') or _texto(resp, 'SEED')
        if estado != '00' or not semilla:
            raise ErrorSII(f'El SII no entregó la semilla de autenticación (estado {estado}).', codigo=estado)
        return semilla

    def semilla_firmada(self, semilla):
        raiz = etree.Element('getToken')
        item = etree.SubElement(raiz, 'item')
        etree.SubElement(item, 'Semilla').text = semilla
        firma.firmar_documento(raiz, self.certificado)
        return '<?xml version="1.0"?>\n' + etree.tostring(raiz, encoding='unicode')

    def token(self, renovar=False):
        """El token de la sesión. Se reutiliza hasta 50 minutos [NV: el SII no publica su vigencia]."""
        if self._token and not renovar and time.time() - self._token_en < 50 * 60:
            return self._token
        resp = self._ws('GetTokenFromSeed', 'getToken', [('pszXml', self.semilla_firmada(self.semilla()))])
        estado = _texto(resp, 'ESTADO')
        token = _texto(resp, 'TOKEN')
        if estado != '00' or not token:
            glosa = _texto(resp, 'GLOSA')
            if estado in ('-07', '-7', '-3'):
                raise ErrorSII('El SII no reconoce el certificado de esta persona: debe tener habilitada la '
                               'autenticación con certificado digital en sii.cl.', codigo=estado, detalle=glosa)
            raise ErrorSII(f'El SII no entregó la sesión (estado {estado}: {glosa or "sin detalle"}).', codigo=estado)
        self._token, self._token_en = token, time.time()
        return token

    def _con_token(self, llamada):
        """`llamada(token)` devuelve (resultado, token_vencido). Si el SII dice que el token venció,
        se repite una vez con uno nuevo."""
        resultado, vencido = llamada(self.token())
        if vencido:
            resultado, _ = llamada(self.token(renovar=True))
        return resultado

    # ── Envío ──────────────────────────────────────────────────────────────────────────────

    def enviar(self, xml, rut_empresa, nombre='EnvioDTE.xml'):
        """Sube un EnvioDTE (o un libro) firmado. STATUS 0 solo dice que llegó: el resultado se
        consulta después con estado_envio()."""
        rut_envia, dv_envia = ruts.partes(self.certificado.rut)
        rut_emp, dv_emp = ruts.partes(rut_empresa)

        def subir(token):
            campos = [('rutSender', (None, rut_envia)), ('dvSender', (None, dv_envia)),
                      ('rutCompany', (None, rut_emp)), ('dvCompany', (None, dv_emp)),
                      ('archivo', (nombre, xml, 'text/xml'))]
            r = self.sesion.post(f'https://{self.host}/cgi_dte/UPL/DTEUpload', files=campos, timeout=TIMEOUT * 3,
                                 headers={'User-Agent': USER_AGENT, 'Cookie': f'TOKEN={token}', 'Accept': '*/*',
                                          'Referer': 'https://afable.ai/', 'Cache-Control': 'no-cache'})
            try:
                raiz = etree.fromstring(r.content)
            except etree.XMLSyntaxError:
                if b'<html' in r.content[:500].lower():  # la página de login: el token no sirvió
                    return RespuestaEnvio(status=5, xml=r.text[:2000]), True
                raise ErrorSII('El SII respondió algo que no es XML al subir el archivo.', detalle=r.text[:500])
            status = int(_texto(raiz, 'STATUS') or -1)
            detalle = [(e.text or '').strip() for e in raiz.iter('ERROR')]
            return RespuestaEnvio(status=status, trackid=_texto(raiz, 'TRACKID'), detalle=detalle,
                                  xml=r.content.decode('iso-8859-1')), status == 5

        resp = self._con_token(subir)
        if not resp.ok:
            motivo = STATUS_UPLOAD.get(resp.status, f'El SII no recibió el archivo (STATUS {resp.status}).')
            raise ErrorSII(motivo + (' ' + '; '.join(resp.detalle) if resp.detalle else ''), codigo=resp.status,
                           detalle=resp.xml)
        return resp

    # ── Consultas ──────────────────────────────────────────────────────────────────────────

    def estado_envio(self, rut_empresa, trackid):
        rut_emp, dv_emp = ruts.partes(rut_empresa)

        def consultar(token):
            resp = self._ws('QueryEstUp', 'getEstUp', [('RutCompania', rut_emp), ('DvCompania', dv_emp),
                                                       ('TrackId', trackid), ('Token', token)])
            estado = _texto(resp, 'ESTADO')
            # RESP_BODY trae, en orden, TIPO_DOCTO seguido de sus conteos; se repite por tipo.
            resumen = []
            for e in resp.iter():
                if not isinstance(e.tag, str):
                    continue
                nombre = etree.QName(e).localname
                if nombre == 'TIPO_DOCTO':
                    resumen.append({'tipo': (e.text or '').strip(), 'informados': 0, 'aceptados': 0,
                                    'rechazados': 0, 'reparos': 0})
                elif resumen and nombre.lower() in resumen[-1]:
                    resumen[-1][nombre.lower()] = int((e.text or '0').strip() or 0)
            return EstadoEnvio(estado=estado, glosa=_texto(resp, 'GLOSA'), resumen=resumen,
                               xml=etree.tostring(resp, encoding='unicode')), estado in TOKEN_INVALIDO

        r = self._con_token(consultar)
        if r.estado.startswith('-') or r.estado in TOKEN_INVALIDO:
            raise ErrorSII(f'El SII no pudo consultar el envío {trackid} ({r.estado}: {r.glosa}).', codigo=r.estado)
        return r

    def estado_dte(self, rut_empresa, rut_receptor, tipo, folio, fecha, monto):
        rut_cons, dv_cons = ruts.partes(self.certificado.rut)
        rut_emp, dv_emp = ruts.partes(rut_empresa)
        rut_rec, dv_rec = ruts.partes(rut_receptor)

        def consultar(token):
            resp = self._ws('QueryEstDte', 'getEstDte', [
                ('RutConsultante', rut_cons), ('DvConsultante', dv_cons), ('RutCompania', rut_emp),
                ('DvCompania', dv_emp), ('RutReceptor', rut_rec), ('DvReceptor', dv_rec), ('TipoDte', tipo),
                ('FolioDte', folio), ('FechaEmisionDte', fecha.strftime('%d%m%Y')), ('MontoDte', int(monto)),
                ('Token', token)])
            estado = _texto(resp, 'ESTADO')
            return {'estado': estado, 'glosa': _texto(resp, 'GLOSA') or _texto(resp, 'GLOSA_ESTADO'),
                    'error': _texto(resp, 'ERR_CODE'), 'descripcion': ESTADOS_DTE.get(estado, ''),
                    'xml': etree.tostring(resp, encoding='unicode')}, estado in TOKEN_INVALIDO

        return self._con_token(consultar)

    # ── Registro de aceptación o reclamo (Ley 20.956) ──────────────────────────────────────

    def _reclamo(self, metodo, rut_emisor, tipo, folio, accion=None):
        rut_emi, dv_emi = ruts.partes(rut_emisor)
        params = [('rutEmisor', rut_emi), ('dvEmisor', dv_emi), ('tipoDoc', tipo), ('folio', folio)]
        if accion:
            params.append(('accionDoc', accion))
        cuerpo = ''.join(f'<{k}>{html.escape(str(v), quote=False)}</{k}>' for k, v in params)
        sobre = ('<?xml version="1.0" encoding="UTF-8"?>'
                 '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
                 f'xmlns:ws="{NS_RECLAMO}"><soapenv:Body><ws:{metodo}>{cuerpo}</ws:{metodo}>'
                 '</soapenv:Body></soapenv:Envelope>').encode('utf-8')

        def llamar(token):
            r = self.sesion.post(RECLAMO[self.ambiente], data=sobre, timeout=TIMEOUT,
                                 headers={'Content-Type': 'text/xml; charset=utf-8', 'SOAPAction': '""',
                                          'Cookie': f'TOKEN={token}'})
            try:
                raiz = etree.fromstring(r.content)
            except etree.XMLSyntaxError:
                raise ErrorSII('El registro de reclamos del SII respondió algo que no es XML.', detalle=r.text[:500])
            codigo = _texto(raiz, 'codResp')
            eventos = [{etree.QName(x).localname: (x.text or '').strip() for x in ev if isinstance(x.tag, str)}
                       for ev in raiz.iter() if isinstance(ev.tag, str) and etree.QName(ev).localname == 'listaEventosDoc']
            return {'codigo': int(codigo) if codigo.lstrip('-').isdigit() else None,
                    'descripcion': _texto(raiz, 'descResp'), 'eventos': eventos},                 not codigo and r.status_code in (401, 403)

        return self._con_token(llamar)

    def aceptar_o_reclamar(self, rut_emisor, tipo, folio, accion):
        if int(tipo) not in (33, 34, 43):
            raise ErrorSII('El SII solo registra aceptaciones y reclamos de facturas (33, 34 y 43).')
        if accion not in (ACEPTA_CONTENIDO, RECLAMA_CONTENIDO, RECIBO_MERCADERIAS, RECLAMO_FALTA_PARCIAL,
                          RECLAMO_FALTA_TOTAL):
            raise ErrorSII(f'Acción desconocida: {accion}.')
        return self._reclamo('ingresarAceptacionReclamoDoc', rut_emisor, tipo, folio, accion)

    def eventos(self, rut_emisor, tipo, folio):
        return self._reclamo('listarEventosHistDoc', rut_emisor, tipo, folio)

    def fecha_recepcion(self, rut_emisor, tipo, folio):
        return self._reclamo('consultarFechaRecepcionSii', rut_emisor, tipo, folio)

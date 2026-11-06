"""Pruebas del cliente del SII (apps/dte/sii.py) contra un SII simulado: sin red.

Revisan lo que se manda (la semilla firmada, los campos del upload, el token en la cookie) y cómo se
leen las respuestas, con los formatos de los manuales del SII.
"""
import html
import re
import unittest
from datetime import date

from lxml import etree

from apps.dte import sii
from apps.dte.nucleo import firma
from apps.dte.nucleo.certificado import Certificado
from apps.dte.tests_nucleo import pfx_de_prueba


def _sobre(metodo, interno):
    return (f'<?xml version="1.0" encoding="utf-8"?><soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">'
            f'<soapenv:Body><ns1:{metodo}Response xmlns:ns1="http://DefaultNamespace">'
            f'<ns1:{metodo}Return>{html.escape(interno)}</ns1:{metodo}Return>'
            f'</ns1:{metodo}Response></soapenv:Body></soapenv:Envelope>').encode()


SEMILLA = ('<?xml version="1.0" encoding="UTF-8"?><SII:RESPUESTA xmlns:SII="http://www.sii.cl/XMLSchema">'
           '<SII:RESP_HDR><ESTADO>00</ESTADO></SII:RESP_HDR><SII:RESP_BODY><SEMILLA>000002360958</SEMILLA>'
           '</SII:RESP_BODY></SII:RESPUESTA>')


def _token(valor='XAuSbYXiNhIk', estado='00'):
    return ('<?xml version="1.0" encoding="UTF-8"?><SII:RESPUESTA xmlns:SII="http://www.sii.cl/XMLSchema">'
            f'<SII:RESP_HDR><ESTADO>{estado}</ESTADO><GLOSA>Token Creado</GLOSA></SII:RESP_HDR>'
            f'<SII:RESP_BODY><TOKEN>{valor}</TOKEN></SII:RESP_BODY></SII:RESPUESTA>')


class Respuesta:
    def __init__(self, contenido, status=200):
        self.content = contenido if isinstance(contenido, bytes) else contenido.encode('iso-8859-1')
        self.status_code = status
        self.text = self.content.decode('iso-8859-1')


class SIISimulado:
    """Una sesión de requests falsa: responde según la URL y guarda lo que se le pidió."""

    def __init__(self, upload=None, estup=None, estdte=None, reclamo=None, tokens=('TOKEN1',)):
        self.pedidos, self.tokens = [], list(tokens)
        self.upload, self.estup, self.estdte, self.reclamo = upload, estup, estdte, reclamo

    def post(self, url, data=None, files=None, headers=None, timeout=None):
        self.pedidos.append({'url': url, 'data': data, 'files': files, 'headers': headers})
        if url.endswith('CrSeed.jws'):
            return Respuesta(_sobre('getSeed', SEMILLA))
        if url.endswith('GetTokenFromSeed.jws'):
            return Respuesta(_sobre('getToken', _token(self.tokens.pop(0) if len(self.tokens) > 1 else self.tokens[0])))
        if url.endswith('DTEUpload'):
            return Respuesta(self.upload.pop(0) if isinstance(self.upload, list) else self.upload)
        if url.endswith('QueryEstUp.jws'):
            return Respuesta(_sobre('getEstUp', self.estup.pop(0) if isinstance(self.estup, list) else self.estup))
        if url.endswith('QueryEstDte.jws'):
            return Respuesta(_sobre('getEstDte', self.estdte))
        if 'registroreclamodte' in url:
            return Respuesta(self.reclamo)
        raise AssertionError(f'URL inesperada: {url}')


UPLOAD_OK = ('<?xml version="1.0"?><RECEPCIONDTE><RUTSENDER>7880442-4</RUTSENDER><RUTCOMPANY>97975000-5</RUTCOMPANY>'
             '<FILE>EnvioDTE.xml</FILE><TIMESTAMP>2026-10-26 10:00:00</TIMESTAMP><STATUS>0</STATUS>'
             '<TRACKID>0123456789012</TRACKID></RECEPCIONDTE>')


class ClienteSIITest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cert = Certificado.desde_pfx(pfx_de_prueba(), 'secreta')

    def test_semilla_firmada_tiene_el_formato_del_manual_y_verifica(self):
        cliente = sii.ClienteSII(self.cert, sii.CERTIFICACION, SIISimulado())
        xml = cliente.semilla_firmada('000002360958')
        self.assertTrue(xml.startswith('<?xml version="1.0"?>\n<getToken><item><Semilla>000002360958</Semilla></item>'
                                       '<Signature xmlns="http://www.w3.org/2000/09/xmldsig#">'))
        self.assertIn('<Reference URI="">', xml)
        self.assertIn('xmldsig#enveloped-signature', xml)
        raiz = etree.fromstring(xml.split('\n', 1)[1].encode())
        self.assertEqual(firma.verificar(raiz), [('', True, '')])

    def test_token_se_pide_una_vez_y_se_reutiliza(self):
        sim = SIISimulado()
        cliente = sii.ClienteSII(self.cert, sii.CERTIFICACION, sim)
        self.assertEqual(cliente.token(), 'TOKEN1')
        self.assertEqual(cliente.token(), 'TOKEN1')
        self.assertEqual([p['url'] for p in sim.pedidos], ['https://maullin.sii.cl/DTEWS/CrSeed.jws',
                                                           'https://maullin.sii.cl/DTEWS/GetTokenFromSeed.jws'])
        # La semilla firmada viaja escapada dentro de pszXml.
        self.assertIn(b'<pszXml xsi:type="xsd:string">&lt;?xml version="1.0"?&gt;', sim.pedidos[1]['data'])

    def test_produccion_va_a_palena(self):
        sim = SIISimulado()
        sii.ClienteSII(self.cert, sii.PRODUCCION, sim).token()
        self.assertTrue(sim.pedidos[0]['url'].startswith('https://palena.sii.cl/'))

    def test_certificado_sin_autenticacion_habilitada(self):
        class Sim(SIISimulado):
            def post(self, url, **kw):
                if url.endswith('GetTokenFromSeed.jws'):
                    return Respuesta(_sobre('getToken', _token('', '-07')))
                return super().post(url, **kw)
        with self.assertRaisesRegex(sii.ErrorSII, 'autenticación con certificado'):
            sii.ClienteSII(self.cert, sii.CERTIFICACION, Sim()).token()

    def test_upload_manda_los_campos_y_la_cookie(self):
        sim = SIISimulado(upload=UPLOAD_OK)
        r = sii.ClienteSII(self.cert, sii.CERTIFICACION, sim).enviar(b'<EnvioDTE/>', '97.975.000-5')
        self.assertEqual(r.trackid, '0123456789012')
        pedido = sim.pedidos[-1]
        self.assertEqual(pedido['url'], 'https://maullin.sii.cl/cgi_dte/UPL/DTEUpload')
        self.assertEqual([c[0] for c in pedido['files']], ['rutSender', 'dvSender', 'rutCompany', 'dvCompany', 'archivo'])
        self.assertEqual([c[1][1] for c in pedido['files'][:4]], ['7880442', '4', '97975000', '5'])
        self.assertEqual(pedido['headers']['Cookie'], 'TOKEN=TOKEN1')
        self.assertIn('PROG 1.0', pedido['headers']['User-Agent'])

    def test_upload_rechazado_por_esquema(self):
        malo = ('<?xml version="1.0"?><RECEPCIONDTE><STATUS>7</STATUS><DETAIL><ERROR>Element Folio: invalid</ERROR>'
                '</DETAIL></RECEPCIONDTE>')
        with self.assertRaisesRegex(sii.ErrorSII, 'esquema.*Element Folio'):
            sii.ClienteSII(self.cert, sii.CERTIFICACION, SIISimulado(upload=malo)).enviar(b'x', '97975000-5')

    def test_upload_con_token_vencido_renueva_y_reintenta(self):
        vencido = '<?xml version="1.0"?><RECEPCIONDTE><STATUS>5</STATUS></RECEPCIONDTE>'
        sim = SIISimulado(upload=[vencido, UPLOAD_OK], tokens=('VIEJO', 'NUEVO'))
        r = sii.ClienteSII(self.cert, sii.CERTIFICACION, sim).enviar(b'x', '97975000-5')
        self.assertTrue(r.ok)
        cookies = [p['headers']['Cookie'] for p in sim.pedidos if p['url'].endswith('DTEUpload')]
        self.assertEqual(cookies, ['TOKEN=VIEJO', 'TOKEN=NUEVO'])

    def test_estado_envio_procesado_con_resumen_por_tipo(self):
        estup = ('<SII:RESPUESTA xmlns:SII="http://www.sii.cl/XMLSchema"><SII:RESP_HDR><TRACKID>251</TRACKID>'
                 '<ESTADO>EPR</ESTADO><GLOSA>Envio Procesado</GLOSA></SII:RESP_HDR><SII:RESP_BODY>'
                 '<TIPO_DOCTO>33</TIPO_DOCTO><INFORMADOS>2</INFORMADOS><ACEPTADOS>1</ACEPTADOS>'
                 '<RECHAZADOS>1</RECHAZADOS><REPAROS>0</REPAROS>'
                 '<TIPO_DOCTO>61</TIPO_DOCTO><INFORMADOS>1</INFORMADOS><ACEPTADOS>1</ACEPTADOS>'
                 '<RECHAZADOS>0</RECHAZADOS><REPAROS>0</REPAROS></SII:RESP_BODY></SII:RESPUESTA>')
        sim = SIISimulado(estup=estup)
        r = sii.ClienteSII(self.cert, sii.CERTIFICACION, sim).estado_envio('97975000-5', '251')
        self.assertTrue(r.final)
        self.assertTrue(r.rechazado)
        self.assertEqual(r.resumen, [
            {'tipo': '33', 'informados': 2, 'aceptados': 1, 'rechazados': 1, 'reparos': 0},
            {'tipo': '61', 'informados': 1, 'aceptados': 1, 'rechazados': 0, 'reparos': 0}])
        self.assertIn(b'<RutCompania xsi:type="xsd:string">97975000</RutCompania>', sim.pedidos[-1]['data'])

    def test_estado_envio_en_proceso_no_es_final(self):
        estup = ('<SII:RESPUESTA xmlns:SII="http://www.sii.cl/XMLSchema"><SII:RESP_HDR><ESTADO>SOK</ESTADO>'
                 '</SII:RESP_HDR></SII:RESPUESTA>')
        r = sii.ClienteSII(self.cert, sii.CERTIFICACION, SIISimulado(estup=estup)).estado_envio('97975000-5', '9')
        self.assertFalse(r.final)

    def test_estado_dte_usa_fecha_ddmmaaaa(self):
        estdte = ('<SII:RESPUESTA xmlns:SII="http://www.sii.cl/XMLSchema"><SII:RESP_HDR><ESTADO>DOK</ESTADO>'
                  '<GLOSA>Documento Recibido por el SII. Datos Coinciden con los Registrados</GLOSA>'
                  '<ERR_CODE>0</ERR_CODE></SII:RESP_HDR></SII:RESPUESTA>')
        sim = SIISimulado(estdte=estdte)
        r = sii.ClienteSII(self.cert, sii.CERTIFICACION, sim).estado_dte(
            '97975000-5', '77777777-7', 33, 60, date(2026, 10, 13), 119000)
        self.assertEqual(r['estado'], 'DOK')
        self.assertIn(b'<FechaEmisionDte xsi:type="xsd:string">13102026</FechaEmisionDte>', sim.pedidos[-1]['data'])

    def test_reclamo_solo_facturas_y_lee_respuesta(self):
        resp = ('<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body>'
                '<ns2:ingresarAceptacionReclamoDocResponse xmlns:ns2="http://ws.registroreclamodte.diii.sdi.sii.cl">'
                '<return><codResp>0</codResp><descResp>Accion Completada OK</descResp></return>'
                '</ns2:ingresarAceptacionReclamoDocResponse></soap:Body></soap:Envelope>')
        sim = SIISimulado(reclamo=resp)
        cliente = sii.ClienteSII(self.cert, sii.CERTIFICACION, sim)
        r = cliente.aceptar_o_reclamar('97975000-5', 33, 60, sii.ACEPTA_CONTENIDO)
        self.assertEqual(r['codigo'], 0)
        self.assertTrue(sim.pedidos[-1]['url'].startswith('https://ws2.sii.cl/WSREGISTRORECLAMODTECERT'))
        self.assertIn(b'<accionDoc>ACD</accionDoc>', sim.pedidos[-1]['data'])
        with self.assertRaisesRegex(sii.ErrorSII, 'solo registra'):
            cliente.aceptar_o_reclamar('97975000-5', 61, 3, sii.ACEPTA_CONTENIDO)


if __name__ == '__main__':
    unittest.main()

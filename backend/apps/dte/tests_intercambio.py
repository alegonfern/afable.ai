"""El intercambio con clientes y proveedores (intercambio.py y nucleo/respuesta.py), con base de
datos, SII simulado y casilla IMAP simulada.

Un "proveedor" ficticio emite con su propio CAF y certificado un EnvioDTE dirigido a la empresa:
así lo que se recibe es exactamente lo que produce un emisor real con el mismo núcleo.
"""
import email.message
from datetime import date, datetime
from unittest import mock

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from apps.finanzas.models import Contacto, DocumentoTributario

from . import intercambio, motor, sii
from .models import ConfiguracionDTE, DocumentoEmitido, DocumentoRecibido, EnvioSII
from .nucleo import ErrorDTE, documento as d, envio, firma
from .nucleo.caf import Caf as CafNucleo
from .nucleo.certificado import Certificado
from .nucleo.esquemas import validar
from .nucleo.xmlutil import SII, leer
from .tests import SIIFalso, _BaseDTE, caf_de_prueba
from .tests_nucleo import pfx_de_prueba

PROVEEDOR = '96874030-K'
NS = {'s': SII}


def envio_del_proveedor(rut_receptor='76000000-0', folio=15, total_neto=10000):
    """Un EnvioDTE firmado por el proveedor, como llegaría a la casilla de la empresa."""
    cert = Certificado.desde_pfx(pfx_de_prueba('5126663-3'), 'secreta')
    caf = CafNucleo(caf_de_prueba(PROVEEDOR, desde=1, hasta=100))
    emisor = d.Emisor(rut=PROVEEDOR, razon_social='Cementos del Sur SpA', giro='Venta de cemento', actecos=['466300'],
                      direccion='Camino Real 100', comuna='Puente Alto')
    receptor = d.Receptor(rut=rut_receptor, razon_social='Ferretería Ejemplo', giro='Ferretería',
                          direccion='Av. Siempre Viva 742', comuna='Providencia')
    doc = d.Documento(tipo=33, folio=folio, fecha=date(2026, 10, 20), emisor=emisor, receptor=receptor,
                      lineas=[d.Linea('Saco de cemento', cantidad=1, precio=total_neto)])
    dte = d.construir(doc, caf)
    return envio.armar([dte], envio.Caratula(rut_emisor=PROVEEDOR, rut_envia='5126663-3',
                                             fecha_resolucion=date(2014, 8, 22), numero_resolucion=80,
                                             rut_receptor=rut_receptor), cert)


class SIIReclamos(SIIFalso):
    def __init__(self, codigo=0):
        super().__init__()
        self.codigo, self.acciones = codigo, []

    def aceptar_o_reclamar(self, rut_emisor, tipo, folio, accion):
        self.acciones.append(accion)
        return {'codigo': self.codigo, 'descripcion': 'Accion Completada OK' if self.codigo == 0 else 'Plazo vencido',
                'eventos': []}


class RecibirTests(_BaseDTE):
    def setUp(self):
        super().setUp()
        self._alta()  # la empresa necesita su certificado para firmar el acuse

    def test_recibe_valida_registra_en_compras_y_acusa(self):
        r = intercambio.recibir(self.org, envio_del_proveedor(), DocumentoRecibido.MANUAL)
        self.assertEqual(r['estado_envio'], 0)
        [x] = r['recibidos']
        self.assertEqual((x.tipo, x.folio, x.emisor_rut, x.monto_total), (33, 15, PROVEEDOR, 11900))
        self.assertTrue(x.esquema_ok and x.firma_ok and x.timbre_ok, x.observaciones)
        dt = x.documento_tributario
        self.assertEqual((dt.libro, dt.tipo_documento, dt.folio, dt.rut, dt.monto_iva), ('compras', '33', '15', PROVEEDOR, 1900))
        # El XML guardado suelto conserva la firma del proveedor.
        self.assertTrue(all(ok for _, ok, _ in firma.verificar(leer(x.xml.encode('iso-8859-1')))))
        # El acuse cumple el esquema, está firmado y dice "recibido conforme".
        acuse = leer(r['acuse'])
        self.assertEqual(validar(acuse, 'RespuestaDTE'), [])
        self.assertTrue(all(ok for _, ok, _ in firma.verificar(acuse)))
        self.assertEqual(acuse.findtext('.//s:EstadoRecepEnv', namespaces=NS), '0')
        self.assertEqual(acuse.findtext('.//s:RecepcionDTE/s:EstadoRecepDTE', namespaces=NS), '0')
        self.assertEqual(acuse.findtext('.//s:RutResponde', namespaces=NS), '76000000-0')
        self.assertTrue(acuse.findtext('.//s:Digest', namespaces=NS))

    def test_no_se_duplica(self):
        datos = envio_del_proveedor()
        intercambio.recibir(self.org, datos)
        r = intercambio.recibir(self.org, datos)
        self.assertEqual(r['recibidos'], [])
        self.assertIn('ya se había recibido', r['ignorados'][0])
        self.assertEqual(DocumentoRecibido.objects.count(), 1)
        self.assertEqual(leer(r['acuse']).findtext('.//s:EstadoRecepDTE', namespaces=NS), '4')

    def test_si_ya_estaba_por_el_rcv_se_enlaza(self):
        previo = DocumentoTributario.objects.create(organization=self.org, libro='compras', tipo_documento='33',
                                                    folio='15', rut=PROVEEDOR, fecha=date(2026, 10, 20), monto_total=11900)
        [x] = intercambio.recibir(self.org, envio_del_proveedor())['recibidos']
        self.assertEqual(x.documento_tributario_id, previo.id)
        self.assertEqual(DocumentoTributario.objects.filter(libro='compras').count(), 1)

    def test_dirigido_a_otra_empresa(self):
        r = intercambio.recibir(self.org, envio_del_proveedor(rut_receptor='77111222-6'))
        self.assertEqual(r['estado_envio'], 3)
        self.assertEqual(r['recibidos'], [])
        self.assertFalse(DocumentoRecibido.objects.exists())

    def test_adulterado_queda_con_la_firma_mala(self):
        datos = envio_del_proveedor().replace(b'<MntTotal>11900</MntTotal>', b'<MntTotal>11901</MntTotal>')
        r = intercambio.recibir(self.org, datos)
        self.assertEqual(r['estado_envio'], 2)
        [x] = r['recibidos']
        self.assertFalse(x.firma_ok)
        self.assertIn('firma', x.observaciones)

    def test_lo_que_no_es_un_envio(self):
        with self.assertRaisesMessage(ErrorDTE, 'EnvioDTE'):
            intercambio.recibir(self.org, b'<?xml version="1.0"?><RespuestaDTE/>')
        with self.assertRaisesMessage(ErrorDTE, 'XML'):
            intercambio.recibir(self.org, b'esto no es xml')


class ResponderTests(_BaseDTE):
    def setUp(self):
        super().setUp()
        self._alta()
        Contacto.objects.create(organization=self.org, rut=PROVEEDOR, razon_social='Cementos del Sur SpA',
                                es_proveedor=True, email='dte@cementos.test')
        [self.recibido] = intercambio.recibir(self.org, envio_del_proveedor())['recibidos']

    def test_aceptar_registra_en_el_sii_y_manda_resultado_y_recibo(self):
        falso = SIIReclamos()
        with mock.patch.object(motor, 'cliente', return_value=falso):
            r = intercambio.aceptar(self.recibido, self.editor, recibo_mercaderias=True, recinto='Bodega central')
        self.assertEqual(falso.acciones, [sii.ACEPTA_CONTENIDO, sii.RECIBO_MERCADERIAS])
        self.recibido.refresh_from_db()
        self.assertEqual(self.recibido.estado, DocumentoRecibido.ACEPTADO)
        self.assertIn('ACD', self.recibido.respuesta_sii)
        for xml, esquema in ((r['resultado'], 'RespuestaDTE'), (r['recibos'], 'EnvioRecibos')):
            raiz = leer(xml)
            self.assertEqual(validar(raiz, esquema), [])
            self.assertTrue(all(ok for _, ok, _ in firma.verificar(raiz)))
        self.assertEqual(len(firma.verificar(leer(r['recibos']))), 2)  # doble firma
        self.assertEqual(leer(r['resultado']).findtext('.//s:EstadoDTE', namespaces=NS), '0')
        [correo] = mail.outbox
        self.assertEqual(correo.to, ['dte@cementos.test'])
        self.assertEqual(len(correo.attachments), 2)

    def test_reclamar_cita_la_ley_y_queda_reclamado(self):
        falso = SIIReclamos()
        with mock.patch.object(motor, 'cliente', return_value=falso):
            r = intercambio.reclamar(self.recibido, 'Precio distinto al pactado', self.editor)
        self.assertEqual(falso.acciones, [sii.RECLAMA_CONTENIDO])
        raiz = leer(r['resultado'])
        self.assertEqual(raiz.findtext('.//s:EstadoDTE', namespaces=NS), '2')
        self.assertIn('Ley 19.983', raiz.findtext('.//s:EstadoDTEGlosa', namespaces=NS))
        self.recibido.refresh_from_db()
        self.assertEqual(self.recibido.estado, DocumentoRecibido.RECLAMADO)
        with self.assertRaisesMessage(ErrorDTE, 'ya está reclamado'):
            intercambio.aceptar(self.recibido)

    def test_si_el_sii_no_lo_registra_no_cambia_nada(self):
        with mock.patch.object(motor, 'cliente', return_value=SIIReclamos(codigo=8)):
            with self.assertRaisesMessage(ErrorDTE, 'Plazo vencido'):
                intercambio.reclamar(self.recibido, 'Tarde', self.editor)
        self.recibido.refresh_from_db()
        self.assertEqual(self.recibido.estado, DocumentoRecibido.RECIBIDO)
        self.assertEqual(mail.outbox, [])


class EnviarAClienteTests(_BaseDTE):
    def setUp(self):
        super().setUp()
        self._alta()
        from apps.comercial import emision
        with mock.patch.object(motor, 'cliente', return_value=SIIFalso()):
            emision.emitir(self._orden(), usuario=self.editor)
        self.emitido = DocumentoEmitido.objects.get(organization=self.org)

    def test_en_certificacion_no_se_le_escribe_al_cliente(self):
        self.assertIsNone(intercambio.enviar_a_cliente(self.emitido))
        self.assertEqual(mail.outbox, [])

    def test_forzado_manda_el_envio_con_el_rut_del_cliente(self):
        para = intercambio.enviar_a_cliente(self.emitido, forzar=True)
        self.assertEqual(para, 'compras@andes.test')
        [correo] = mail.outbox
        nombre, xml, tipo = correo.attachments[0]
        self.assertTrue(nombre.startswith('EnvioDTE_76000000-0_T33F1'))
        raiz = leer(xml)
        self.assertEqual(raiz.findtext('.//s:RutReceptor', namespaces=NS), '77111222-6')
        self.assertEqual(validar(raiz, 'EnvioDTE'), [])
        # La firma original del DTE se respeta y la del nuevo envío también verifica.
        self.assertEqual([ok for _, ok, _ in firma.verificar(raiz)], [True, True])

    def test_el_motor_lo_manda_cuando_el_sii_acepta(self):
        EnvioSII.objects.update(estado=EnvioSII.SUBIDO, trackid='1', siguiente_intento='2026-01-01T00:00:00Z')
        with mock.patch.object(motor, 'cliente', return_value=SIIFalso('EPR')), \
                mock.patch.object(intercambio, 'enviar_a_cliente') as enviar:
            motor.procesar()
        enviar.assert_called_once()
        self.assertEqual(enviar.call_args[0][0].pk, self.emitido.pk)

    def test_api_reenviar_a_otro_correo(self):
        r = self.client.post(f'{self.dte}/documentos/{self.emitido.id}/enviar-a-cliente/',
                             {'correo': 'otra@andes.test'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(mail.outbox[0].to, ['otra@andes.test'])


class _IMAPFalso:
    """Lo que usa revisar_casilla de imaplib.IMAP4_SSL, con un correo no leído."""

    def __init__(self, crudo):
        self.crudo, self.marcados = crudo, []

    def __call__(self, servidor, puerto, timeout=None):
        self.servidor = servidor
        return self

    def login(self, usuario, clave):
        if clave != 'clave-imap':
            import imaplib
            raise imaplib.IMAP4.error('AUTHENTICATIONFAILED')

    def select(self, buzon, readonly=False):
        return 'OK', [b'1']

    def search(self, charset, criterio):
        return 'OK', [b'1']

    def fetch(self, num, partes):
        return 'OK', [(b'1 (RFC822 {%d}' % len(self.crudo), self.crudo), b')']

    def store(self, num, accion, bandera):
        self.marcados.append(num)

    def logout(self):
        pass


class CasillaTests(_BaseDTE):
    def setUp(self):
        super().setUp()
        self._alta()
        self.client.force_authenticate(self.admin)
        r = self.client.put(f'{self.dte}/casilla/', {'imap_servidor': 'imap.empresa.test', 'imap_usuario': 'dte@empresa.test',
                                                    'clave': 'clave-imap', 'correo_intercambio': 'dte@empresa.test'},
                            format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.data['tiene_clave'])
        self.assertNotIn('clave', r.data)

    def _correo(self):
        m = email.message.EmailMessage()
        m['From'] = 'Cementos del Sur <dte@cementos.test>'
        m['Subject'] = 'Factura 15'
        m.set_content('Adjuntamos factura')
        m.add_attachment(envio_del_proveedor(), maintype='application', subtype='xml', filename='EnvioDTE_15.xml')
        return m.as_bytes()

    def test_revisa_la_casilla_recibe_y_acusa(self):
        falso = _IMAPFalso(self._correo())
        with mock.patch('imaplib.IMAP4_SSL', falso):
            n = intercambio.revisar_casilla(self.org)
        self.assertEqual(n, 1)
        x = DocumentoRecibido.objects.get()
        self.assertEqual((x.origen, x.correo_de), ('correo', 'dte@cementos.test'))
        self.assertIsNotNone(x.acuse_enviado_en)
        self.assertEqual(falso.marcados, [b'1'])
        self.assertEqual(mail.outbox[0].to, ['dte@cementos.test'])
        self.assertTrue(mail.outbox[0].attachments[0][0].startswith('RespuestaDTE_'))

    def test_procesar_casillas_respeta_los_15_minutos(self):
        falso = _IMAPFalso(self._correo())
        with mock.patch('imaplib.IMAP4_SSL', falso):
            self.assertEqual(intercambio.procesar_casillas(), 1)
            self.assertEqual(intercambio.procesar_casillas(), 0)

    def test_clave_mala_queda_anotada(self):
        self.client.put(f'{self.dte}/casilla/', {'clave': 'otra'}, format='json')
        with mock.patch('imaplib.IMAP4_SSL', _IMAPFalso(b'')):
            r = self.client.post(f'{self.dte}/casilla/probar/')
        self.assertEqual(r.status_code, 400)
        self.assertIn('No se pudo entrar', r.data['detail'])


class ApiRecibidosTests(_BaseDTE):
    def setUp(self):
        super().setUp()
        self._alta()

    def test_subir_listar_y_bajar_el_xml(self):
        r = self.client.post(f'{self.dte}/recibidos/subir/', {
            'archivo': SimpleUploadedFile('EnvioDTE.xml', envio_del_proveedor())})
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data['recibidos'][0]['folio'], 15)
        self.assertTrue(r.data['acuse'])
        lista = self.client.get(f'{self.dte}/recibidos/').data
        self.assertEqual(lista[0]['emisor_rut'], PROVEEDOR)
        r = self.client.get(f'{self.dte}/recibidos/{lista[0]["id"]}/xml/')
        self.assertTrue(r.content.startswith(b'<?xml version="1.0" encoding="ISO-8859-1"?>'))

    def test_el_miembro_solo_mira(self):
        self.client.force_authenticate(self.miembro)
        r = self.client.post(f'{self.dte}/recibidos/subir/', {
            'archivo': SimpleUploadedFile('EnvioDTE.xml', envio_del_proveedor())})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.client.get(f'{self.dte}/recibidos/').status_code, 200)


class RespuestasCertificacionTests(_BaseDTE):
    """El paso de intercambio de la certificación: los tres archivos de respuesta, válidos, y sin
    tocar Compras (son documentos de prueba)."""

    def setUp(self):
        super().setUp()
        self._alta(activar=False)

    def test_responde_los_tres_archivos_y_no_registra_compras(self):
        from .intercambio import respuestas_certificacion
        archivos = respuestas_certificacion(self.org, envio_del_proveedor())
        self.assertEqual(sorted(archivos), ['EnvioRecibos.xml', 'RespuestaEnvio.xml', 'ResultadoDTE.xml'])
        for nombre, datos in archivos.items():
            raiz = leer(datos)
            self.assertTrue(all(ok for _, ok, _ in firma.verificar(raiz)), nombre)
        self.assertFalse(DocumentoRecibido.objects.exists())


@override_settings(DTE_CORREO_DOMINIO='dte.afable.test', DTE_CORREO_SECRETO='s3creto')
class CasillaAfableTests(_BaseDTE):
    """La casilla de intercambio de Afable: la dirección de cada empresa y el correo entrante que
    reenvía el proveedor (MIME crudo o formulario), sin depender de cuál sea."""

    URL = '/api/v1/dte/correo-entrante/s3creto/'
    DIRECCION = 'dte-76000000-0@dte.afable.test'

    def setUp(self):
        super().setUp()
        self._alta()
        self.client.force_authenticate(self.admin)
        r = self.client.put(f'{self.dte}/casilla/', {'casilla_afable': True}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.client.force_authenticate(None)

    def _correo(self, para=None):
        m = email.message.EmailMessage()
        m['From'] = 'Cementos del Sur <dte@cementos.test>'
        m['To'] = para or self.DIRECCION
        m['Subject'] = 'Factura 15'
        m.set_content('Adjuntamos factura')
        m.add_attachment(envio_del_proveedor(), maintype='application', subtype='xml', filename='EnvioDTE_15.xml')
        return m.as_bytes()

    def test_la_casilla_queda_como_correo_de_intercambio(self):
        self.client.force_authenticate(self.admin)
        r = self.client.get(f'{self.dte}/casilla/')
        self.assertTrue(r.data['casilla_afable_disponible'])
        self.assertEqual((r.data['direccion_afable'], r.data['correo_intercambio']), (self.DIRECCION, self.DIRECCION))
        r = self.client.put(f'{self.dte}/casilla/', {'casilla_afable': False}, format='json')
        self.assertEqual((r.data['casilla_afable'], r.data['correo_intercambio']), (False, ''))

    def test_mime_crudo_registra_el_documento_y_acusa_desde_la_casilla(self):
        r = self.client.generic('POST', self.URL, self._correo(), content_type='message/rfc822')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['recibidos'], 1)
        x = DocumentoRecibido.objects.get()
        self.assertEqual((x.origen, x.correo_de, x.folio), ('correo', 'dte@cementos.test', 15))
        self.assertEqual(mail.outbox[0].from_email, self.DIRECCION)
        self.assertEqual(mail.outbox[0].to, ['dte@cementos.test'])

    def test_formulario_con_el_mime_y_el_sobre(self):
        # Como SendGrid Inbound Parse en modo "raw": el MIME en un campo y el sobre aparte. El
        # encabezado To es otro (una lista), el destinatario real viene en el sobre.
        crudo = self._correo(para='lista@proveedor.test')
        r = self.client.post(self.URL, {'email': SimpleUploadedFile('mensaje.eml', crudo, 'message/rfc822'),
                                        'envelope': '{"to": ["%s"], "from": "dte@cementos.test"}' % self.DIRECCION})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['recibidos'], 1)

    def test_secreto_malo(self):
        r = self.client.generic('POST', '/api/v1/dte/correo-entrante/otro/', self._correo(), content_type='message/rfc822')
        self.assertEqual(r.status_code, 403)
        self.assertFalse(DocumentoRecibido.objects.exists())

    def test_empresa_sin_la_casilla_de_afable_no_recibe(self):
        ConfiguracionDTE.objects.filter(organization=self.org).update(casilla_afable=False)
        r = self.client.generic('POST', self.URL, self._correo(), content_type='message/rfc822')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['recibidos'], 0)
        self.assertFalse(DocumentoRecibido.objects.exists())

    def test_sin_dominio_no_existe(self):
        with override_settings(DTE_CORREO_DOMINIO=''):
            r = self.client.generic('POST', self.URL, self._correo(), content_type='message/rfc822')
        self.assertEqual(r.status_code, 404)

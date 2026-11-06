"""El facturador nativo de punta a punta, con base de datos y un SII simulado: el alta de la
empresa por la API, los permisos, los folios, emitir desde una orden de venta y el motor que
sube y consulta (aceptado y rechazado)."""
import base64
from datetime import date
from unittest import mock

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from apps.comercial import emision, facturacion
from apps.comercial.models import ConfiguracionComercial, Pedido
from apps.comercial.tests import _Base
from apps.comercial.tests_facturar import configurar_emisor
from apps.finanzas.models import DocumentoTributario
from apps.notificaciones.models import Notificacion

from . import motor, servicio, sii
from .models import Caf, ConfiguracionDTE, DocumentoEmitido, EnvioSII
from .nucleo import ErrorDTE, envio as nucleo_envio, firma, ted
from .nucleo.xmlutil import SII, leer
from .tests_nucleo import pfx_de_prueba


def caf_de_prueba(rut, tipo=33, desde=1, hasta=50, idk=100):
    """Un CAF con la forma del SII para cualquier RUT (la firma FRMA del SII es de relleno: el
    núcleo no la verifica)."""
    llave = rsa.generate_private_key(public_exponent=3, key_size=1024)
    n = llave.public_key().public_numbers().n
    m = base64.b64encode(n.to_bytes((n.bit_length() + 7) // 8, 'big')).decode()
    pem = llave.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                              serialization.NoEncryption()).decode()
    return (f'<?xml version="1.0"?>\n<AUTORIZACION>\n<CAF version="1.0">\n<DA>\n<RE>{rut}</RE>\n<RS>EMPRESA DE PRUEBA</RS>\n'
            f'<TD>{tipo}</TD>\n<RNG><D>{desde}</D><H>{hasta}</H></RNG>\n<FA>2026-10-01</FA>\n'
            f'<RSAPK><M>{m}</M><E>Aw==</E></RSAPK>\n<IDK>{idk}</IDK>\n</DA>\n'
            f'<FRMA algoritmo="SHA1withRSA">AAAA</FRMA>\n</CAF>\n<RSASK>{pem}</RSASK>\n</AUTORIZACION>\n').encode()


class SIIFalso:
    """Lo que necesita el motor del cliente del SII, con respuestas fijas."""

    def __init__(self, estado='EPR', rechazados=0, reparos=0, falla_upload=None):
        self.estado, self.rechazados, self.reparos, self.falla_upload = estado, rechazados, reparos, falla_upload
        self.subidos = []

    def enviar(self, xml, rut_empresa, nombre=''):
        if self.falla_upload:
            raise self.falla_upload
        self.subidos.append(xml)
        return sii.RespuestaEnvio(status=0, trackid='9876543210', xml='<RECEPCIONDTE/>')

    def estado_envio(self, rut, trackid):
        resumen = [] if self.estado != 'EPR' else [{'tipo': '33', 'informados': 1, 'aceptados': 1 - self.rechazados,
                                                    'rechazados': self.rechazados, 'reparos': self.reparos}]
        return sii.EstadoEnvio(estado=self.estado, glosa='', resumen=resumen, xml='<RESPUESTA/>')


@override_settings(DTE_NATIVO='on')
class _BaseDTE(_Base):
    def setUp(self):
        super().setUp()
        configurar_emisor(self.org)
        self.dte = f'/api/v1/workspaces/{self.org.slug}/dte'
        # El RUT de las pruebas de Ventas (77111222-3) tiene mal el dígito: el SII no lo aceptaría.
        self.cliente.rut = '77111222-6'
        self.cliente.giro, self.cliente.direccion, self.cliente.comuna = 'Construcción', 'Los Militares 5001', 'Las Condes'
        self.cliente.save()

    def _alta(self, ambiente=sii.CERTIFICACION, activar=True):
        """La empresa completa el asistente por la API, como lo haría desde la pantalla."""
        self.client.force_authenticate(self.admin)
        r = self.client.put(f'{self.dte}/configuracion/', {'camino': 'certificar', 'actecos': ['475200'],
                                                          'certificacion_fecha': '2026-10-20'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        r = self.client.post(f'{self.dte}/certificado/', {
            'archivo': SimpleUploadedFile('firma.pfx', pfx_de_prueba('11111111-1')), 'clave': 'secreta'})
        self.assertEqual(r.status_code, 201, r.content)
        r = self.client.post(f'{self.dte}/cafs/', {
            'archivo': SimpleUploadedFile('caf33.xml', caf_de_prueba('76000000-0'))})
        self.assertEqual(r.status_code, 201, r.content)
        if activar:
            r = self.client.post(f'{self.dte}/activar/', {'ambiente': ambiente}, format='json')
            self.assertEqual(r.status_code, 200, r.content)
        self.client.force_authenticate(self.editor)

    def _orden(self):
        p = self._cotizacion()
        self.assertEqual(self._accion(p['id'], 'confirmar').status_code, 200)
        return Pedido.objects.get(pk=p['id'])


class AltaTests(_BaseDTE):
    def test_apagado_nadie_lo_ve(self):
        with override_settings(DTE_NATIVO='off'):
            r = self.client.get(f'{self.dte}/estado/')
            self.assertEqual(r.status_code, 200)
            self.assertFalse(r.data['disponible'])
            self.client.force_authenticate(self.admin)
            self.assertEqual(self.client.get(f'{self.dte}/cafs/').status_code, 403)

    def test_piloto_solo_para_las_empresas_de_la_lista(self):
        with override_settings(DTE_NATIVO='piloto', DTE_PILOTO=['otra-cosa']):
            self.assertFalse(servicio.disponible(self.org))
        with override_settings(DTE_NATIVO='piloto', DTE_PILOTO=[self.org.slug]):
            self.assertTrue(servicio.disponible(self.org))

    def test_el_asistente_dice_que_falta_paso_a_paso(self):
        r = self.client.get(f'{self.dte}/estado/')
        pasos = {p['clave']: p for p in r.data['pasos']}
        self.assertFalse(r.data['listo'])
        self.assertIn('la actividad económica (código del SII)', pasos['empresa']['falta'])
        self.assertFalse(pasos['certificado']['listo'])
        self._alta(activar=False)
        r = self.client.get(f'{self.dte}/estado/')
        self.assertTrue(r.data['listo'], r.data['pasos'])
        self.assertEqual(r.data['certificado']['rut'], '11111111-1')
        self.assertEqual(r.data['folios'][0], {'tipo': 33, 'nombre': 'Factura electrónica', 'disponibles': 50})

    def test_activar_deja_a_ventas_emitiendo_con_el_sii(self):
        self._alta()
        cfg = ConfiguracionDTE.de(self.org)
        self.assertEqual((cfg.ambiente, cfg.activo), (sii.CERTIFICACION, True))
        self.assertEqual(ConfiguracionComercial.de(self.org).proveedor_dte, 'sii')
        self.client.force_authenticate(self.admin)
        self.client.post(f'{self.dte}/desactivar/')
        self.assertEqual(ConfiguracionComercial.de(self.org).proveedor_dte, '')

    def test_no_se_activa_a_medias(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'{self.dte}/activar/', {'ambiente': sii.CERTIFICACION}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('certificado digital', r.data['detail'])

    def test_certificado_y_folios_solo_del_administrador(self):
        r = self.client.post(f'{self.dte}/certificado/', {
            'archivo': SimpleUploadedFile('f.pfx', pfx_de_prueba()), 'clave': 'secreta'})
        self.assertEqual(r.status_code, 403)
        self.client.force_authenticate(self.ajeno)
        self.assertEqual(self.client.get(f'{self.dte}/estado/').status_code, 404)

    def test_clave_incorrecta_se_explica(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'{self.dte}/certificado/', {
            'archivo': SimpleUploadedFile('f.pfx', pfx_de_prueba()), 'clave': 'mala'})
        self.assertEqual(r.status_code, 400)
        self.assertIn('clave no es correcta', r.data['detail'])

    def test_caf_de_otra_empresa_o_que_se_cruza(self):
        with self.assertRaisesMessage(ErrorDTE, 'es del RUT 97975000-5'):
            servicio.cargar_caf(self.org, caf_de_prueba('97975000-5'))
        servicio.cargar_caf(self.org, caf_de_prueba('76000000-0', desde=1, hasta=50))
        with self.assertRaisesMessage(ErrorDTE, 'se cruza'):
            servicio.cargar_caf(self.org, caf_de_prueba('76000000-0', desde=40, hasta=90))
        produccion = servicio.cargar_caf(self.org, caf_de_prueba('76000000-0', desde=1, hasta=10, idk=300))
        self.assertEqual(produccion.ambiente, sii.PRODUCCION)

    def test_los_secretos_quedan_cifrados(self):
        self._alta(activar=False)
        caf = Caf.objects.get(organization=self.org)
        self.assertNotIn('PRIVATE KEY', caf._xml)
        self.assertEqual(caf.cargar().rut, '76000000-0')
        cert = servicio.certificado_activo(self.org)
        self.assertNotIn('secreta', cert._clave)
        self.assertEqual(cert.cargar().rut, '11111111-1')


class EmitirTests(_BaseDTE):
    def setUp(self):
        super().setUp()
        self._alta()

    def test_emitir_desde_la_orden_timbra_firma_y_deja_el_envio(self):
        p = self._orden()
        falso = SIIFalso()
        with mock.patch.object(motor, 'cliente', return_value=falso), self.captureOnCommitCallbacks(execute=True):
            doc = emision.emitir(p, usuario=self.editor)
        self.assertEqual((doc.tipo_documento, doc.folio, doc.monto_neto, doc.monto_total), ('33', '1', 80000, 95200))
        self.assertEqual(facturacion.facturado(p), p.base_clp)
        emitido = DocumentoEmitido.objects.get(organization=self.org)
        self.assertEqual((emitido.folio, emitido.documento_tributario_id), (1, doc.id))
        # Subió enseguida: queda en revisión del SII con su trackid.
        self.assertEqual(emitido.envio.estado, EnvioSII.SUBIDO)
        self.assertEqual(emitido.envio.trackid, '9876543210')
        self.assertEqual(emitido.estado, DocumentoEmitido.ENVIADO)
        # Lo que se subió cumple el esquema, sus firmas verifican y el timbre corresponde al CAF.
        caf = Caf.objects.get(organization=self.org).cargar()
        raiz = nucleo_envio.revisar(falso.subidos[0], cafs={('76000000-0', 33): caf})
        self.assertEqual(raiz.findtext(f'.//{{{SII}}}RutEnvia'), '11111111-1')
        self.assertEqual(raiz.findtext(f'.//{{{SII}}}NroResol'), '0')
        self.assertEqual(raiz.findtext(f'.//{{{SII}}}FchResol'), '2026-10-20')
        nombres = raiz.xpath('//s:Detalle/s:NmbItem/text()', namespaces={'s': SII})
        self.assertEqual(nombres, ['Saco de cemento', 'Flete'])
        # El DTE guardado suelto también verifica.
        suelto = leer(emitido.xml.encode('iso-8859-1'))
        self.assertTrue(all(ok for _, ok, _ in firma.verificar(suelto)))
        self.assertTrue(ted.verificar(suelto.find(f'.//{{{SII}}}TED'), caf))

    def test_si_el_sii_no_responde_queda_para_el_motor(self):
        falso = SIIFalso(falla_upload=sii.ErrorSII('timeout'))
        with mock.patch.object(motor, 'cliente', return_value=falso), self.captureOnCommitCallbacks(execute=True):
            emision.emitir(self._orden())
        e = EnvioSII.objects.get(organization=self.org)
        self.assertEqual(e.estado, EnvioSII.POR_SUBIR)
        self.assertEqual(e.error, 'timeout')
        self.assertIsNotNone(e.siguiente_intento)

    def test_un_error_antes_de_firmar_no_gasta_el_folio(self):
        self.cliente.giro = ''
        self.cliente.save()
        with self.assertRaisesMessage(emision.ErrorComercial, 'le falta el giro'):
            emision.emitir(self._orden())
        self.assertEqual(Caf.objects.get(organization=self.org).siguiente, 1)
        self.assertFalse(DocumentoEmitido.objects.exists())

    def test_folios_correlativos_y_se_acaban(self):
        Caf.objects.filter(organization=self.org).update(hasta=2)
        with mock.patch.object(motor, 'cliente', return_value=SIIFalso()):
            a = emision.emitir(self._orden())
            b = emision.emitir(self._orden())
            with self.assertRaisesMessage(emision.ErrorComercial, 'folios'):
                emision.emitir(self._orden())
        self.assertEqual((a.folio, b.folio), ('1', '2'))

    def test_orden_toda_exenta_sale_como_factura_exenta(self):
        servicio.cargar_caf(self.org, caf_de_prueba('76000000-0', tipo=34))
        p = self._orden()
        p.lineas.update(exento=True)
        p.recalcular()
        with mock.patch.object(motor, 'cliente', return_value=SIIFalso()):
            doc = emision.emitir(p)
        self.assertEqual((doc.tipo_documento, doc.monto_iva, doc.monto_exento), ('34', 0, 80000))


class MotorTests(_BaseDTE):
    def setUp(self):
        super().setUp()
        self._alta()
        self.pedido = self._orden()
        with mock.patch.object(motor, 'cliente', return_value=SIIFalso()), self.captureOnCommitCallbacks(execute=True):
            self.doc = emision.emitir(self.pedido, usuario=self.editor)
        self.envio = EnvioSII.objects.get(organization=self.org)
        EnvioSII.objects.update(siguiente_intento='2026-01-01T00:00:00Z')

    def test_aceptado(self):
        with mock.patch.object(motor, 'cliente', return_value=SIIFalso('EPR')):
            self.assertEqual(motor.procesar(), 1)
        self.envio.refresh_from_db()
        self.assertEqual((self.envio.estado, self.envio.estado_sii), (EnvioSII.ACEPTADO, 'EPR'))
        self.assertEqual(DocumentoEmitido.objects.get().estado, DocumentoEmitido.ACEPTADO)
        self.assertIsNone(self.envio.siguiente_intento)

    def test_con_reparos(self):
        with mock.patch.object(motor, 'cliente', return_value=SIIFalso('EPR', reparos=1)):
            motor.procesar()
        self.assertEqual(DocumentoEmitido.objects.get().estado, DocumentoEmitido.REPAROS)

    def test_en_proceso_se_vuelve_a_preguntar_mas_tarde(self):
        with mock.patch.object(motor, 'cliente', return_value=SIIFalso('SOK')):
            motor.procesar()
        self.envio.refresh_from_db()
        self.assertEqual(self.envio.estado, EnvioSII.SUBIDO)
        self.assertGreater(self.envio.siguiente_intento.year, 2025)

    def test_rechazado_sale_del_libro_y_la_orden_vuelve_a_por_facturar(self):
        with mock.patch.object(motor, 'cliente', return_value=SIIFalso('RCT')):
            motor.procesar()
        self.assertEqual(DocumentoEmitido.objects.get().estado, DocumentoEmitido.RECHAZADO)
        self.assertFalse(DocumentoTributario.objects.filter(pk=self.doc.id).exists())
        self.assertEqual(facturacion.facturado(self.pedido), 0)
        aviso = Notificacion.objects.filter(organization=self.org, user=self.editor).first()
        self.assertIn('El SII rechazó 33-1', aviso.titulo)
        # Y se puede volver a facturar, con el folio siguiente (el rechazado queda gastado).
        with mock.patch.object(motor, 'cliente', return_value=SIIFalso()):
            otra = emision.emitir(self.pedido)
        self.assertEqual(otra.folio, '2')

    def test_bitacora_y_xml(self):
        r = self.client.get(f'{self.dte}/documentos/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data[0]['folio'], 1)
        r = self.client.get(f'{self.dte}/documentos/{r.data[0]["id"]}/xml/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b'<?xml version="1.0" encoding="ISO-8859-1"?>'))
        self.assertIn('DTE_76000000-0_T33F1.xml', r['Content-Disposition'])

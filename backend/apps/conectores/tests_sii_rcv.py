"""El conector SII · Libros contables con un SII simulado: la sesión con el certificado, el resumen
y el detalle del RCV, la carga en borrador que queda en Contabilidad, las resincronizaciones y los
avisos cuando el SII no deja (sesión rechazada, reCAPTCHA)."""
from datetime import date, datetime
from unittest import mock

from django.utils import timezone

from apps.comercial.tests import _Base
from apps.dte import servicio as dte_servicio
from apps.dte.tests_nucleo import pfx_de_prueba
from apps.finanzas import importador
from apps.finanzas.models import Carga, DocumentoTributario

from . import servicio, sii_rcv
from .models import Conexion, Sincronizacion
from .servicio import ErrorConector


def con_dv(numero):
    s, m = 0, 2
    for d in reversed(str(numero)):
        s += int(d) * m
        m = 2 if m == 7 else m + 1
    dv = 11 - s % 11
    return f'{numero}-' + {11: '0', 10: 'K'}.get(dv, str(dv))


PROV_A, PROV_B = '76111222', '96555444'
COMPRAS = {
    33: [
        {'detTipoDoc': 33, 'detRutDoc': int(PROV_A), 'detDvDoc': con_dv(PROV_A)[-1], 'detRznSoc': 'Cementos Sur SpA',
         'detNroDoc': 1501, 'detFchDoc': '05/10/2026', 'detMntExe': 0, 'detMntNeto': 100000, 'detMntIVA': 19000,
         'detMntIVANoRec': 0, 'detMntTotal': 119000},
        {'detTipoDoc': 33, 'detRutDoc': int(PROV_B), 'detDvDoc': con_dv(PROV_B)[-1], 'detRznSoc': 'Ferromax Ltda',
         'detNroDoc': 88, 'detFchDoc': '2026-10-09', 'detMntExe': 5000, 'detMntNeto': 50000, 'detMntIVA': 9500,
         'detMntIVANoRec': 0, 'detMntTotal': 64500},
    ],
    61: [
        {'detRutDoc': int(PROV_A), 'detDvDoc': con_dv(PROV_A)[-1], 'detRznSoc': 'Cementos Sur SpA',
         'detNroDoc': 12, 'detFchDoc': '10/10/2026', 'detMntNeto': 10000, 'detMntIVA': 1900, 'detMntTotal': 11900},
    ],
}


class Respuesta:
    def __init__(self, status=200, json=None, text=None):
        self.status_code, self._json = status, json
        self.text = text if text is not None else ('{}' if json is not None else '')

    def json(self):
        if self._json is None:
            raise ValueError('no es JSON')
        return self._json


def sii_falso(detalle=None, ventas=None):
    """Un facadeService con respuestas fijas: compras de `detalle` y ventas de `ventas`."""
    llamadas = []

    def post(url, json=None, **kw):
        llamadas.append((url.rsplit('/', 1)[-1], json, kw))
        metodo, data = url.rsplit('/', 1)[-1], json['data']
        libro = (detalle if detalle is not None else COMPRAS) if data['operacion'] == 'COMPRA' else (ventas or {})
        if metodo == 'getResumen':
            return Respuesta(json={'data': [{'rsmnTipoDocInteger': t, 'rsmnTotDoc': len(v)} for t, v in libro.items()],
                                   'respEstado': {'codRespuesta': 0}})
        return Respuesta(json={'data': libro.get(data['codTipoDoc'], []), 'respEstado': {'codRespuesta': 0}})

    post.llamadas = llamadas
    return post


class _BaseRCV(_Base):
    def setUp(self):
        super().setUp()
        self.url = f'/api/v1/workspaces/{self.org.slug}/conectores/sii_rcv'
        p = mock.patch('apps.dte.sii.ClienteSII.token', return_value='TOKEN123')
        p.start()
        self.addCleanup(p.stop)

    def _certificado(self):
        dte_servicio.cargar_certificado(self.org, pfx_de_prueba('11111111-1'), 'secreta', self.admin)

    def _conexion(self, **config):
        self._certificado()
        return Conexion.objects.create(organization=self.org, tipo=Conexion.SII_RCV, config=config,
                                       cuenta={'rut': self.org.rut})


class RequisitosTests(_BaseRCV):
    def test_sin_certificado_no_conecta(self):
        self.assertTrue(sii_rcv.requisitos(self.org))
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'{self.url}/conectar/', {}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('certificado', r.data['detail'])

    def test_sin_rut_valido(self):
        self._certificado()
        self.org.rut = '76.000.000-5'
        self.org.save()
        self.assertEqual(len(sii_rcv.requisitos(self.org)), 1)
        self.assertIn('RUT', sii_rcv.requisitos(self.org)[0])

    def test_conectar_es_del_administrador(self):
        self._certificado()
        r = self.client.post(f'{self.url}/conectar/', {}, format='json')  # editor
        self.assertEqual(r.status_code, 403)
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'{self.url}/conectar/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['estado'], 'conectado')
        self.assertEqual(r.data['cuenta']['titular'], 'Firmante de Prueba')
        self.assertEqual(r.data['requisitos'], [])

    def test_config(self):
        self.assertEqual(sii_rcv.validar_config({'libros': ['ventas', 'otro'], 'automatico': 1}),
                         {'libros': ['ventas'], 'automatico': True})
        with self.assertRaises(ErrorConector):
            sii_rcv.validar_config({'libros': []})


class SincronizarTests(_BaseRCV):
    def _sincronizar(self, c, falso, **opciones):
        with mock.patch('apps.conectores.sii_rcv.requests.post', side_effect=falso):
            return servicio.sincronizar(c, {'periodo': '202610', **opciones}, self.editor)

    def test_deja_la_carga_de_compras_en_borrador(self):
        c = self._conexion()
        falso = sii_falso()
        resumen = self._sincronizar(c, falso)
        self.assertEqual(len(resumen['cargas']), 1)  # ventas sin movimiento: sin carga
        info = resumen['cargas'][0]
        self.assertEqual((info['libro'], info['periodo'], info['filas'], info['nuevos'], info['errores']),
                         ('compras', '202610', 3, 3, 0))
        carga = Carga.objects.get(pk=info['carga_id'])
        self.assertEqual(carga.estado, Carga.BORRADOR)
        self.assertEqual(carga.nombre_archivo, 'SII RCV compras 202610.csv')
        filas = {(f['tipo_documento'], f['folio']): f for f in carga.filas_previas}
        f = filas[(33, 88)] if (33, 88) in filas else filas[('33', '88')]
        self.assertEqual((f['rut'], f['monto_exento'], f['monto_neto'], f['monto_total'], f['fecha']),
                         (con_dv(PROV_B), 5000, 50000, 64500, '2026-10-09'))
        # La sesión va como el SII la espera.
        _, cuerpo, kw = falso.llamadas[0]
        self.assertEqual(cuerpo['metaData']['conversationId'], 'TOKEN123')
        self.assertEqual((cuerpo['data']['rutEmisor'], cuerpo['data']['dvEmisor']), ('76000000', '0'))
        self.assertIn('TOKEN=TOKEN123', kw['headers']['Cookie'])
        c.refresh_from_db()
        self.assertEqual(c.ultimo_resultado['cargas'][0]['carga_id'], carga.id)
        self.assertEqual(c.sincronizaciones.get().estado, Sincronizacion.OK)

    def test_resincronizar_reemplaza_el_borrador_y_reconoce_lo_importado(self):
        c = self._conexion()
        primera = self._sincronizar(c, sii_falso())['cargas'][0]['carga_id']
        segunda = self._sincronizar(c, sii_falso())['cargas'][0]['carga_id']
        self.assertFalse(Carga.objects.filter(pk=primera).exists())
        importador.confirmar(Carga.objects.get(pk=segunda))
        self.assertEqual(DocumentoTributario.objects.filter(organization=self.org).count(), 3)
        info = self._sincronizar(c, sii_falso())['cargas'][0]
        self.assertEqual((info['nuevos'], info['ya_estaban']), (0, 3))
        self.assertTrue(Carga.objects.filter(pk=segunda, estado=Carga.IMPORTADA).exists())

    def test_confirmar_solo(self):
        c = self._conexion(confirmar_solo=True)
        info = self._sincronizar(c, sii_falso(), libros=['compras'])['cargas'][0]
        self.assertEqual(info['estado'], Carga.IMPORTADA)
        self.assertEqual(DocumentoTributario.objects.filter(organization=self.org, libro='compras').count(), 3)

    def test_ventas(self):
        c = self._conexion()
        ventas = {33: [{'detRutDoc': 77111222, 'detDvDoc': '6', 'detRznSoc': 'Constructora Andes', 'detNroDoc': 7,
                        'detFchDoc': '2026-10-02', 'detMntNeto': 200000, 'detMntIVA': 38000, 'detMntTotal': 238000}]}
        info = self._sincronizar(c, sii_falso(detalle={}, ventas=ventas))['cargas']
        self.assertEqual([(x['libro'], x['nuevos']) for x in info], [('ventas', 1)])
        carga = Carga.objects.get(pk=info[0]['carga_id'])
        self.assertEqual(carga.libro, 'ventas')
        self.assertEqual(carga.filas_previas[0]['monto_iva'], 38000)

    def test_sesion_rechazada(self):
        c = self._conexion()
        falso = lambda url, **kw: Respuesta(status=401, text='<html><body>401</body></html>')  # noqa: E731
        with self.assertRaises(ErrorConector) as e:
            self._sincronizar(c, falso)
        self.assertEqual(str(e.exception), sii_rcv.MSG_SESION)
        c.refresh_from_db()
        self.assertEqual(c.ultimo_error, sii_rcv.MSG_SESION)
        self.assertEqual(c.sincronizaciones.get().estado, Sincronizacion.ERROR)

    def test_captcha(self):
        c = self._conexion()
        falso = lambda url, **kw: Respuesta(status=200, text='<div class="g-recaptcha"></div>')  # noqa: E731
        with self.assertRaises(ErrorConector) as e:
            self._sincronizar(c, falso)
        self.assertEqual(str(e.exception), sii_rcv.MSG_CAPTCHA)

    def test_error_del_sii(self):
        c = self._conexion()
        falso = lambda url, **kw: Respuesta(json={'data': None, 'respEstado': {'codRespuesta': 9, 'msgeRespuesta': 'Error interno'}})  # noqa: E731,E501
        with self.assertRaisesMessage(ErrorConector, 'Error interno'):
            self._sincronizar(c, falso)

    def test_por_la_api(self):
        self._conexion()
        with mock.patch('apps.conectores.sii_rcv.requests.post', side_effect=sii_falso()):
            r = self.client.post(f'{self.url}/sincronizar/', {'periodo': '2026-10'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['resumen']['cargas'][0]['nuevos'], 3)
        self.assertEqual(r.data['resumen']['enlace'], sii_rcv.ENLACE)
        self.client.force_authenticate(self.miembro)
        r = self.client.post(f'{self.url}/sincronizar/', {}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_periodo_malo(self):
        c = self._conexion()
        with self.assertRaises(ErrorConector):
            self._sincronizar(c, sii_falso(), periodo='202613')


class PeriodosYProgramaTests(_BaseRCV):
    def test_periodos(self):
        self.assertEqual(sii_rcv._periodos({}, date(2026, 10, 27)), ['202610'])
        self.assertEqual(sii_rcv._periodos({}, date(2026, 10, 5)), ['202609', '202610'])
        self.assertEqual(sii_rcv._periodos({}, date(2027, 1, 3)), ['202612', '202701'])

    def test_toca_correr_una_vez_al_dia(self):
        c = self._conexion(automatico=True)
        tz = timezone.get_current_timezone()
        temprano = timezone.make_aware(datetime(2026, 10, 27, 6, 0), tz)
        tarde = timezone.make_aware(datetime(2026, 10, 27, 9, 0), tz)
        self.assertFalse(sii_rcv.toca_correr(c, temprano))
        self.assertTrue(sii_rcv.toca_correr(c, tarde))
        c.ultima_sincronizacion = tarde
        self.assertFalse(sii_rcv.toca_correr(c, timezone.make_aware(datetime(2026, 10, 27, 20, 0), tz)))
        self.assertTrue(sii_rcv.toca_correr(c, timezone.make_aware(datetime(2026, 10, 28, 8, 0), tz)))

    def test_procesar_programadas(self):
        self._conexion(automatico=True)
        tarde = timezone.make_aware(datetime(2026, 10, 27, 9, 0), timezone.get_current_timezone())
        with mock.patch('apps.conectores.sii_rcv.requests.post', side_effect=sii_falso()), \
                mock.patch('apps.conectores.sii_rcv.timezone.localdate', return_value=date(2026, 10, 27)):
            self.assertEqual(servicio.procesar_programadas(tarde), 1)
        self.assertTrue(Carga.objects.filter(organization=self.org, nombre_archivo='SII RCV compras 202610.csv').exists())

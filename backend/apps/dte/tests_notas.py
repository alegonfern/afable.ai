"""Notas de crédito y débito sobre lo emitido por el facturador nativo."""
from unittest import mock

from apps.comercial import emision, facturacion
from apps.finanzas.models import DocumentoTributario

from . import motor, servicio
from .models import DocumentoEmitido
from .nucleo import envio as nucleo_envio, firma
from .nucleo.xmlutil import SII, leer
from .tests import SIIFalso, _BaseDTE, caf_de_prueba

NS = {'s': SII}


class NotasTests(_BaseDTE):
    def setUp(self):
        super().setUp()
        self._alta()
        servicio.cargar_caf(self.org, caf_de_prueba('76000000-0', tipo=61))
        servicio.cargar_caf(self.org, caf_de_prueba('76000000-0', tipo=56))
        self.pedido = self._orden()
        self.sii = SIIFalso()
        self.parche = mock.patch.object(motor, 'cliente', return_value=self.sii)
        self.parche.start()
        self.factura_dt = emision.emitir(self.pedido, usuario=self.editor)
        self.factura = DocumentoEmitido.objects.get(documento_tributario=self.factura_dt)

    def tearDown(self):
        self.parche.stop()
        super().tearDown()

    def _nota(self, **datos):
        return self.client.post(f'{self.dte}/documentos/{self.factura.id}/nota/', datos, format='json')

    def _xml(self, nota_id):
        return leer(DocumentoEmitido.objects.get(pk=nota_id).xml.encode('iso-8859-1'))

    def test_anular_copia_las_lineas_referencia_la_factura_y_libera_la_orden(self):
        r = self._nota(tipo=61, codigo=1, razon='Anula factura por error en el pedido')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual((r.data['tipo'], r.data['folio'], r.data['monto_total']), (61, 1, 95200))
        xml = self._xml(r.data['id'])
        self.assertEqual(xml.xpath('//s:Detalle/s:NmbItem/text()', namespaces=NS), ['Saco de cemento', 'Flete'])
        ref = xml.find('.//s:Referencia', NS)
        self.assertEqual([ref.findtext(f's:{c}', namespaces=NS) for c in ('TpoDocRef', 'FolioRef', 'CodRef')],
                         ['33', '1', '1'])
        self.assertTrue(all(ok for _, ok, _ in firma.verificar(xml)))
        nota_dt = DocumentoTributario.objects.get(tipo_documento='61', folio='1')
        self.assertEqual(nota_dt.monto_total, 95200)
        self.assertEqual(facturacion.facturado(self.pedido), 0)  # la orden queda otra vez por facturar
        # El envío al SII cumple el esquema y sus firmas verifican.
        nucleo_envio.revisar(DocumentoEmitido.objects.get(pk=r.data['id']).envio.xml.encode('iso-8859-1'))

    def test_corregir_texto_va_en_cero(self):
        r = self._nota(tipo=61, codigo=2, razon='Donde dice Las Condes debe decir Vitacura')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data['monto_total'], 0)
        xml = self._xml(r.data['id'])
        self.assertEqual(xml.findtext('.//s:MontoItem', namespaces=NS), '0')
        self.assertEqual(facturacion.facturado(self.pedido), self.pedido.base_clp)
        nucleo_envio.revisar(DocumentoEmitido.objects.get(pk=r.data['id']).envio.xml.encode('iso-8859-1'))

    def test_corregir_montos_por_una_devolucion_parcial(self):
        r = self._nota(tipo=61, codigo=3, razon='Devolución de 2 sacos',
                       lineas=[{'nombre': 'Saco de cemento', 'cantidad': 2, 'precio': 6000}])
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data['monto_total'], 14280)
        self.assertEqual(facturacion.facturado(self.pedido), self.pedido.base_clp - 12000)

    def test_nota_de_debito_que_anula_una_nota_de_credito(self):
        nc = self._nota(tipo=61, codigo=1, razon='Anula factura').data
        r = self.client.post(f'{self.dte}/documentos/{nc["id"]}/nota/',
                             {'tipo': 56, 'codigo': 1, 'razon': 'Anula la nota de crédito'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        ref = self._xml(r.data['id']).find('.//s:Referencia', NS)
        self.assertEqual(ref.findtext('s:TpoDocRef', namespaces=NS), '61')

    def test_validaciones(self):
        self.assertIn('razón', self._nota(tipo=61, codigo=1, razon='').data['detail'])
        self.assertIn('montos', self._nota(tipo=61, codigo=3, razon='x', lineas=[]).data['detail'])
        self.factura.estado = DocumentoEmitido.RECHAZADO
        self.factura.save()
        self.assertIn('rechazó', self._nota(tipo=61, codigo=1, razon='x').data['detail'])

    def test_un_miembro_no_emite_notas(self):
        self.client.force_authenticate(self.miembro)
        self.assertEqual(self._nota(tipo=61, codigo=1, razon='x').status_code, 403)


class DatosDeLaEmpresaTests(_BaseDTE):
    """Los datos de la empresa se editan en un solo lugar (Ajustes › Empresas › Datos y logo): el RUT
    se valida y se guarda normalizado, y es el mismo que usa el facturador."""

    def test_el_rut_se_valida_y_se_normaliza(self):
        self.client.force_authenticate(self.admin)
        url = f'/api/v1/workspaces/{self.org.slug}/'
        r = self.client.patch(url, {'rut': '76.000.000-5'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('dígito verificador', str(r.data['rut']))
        r = self.client.patch(url, {'rut': '76.000.000-0'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.org.refresh_from_db()
        self.assertEqual(self.org.rut, '76000000-0')
        self.assertEqual(servicio.emisor(self.org).rut, '76000000-0')

    def test_la_oficina_del_sii_se_configura(self):
        self.client.force_authenticate(self.admin)
        r = self.client.put(f'{self.dte}/configuracion/', {'oficina_sii': 'Santiago Oriente'}, format='json')
        self.assertEqual(r.data['oficina_sii'], 'Santiago Oriente')

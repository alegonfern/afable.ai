"""Guía de despacho electrónica desde Entregas y facturación parcial con el detalle de cada línea."""
from unittest import mock

from apps.comercial import emision
from apps.comercial.models import Entrega

from . import motor, servicio
from .models import DocumentoEmitido
from .nucleo import envio as nucleo_envio
from .nucleo.xmlutil import SII, leer
from .tests import SIIFalso, _BaseDTE, caf_de_prueba

NS = {'s': SII}


def _xml(emitido):
    return leer(emitido.xml.encode('iso-8859-1'))


def _lineas(emitido):
    x = _xml(emitido)
    return [(det.findtext('s:NmbItem', namespaces=NS), det.findtext('s:QtyItem', namespaces=NS))
            for det in x.findall('.//s:Detalle', NS)]


class _ConEntregas(_BaseDTE):
    def setUp(self):
        super().setUp()
        self._alta()
        servicio.cargar_caf(self.org, caf_de_prueba('76000000-0', tipo=52))
        self.parche = mock.patch.object(motor, 'cliente', return_value=SIIFalso())
        self.parche.start()
        self.pedido = self._orden()
        self.cemento, self.flete = list(self.pedido.lineas.order_by('id'))

    def tearDown(self):
        self.parche.stop()
        super().tearDown()

    def _entregar(self, cantidades):
        r = self.client.post(f'{self.base}/pedidos/{self.pedido.id}/entregar/', {'cantidades': cantidades}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        return r.data


class GuiaTests(_ConEntregas):
    def test_emitir_la_guia_de_una_entrega(self):
        datos = self._entregar({self.cemento.id: 4})
        entrega = datos['entregas'][0]
        self.assertTrue(entrega['guia_disponible'])
        r = self.client.post(f'{self.base}/pedidos/{self.pedido.id}/entregas/{entrega["id"]}/guia/',
                             {'patente': 'AB1234', 'comuna_destino': 'Vitacura'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        e = r.data['entregas'][0]
        self.assertEqual(e['folio_guia'], '1')
        self.assertFalse(e['guia_disponible'])
        guia = DocumentoEmitido.objects.get(pk=e['guia_documento'])
        self.assertEqual(guia.tipo, 52)
        x = _xml(guia)
        self.assertEqual(x.findtext('.//s:IndTraslado', namespaces=NS), '1')
        self.assertEqual(x.findtext('.//s:Patente', namespaces=NS), 'AB1234')
        self.assertEqual(x.findtext('.//s:CmnaDest', namespaces=NS), 'Vitacura')
        self.assertEqual(_lineas(guia), [('Saco de cemento', '4')])
        nucleo_envio.revisar(guia.envio.xml.encode('iso-8859-1'))  # esquema y firmas
        # Una entrega tiene una sola guía.
        r = self.client.post(f'{self.base}/pedidos/{self.pedido.id}/entregas/{entrega["id"]}/guia/', {}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('ya tiene la guía', r.data['detail'])

    def test_devolucion_del_cliente_va_como_guia_de_devolucion(self):
        self._entregar({self.cemento.id: 4})
        r = self.client.post(f'{self.base}/pedidos/{self.pedido.id}/devolver/', {'cantidades': {self.cemento.id: 1}},
                             format='json')
        self.assertEqual(r.status_code, 200, r.content)
        devolucion = Entrega.objects.get(pedido=self.pedido, tipo=Entrega.DEVOLUCION)
        r = self.client.post(f'{self.base}/pedidos/{self.pedido.id}/entregas/{devolucion.id}/guia/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        guia = DocumentoEmitido.objects.get(tipo=52)
        self.assertEqual(_xml(guia).findtext('.//s:IndTraslado', namespaces=NS), '7')
        self.assertEqual(_lineas(guia), [('Saco de cemento', '1')])

    def test_sin_el_facturador_activo_no_hay_guia(self):
        servicio.desactivar(self.org)
        datos = self._entregar({self.cemento.id: 4})
        self.assertFalse(datos['entregas'][0]['guia_disponible'])
        r = self.client.post(f'{self.base}/pedidos/{self.pedido.id}/entregas/{datos["entregas"][0]["id"]}/guia/', {},
                             format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('active el facturador', r.data['detail'])

    def test_un_miembro_no_emite_guias(self):
        datos = self._entregar({self.cemento.id: 4})
        self.client.force_authenticate(self.miembro)
        r = self.client.post(f'{self.base}/pedidos/{self.pedido.id}/entregas/{datos["entregas"][0]["id"]}/guia/', {},
                             format='json')
        self.assertEqual(r.status_code, 403)


class FacturacionParcialTests(_ConEntregas):
    def test_facturar_lo_entregado_lleva_el_detalle_y_despues_el_resto(self):
        self._entregar({self.cemento.id: 4})
        primera = emision.emitir(self.pedido, que='entregado')
        self.assertEqual(primera.monto_neto, 24000)
        self.assertEqual(_lineas(primera.emitido), [('Saco de cemento', '4')])
        # El resto: 6 sacos y el flete.
        self._entregar({self.cemento.id: 6, self.flete.id: 1})
        self.pedido.refresh_from_db()
        segunda = emision.emitir(self.pedido, que='entregado')
        self.assertEqual(segunda.monto_neto, 56000)
        self.assertEqual(_lineas(segunda.emitido), [('Saco de cemento', '6'), ('Flete', '1')])

    def test_una_nota_de_credito_devuelve_cantidades_por_facturar(self):
        servicio.cargar_caf(self.org, caf_de_prueba('76000000-0', tipo=61))
        self._entregar({self.cemento.id: 10, self.flete.id: 1})
        factura = emision.emitir(self.pedido)
        from .comercial import registrar_nota, ya_facturado
        nota = servicio.emitir_nota(self.org, factura.emitido, 61, 3, 'Devolución de 2 sacos',
                                    [{'nombre': 'Saco de cemento', 'cantidad': 2, 'precio': 6000}])
        registrar_nota(nota, factura.emitido)
        facturado = ya_facturado(self.pedido)
        self.assertEqual(facturado[('c', 'CEM')], 8)

    def test_si_el_monto_no_calza_con_el_detalle_va_una_linea(self):
        doc = emision.emitir(self.pedido, monto=12345)
        self.assertEqual(_lineas(doc.emitido), [(f'Facturación parcial {self.pedido.numero}', '1')])
        self.assertEqual(doc.monto_neto, 12345)

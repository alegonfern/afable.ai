"""Facturar desde Afable (25-10-2026): el facturador simulado, el PDF, y emitir y recibir
facturas desde el chat."""
from apps.finanzas.models import DocumentoTributario

from . import emision, facturacion, herramienta
from .models import Pedido
from .tests import _Base


def configurar_emisor(org):
    from .models import ConfiguracionComercial
    ConfiguracionComercial.objects.filter(pk=ConfiguracionComercial.de(org).pk).update(
        emisor_razon_social='Ferretería Ejemplo SpA', emisor_giro='Venta de materiales de construcción',
        emisor_direccion='Av. Siempre Viva 742', emisor_comuna='Providencia', emisor_ciudad='Santiago')


class FacturarTests(_Base):

    def setUp(self):
        super().setUp()
        configurar_emisor(self.org)

    def test_sin_los_datos_del_emisor_dice_exactamente_que_falta(self):
        from .models import ConfiguracionComercial
        ConfiguracionComercial.objects.filter(organization=self.org).update(emisor_giro='', emisor_comuna='')
        with self.assertRaisesMessage(emision.ErrorComercial, 'falta el giro y la comuna de su empresa'):
            emision.emitir(self._orden_confirmada())

    def test_el_rut_de_la_empresa_se_valida_al_configurarlo(self):
        r = self.client.put(f'{self.base}/configuracion/', {'emisor': {'rut': '76.000.000-5'}}, format='json')
        self.assertEqual(r.status_code, 400)
        r = self.client.put(f'{self.base}/configuracion/', {'emisor': {'rut': '76.000.000-0', 'giro': 'Ferretería'}}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.data['emisor']['rut'], r.data['emisor']['giro']), ('76000000-0', 'Ferretería'))

    def _orden_confirmada(self):
        p = self._cotizacion()
        self.assertEqual(self._accion(p['id'], 'confirmar').status_code, 200)
        return Pedido.objects.get(pk=p['id'])

    def test_emitir_deja_la_factura_en_el_libro_de_ventas_amarrada_a_su_orden(self):
        p = self._orden_confirmada()
        doc = emision.emitir(p, usuario=self.editor)
        self.assertTrue(doc.emitido_en_afable)
        self.assertEqual((doc.libro, doc.tipo_documento, doc.rut), ('ventas', '33', '77111222-3'))
        self.assertEqual(doc.monto_neto, 80000)          # 10 × 6.000 + 20.000
        self.assertEqual(doc.monto_total, 95200)
        self.assertEqual(facturacion.facturado(p), p.base_clp)

    def test_el_folio_sigue_al_mayor_que_ya_tiene_la_empresa(self):
        DocumentoTributario.objects.create(organization=self.org, libro='ventas', tipo_documento='33', folio='1043',
                                           rut='1-9', fecha='2026-10-01', monto_total=1)
        a = emision.emitir(self._orden_confirmada())
        b = emision.emitir(self._orden_confirmada())
        self.assertEqual((a.folio, b.folio), ('1044', '1045'))

    def test_no_se_factura_dos_veces_ni_una_cotizacion(self):
        p = self._orden_confirmada()
        emision.emitir(p)
        with self.assertRaisesMessage(emision.ErrorComercial, 'ya está facturada'):
            emision.emitir(p)
        cot = Pedido.objects.get(pk=self._cotizacion()['id'])
        with self.assertRaisesMessage(emision.ErrorComercial, 'confirmar'):
            emision.emitir(cot)

    def test_el_pdf_se_descarga(self):
        doc = emision.emitir(self._orden_confirmada())
        r = self.client.get(f'{self.base}/facturas/{doc.id}/pdf/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertTrue(r.content.startswith(b'%PDF'))

    def test_facturar_desde_el_chat_pide_confirmacion_y_deja_la_tarjeta(self):
        from services import agent_tools
        p = self._orden_confirmada()
        r = herramienta.ejecutar(self.org, {'accion': 'facturar', 'numero': p.numero}, self.editor)
        self.assertTrue(r['requiere_confirmacion'])
        self.assertFalse(DocumentoTributario.objects.filter(organization=self.org, libro='ventas').exists())
        artifacts = {}
        agent_tools.execute_tool('compras_ventas', {'accion': 'facturar', 'numero': p.numero, 'confirmado': True},
                                 self.org, [], None, artifacts, usuario=self.editor)
        t = artifacts['acciones'][0]
        self.assertEqual(t['tipo'], 'factura')
        self.assertEqual([l['descripcion'] for l in t['lineas']], ['Saco de cemento', 'Flete'])
        self.assertEqual(t['totales'][-1]['valor'], '$95.200')

    def test_facturar_libre_crea_la_orden_y_la_factura(self):
        r = herramienta.ejecutar(self.org, {
            'accion': 'facturar_directo', 'contacto': 'andes', 'confirmado': True,
            'lineas': [{'descripcion': 'Asesoría', 'cantidad': 3, 'precio_unitario': 50000}]}, self.editor)
        self.assertEqual(r['factura_emitida']['neto'], 150000)
        p = Pedido.objects.get(numero=r['pedido'], organization=self.org)
        self.assertEqual(p.estado, Pedido.CONFIRMADO)
        self.assertEqual(facturacion.facturado(p), 150000)

    def test_registrar_la_factura_de_un_proveedor_amarrada_a_su_orden(self):
        oc = Pedido.objects.get(pk=self._cotizacion(tipo='compra')['id'])
        self._accion(oc.id, 'confirmar')
        oc.refresh_from_db()
        neto = oc.base_clp
        args = {'accion': 'registrar_factura_proveedor', 'rut': '76.555.444-1', 'folio': '8812', 'fecha': '2026-10-20',
                'neto': neto, 'iva': round(neto * 0.19), 'total': neto + round(neto * 0.19), 'numero': oc.numero}
        self.assertTrue(herramienta.ejecutar(self.org, args, self.editor)['requiere_confirmacion'])
        r = herramienta.ejecutar(self.org, {**args, 'confirmado': True}, self.editor)
        self.assertEqual(r['registrada']['proveedor'], 'Cementos Sur')
        doc = DocumentoTributario.objects.get(organization=self.org, libro='compras', folio='8812')
        self.assertEqual(facturacion.facturado(oc), neto)
        self.assertFalse(doc.emitido_en_afable)
        otra = herramienta.ejecutar(self.org, {**args, 'confirmado': True, 'numero': None}, self.editor)
        self.assertIn('ya está en el Libro de Compras', otra['error'])


class ElegirQueFacturarTests(_Base):
    """Cuando se vendió más de lo que se entregó, se pregunta qué facturar (25-10-2026)."""

    def setUp(self):
        super().setUp()
        configurar_emisor(self.org)
        from .models import ConfiguracionComercial
        ConfiguracionComercial.objects.filter(organization=self.org).update(facturar_ventas='entregado')
        p = self._cotizacion()
        self._accion(p['id'], 'confirmar')
        self.p = Pedido.objects.get(pk=p['id'])

    def test_sin_entregas_no_pregunta_y_confirma_lo_vendido_avisandolo(self):
        # Con nada entregado no hay qué elegir: una pregunta de una sola respuesta sobra.
        r = herramienta.ejecutar(self.org, {'accion': 'facturar', 'numero': self.p.numero}, self.editor)
        self.assertTrue(r['requiere_confirmacion'])
        self.assertIn('Todavía no se entrega nada', r['se_hara'])
        r = herramienta.ejecutar(self.org, {'accion': 'facturar', 'numero': self.p.numero, 'que': 'vendido',
                                            'confirmado': True}, self.editor)
        self.assertEqual(r['factura_emitida']['neto'], 80000)

    def test_con_entrega_parcial_ofrece_las_dos_y_deja_la_tarjeta(self):
        from services import agent_tools
        from . import operaciones as op
        cemento = self.p.lineas.get(producto=self.cemento)
        op.registrar_entrega(self.p, {cemento.id: 5}, self.editor)        # 5 de 10 sacos: $30.000
        artifacts = {}
        agent_tools.execute_tool('compras_ventas', {'accion': 'facturar', 'numero': self.p.numero},
                                 self.org, [], None, artifacts, usuario=self.editor)
        t = artifacts['acciones'][0]
        self.assertEqual(t['tipo'], 'elegir')
        self.assertEqual([o['texto'] for o in t['opciones']],
                         ['Facturar lo vendido ($80.000)', 'Facturar lo entregado ($30.000)'])
        r = herramienta.ejecutar(self.org, {'accion': 'facturar', 'numero': self.p.numero, 'que': 'entregado',
                                            'confirmado': True}, self.editor)
        self.assertEqual(r['factura_emitida']['neto'], 30000)

    def test_la_ficha_de_la_orden_trae_los_dos_montos_y_emite_el_elegido(self):
        r = self.client.get(f'{self.base}/pedidos/{self.p.id}/')
        self.assertEqual(r.data['facturable'], {'vendido': 80000, 'entregado': 0})
        r = self.client.post(f'{self.base}/pedidos/{self.p.id}/accion/', {'accion': 'emitir', 'que': 'vendido'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(facturacion.facturado(self.p), 80000)


class LoQueHizoHoyTests(_Base):
    """La columna "Lo que hizo hoy" de la vista Agente sale de hechos registrados (25-10-2026)."""

    def test_ventas_muestra_la_orden_confirmada_y_la_factura_emitida(self):
        configurar_emisor(self.org)
        p = self._cotizacion()
        self._accion(p['id'], 'confirmar')
        doc = emision.emitir(Pedido.objects.get(pk=p['id']))
        r = self.client.get(f'/api/v1/workspaces/{self.org.slug}/finanzas/agentes/ventas/hoy/')
        self.assertEqual(r.status_code, 200)
        titulos = [x['titulo'] for x in r.data]
        self.assertIn(f'Emitió la factura N° {doc.folio}', titulos)
        self.assertTrue(any(t.startswith('Confirmó OV-') for t in titulos))
        self.assertEqual(self.client.get(f'/api/v1/workspaces/{self.org.slug}/finanzas/agentes/otro/hoy/').status_code, 404)

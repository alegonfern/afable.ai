"""Que lo que el chat hace en el ERP llegue a la pantalla como tarjeta (25-10-2026).

Ninguna prueba habla con un modelo: se ejecutan las herramientas directo, y el stream se
prueba con un agente falso que entrega el evento final.
"""
import json
import unittest.mock as mock

from apps.comercial.models import Pedido
from apps.comercial.tests import _Base
from apps.agents.models import Agent, Message
from services import agent_tools, tarjetas_chat


class TarjetasDeComprasYVentasTests(_Base):

    def _ejecutar(self, args):
        artifacts = {}
        r = agent_tools.execute_tool('compras_ventas', args, self.org, [], None, artifacts, usuario=self.editor)
        return r, artifacts.get('acciones', [])

    def test_crear_una_cotizacion_deja_el_documento_con_sus_lineas(self):
        r, acciones = self._ejecutar({'accion': 'crear_cotizacion', 'tipo': 'venta', 'contacto': 'andes',
                                      'lineas': [{'producto': 'CEM', 'cantidad': 10}, {'producto': 'Flete', 'cantidad': 1}]})
        self.assertEqual(len(acciones), 1)
        t = acciones[0]
        self.assertEqual(t['tipo'], 'documento')
        self.assertEqual(t['modulo'], 'ventas')
        self.assertEqual(t['titulo'], f'Cotización {r["creada"]}')
        self.assertEqual(t['subtitulo'], 'Constructora Andes')
        self.assertEqual([l['descripcion'] for l in t['lineas']], ['Saco de cemento', 'Flete'])
        # 10 × 6.000 + 20.000 = 80.000 neto; con IVA, 95.200.
        self.assertEqual(t['totales'][0], {'etiqueta': 'Neto', 'valor': '$80.000'})
        self.assertEqual(t['totales'][-1]['valor'], '$95.200')
        self.assertTrue(t['enlace'].startswith('/app/ventas/ordenes/'))

    def test_confirmar_primero_pregunta_y_despues_dice_que_quedo_hecho(self):
        self._ejecutar({'accion': 'crear_cotizacion', 'tipo': 'venta', 'contacto': 'andes',
                        'lineas': [{'producto': 'CEM', 'cantidad': 2}]})
        numero = Pedido.objects.get(organization=self.org).numero
        _, acciones = self._ejecutar({'accion': 'confirmar', 'numero': numero})
        self.assertEqual(acciones[0]['tipo'], 'confirmar')
        self.assertIn(numero, acciones[0]['texto'])
        _, acciones = self._ejecutar({'accion': 'confirmar', 'numero': numero, 'confirmado': True})
        self.assertEqual(acciones[0]['tipo'], 'hecho')
        self.assertEqual(acciones[0]['titulo'], 'Orden confirmada')

    def test_un_error_no_deja_tarjeta(self):
        _, acciones = self._ejecutar({'accion': 'confirmar', 'numero': 'OV-9999'})
        self.assertEqual(acciones, [])

    def test_una_lista_de_pedidos_lleva_enlace_a_cada_uno(self):
        self._ejecutar({'accion': 'crear_cotizacion', 'tipo': 'venta', 'contacto': 'andes',
                        'lineas': [{'producto': 'CEM', 'cantidad': 2}]})
        _, acciones = self._ejecutar({'accion': 'pedidos', 'tipo': 'venta'})
        self.assertEqual(acciones[0]['tipo'], 'lista')
        self.assertEqual(acciones[0]['filas'][0]['valor'], '$12.000')
        self.assertTrue(acciones[0]['filas'][0]['enlace'].startswith('/app/ventas/ordenes/'))


class TarjetasDeFinanzasTests(_Base):

    def test_el_resumen_del_mes_son_cuatro_cifras_con_la_ganancia_destacada(self):
        t = tarjetas_chat.de('consultar_finanzas', {'consulta': 'resumen_mes'}, {
            'anio': 2026, 'mes': 10, 'mes_ingresos_sin_iva': 39580000, 'mes_gastos_sin_iva': 8650500,
            'mes_ganancia': 30929500, 'mes_margen_pct': 78.1, 'anio_ingresos': 1, 'anio_gastos': 1,
            'anio_ganancia': 42326000, 'meses_con_datos': [10]})
        self.assertEqual(t['titulo'], 'Octubre 2026')
        self.assertEqual(t['cifras'][0], {'etiqueta': 'Ganancia', 'valor': '$30.929.500',
                                          'detalle': 'margen 78,1%', 'destacado': True})

    def test_caja_sin_cartolas_no_inventa_una_tarjeta(self):
        self.assertIsNone(tarjetas_chat.de('consultar_finanzas', {'consulta': 'caja'}, {'disponible': None}))

    def test_una_tarjeta_que_falla_al_armarse_no_rompe_nada(self):
        self.assertIsNone(tarjetas_chat.de('consultar_finanzas', {'consulta': 'resumen_mes'}, {'mes': 3}))


class LasTarjetasViajanPorElStreamTests(_Base):

    def test_el_stream_las_manda_antes_del_texto_y_quedan_en_el_mensaje(self):
        Agent.objects.create(organization=self.org, name='Afable')
        tarjeta = {'tipo': 'hecho', 'modulo': 'ventas', 'titulo': 'Orden confirmada', 'texto': 'x'}

        def falso(*a, **k):
            yield {'status': 'Revisando ventas'}
            yield {'final': 'Listo, quedó confirmada.', 'documentos': [], 'acciones': [tarjeta]}

        with mock.patch('services.agent_service.run_agent_live_events', falso), \
                mock.patch('apps.agents.views._build_onboarding_context', return_value={
                    'system_prompt': 'x', 'mode': 'con_herramientas', 'org': self.org,
                    'allowed_ids': None, 'allowed_doc_ids': None}):
            r = self.client.post('/api/v1/agents/direct-chat/stream/', {'message': 'confirma la OV-0001',
                                 'workspace': self.org.slug}, format='json')
            cuerpo = b''.join(r.streaming_content).decode()
        eventos = [json.loads(l[6:]) for l in cuerpo.split('\n') if l.startswith('data: ')]
        i_acciones = next(i for i, e in enumerate(eventos) if 'acciones' in e and 'done' not in e)
        i_texto = next(i for i, e in enumerate(eventos) if 'chunk' in e)
        self.assertLess(i_acciones, i_texto)
        respuesta = Message.objects.filter(role='assistant').last()
        self.assertEqual(respuesta.acciones, [tarjeta])
        # Los pasos quedan con la respuesta. Una respuesta que solo informa no avisa.
        self.assertEqual(respuesta.pasos, ['Revisando ventas'])
        from apps.notificaciones.models import Notificacion
        self.assertFalse(Notificacion.objects.filter(user=self.editor).exists())
        fin = next(e for e in eventos if e.get('done'))
        self.assertEqual(fin['pasos'], ['Revisando ventas'])
        self.assertNotIn('notificacion_id', fin)

    def test_avisa_solo_cuando_hay_un_boton_que_espera_a_quien_pregunto(self):
        from apps.notificaciones.models import Notificacion
        Agent.objects.create(organization=self.org, name='Afable')
        tarjeta = {'tipo': 'confirmar', 'modulo': 'ventas', 'titulo': '¿Lo confirma?', 'texto': 'Confirmar OV-0001.'}

        def falso(*a, **k):
            yield {'final': '¿La confirmo?', 'documentos': [], 'acciones': [tarjeta]}

        with mock.patch('services.agent_service.run_agent_live_events', falso), \
                mock.patch('apps.agents.views._build_onboarding_context', return_value={
                    'system_prompt': 'x', 'mode': 'con_herramientas', 'org': self.org,
                    'allowed_ids': None, 'allowed_doc_ids': None}):
            r = self.client.post('/api/v1/agents/direct-chat/stream/', {'message': 'confirma la OV-0001',
                                 'workspace': self.org.slug}, format='json')
            cuerpo = b''.join(r.streaming_content).decode()
        aviso = Notificacion.objects.get(user=self.editor)
        self.assertEqual((aviso.titulo, aviso.detalle), ('Revisa la respuesta de Afable', 'Confirmar OV-0001.'))
        self.assertIn(f'"notificacion_id": {aviso.id}', cuerpo)


class GuiaDeLibrosTests(_Base):

    def test_la_guia_se_ofrece_siempre_y_deja_su_tarjeta(self):
        nombres = [t['name'] for t in agent_tools._tools_spec(self.org)]
        self.assertIn('guia_libros_sii', nombres)
        artifacts = {}
        agent_tools.execute_tool('guia_libros_sii', {'libro': 'ventas'}, self.org, [], None, artifacts, usuario=self.editor)
        self.assertEqual((artifacts['acciones'][0]['tipo'], artifacts['acciones'][0]['libro']), ('guia', 'ventas'))


class CadaTarjetaDiceSuAgenteTests(_Base):
    """Detrás de cada módulo hay un agente, y la tarjeta y el paso dicen cuál trabajó (25-10-2026)."""

    def test_la_tarjeta_y_el_paso_llevan_el_agente_del_modulo(self):
        from services.agent_service import _tool_status
        artifacts = {}
        agent_tools.execute_tool('compras_ventas', {'accion': 'crear_cotizacion', 'tipo': 'venta', 'contacto': 'andes',
                                 'lineas': [{'producto': 'CEM', 'cantidad': 1}]}, self.org, [], None, artifacts, usuario=self.editor)
        self.assertEqual(artifacts['acciones'][0]['agente'], 'Agente de Ventas')
        self.assertEqual(tarjetas_chat.agente_de('compras_ventas', {'accion': 'registrar_factura_proveedor'}), 'Agente de Compras')
        self.assertEqual(tarjetas_chat.agente_de('conciliar_banco', {'accion': 'pendientes'}), 'Agente de Finanzas')
        self.assertEqual(tarjetas_chat.agente_de('consultar_finanzas', {'consulta': 'f29'}), 'Agente de Contabilidad')
        self.assertTrue(_tool_status('consultar_finanzas', {'consulta': 'caja'}).startswith('Agente de Finanzas · '))

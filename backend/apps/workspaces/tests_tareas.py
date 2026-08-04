"""Pruebas de las Tareas del Espacio.

Lo que cubren: que el permiso sea exactamente el del Espacio (una tarea de un
Espacio que no veo no existe para mí), que no se asigne un agente que el Espacio no
alcanza, que el orden ponga lo pendiente arriba, y que la ejecución por un agente
guarde el resultado sin dejar la tarea trabada si el modelo falla.

La ejecución no habla con ningún modelo: `_run_prompt` se reemplaza.
"""

import unittest.mock as mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.agents.models import Agent
from apps.organizations.models import Organization
from apps.workspaces.models import (
    ROLE_ADMIN, ROLE_MEMBER, VISIBILITY_OPEN, VISIBILITY_RESTRICTED,
    Space, Task, Workspace,
)

User = get_user_model()


class BaseTareas(TestCase):

    def setUp(self):
        self.client = APIClient()

        self.duena = User.objects.create_user(
            username='duena@afable.test', email='duena@afable.test', password='afable123',
        )
        self.colega = User.objects.create_user(
            username='colega@afable.test', email='colega@afable.test', password='afable123',
        )
        self.ajeno = User.objects.create_user(
            username='ajeno@afable.test', email='ajeno@afable.test', password='afable123',
        )

        self.org = Organization.objects.create(owner=self.duena, name='Cocinas SpA')
        self.ws = Workspace.objects.create(name='Cocinas SpA', organization=self.org)
        self.ws.add_member(self.duena, ROLE_ADMIN)
        self.ws.add_member(self.colega, ROLE_MEMBER)

        self.agente = Agent.objects.create(organization=self.org, name='Cobranzas')
        self.otro_agente = Agent.objects.create(organization=self.org, name='Compras')

        self.espacio = Space.objects.create(
            workspace=self.ws, name='Finanzas', visibility=VISIBILITY_OPEN,
        )
        self.espacio.agents.add(self.agente)

    def url(self, espacio=None, pk=None, sufijo=''):
        base = f'/api/v1/workspaces/{self.ws.slug}/espacios/{(espacio or self.espacio).slug}/tareas/'
        if pk is not None:
            base += f'{pk}/{sufijo}'
        return base

    def crear(self, quien=None, **datos):
        self.client.force_authenticate(user=quien or self.duena)
        cuerpo = {'title': 'Revisar facturas vencidas'}
        cuerpo.update(datos)
        return self.client.post(self.url(), cuerpo, format='json')


class PermisoTests(BaseTareas):

    def test_cualquier_miembro_del_espacio_crea_una_tarea(self):
        """Son items de trabajo livianos, no configuración de la empresa."""
        r = self.crear(self.colega)
        self.assertEqual(r.status_code, 201)

    def test_quien_no_es_miembro_del_workspace_no_las_ve(self):
        self.client.force_authenticate(user=self.ajeno)
        r = self.client.get(self.url())
        self.assertEqual(r.status_code, 404)

    def test_un_espacio_restringido_esconde_sus_tareas(self):
        reservado = Space.objects.create(
            workspace=self.ws, name='Directorio', visibility=VISIBILITY_RESTRICTED,
        )
        Task.objects.create(space=reservado, title='Secreta')

        self.client.force_authenticate(user=self.colega)
        r = self.client.get(self.url(espacio=reservado))
        self.assertEqual(r.status_code, 404)

    def test_el_administrador_si_ve_el_espacio_restringido(self):
        reservado = Space.objects.create(
            workspace=self.ws, name='Directorio', visibility=VISIBILITY_RESTRICTED,
        )
        self.client.force_authenticate(user=self.duena)
        self.assertEqual(self.client.get(self.url(espacio=reservado)).status_code, 200)

    def test_una_tarea_de_otro_espacio_no_se_alcanza_por_id(self):
        otro = Space.objects.create(workspace=self.ws, name='Compras')
        ajena = Task.objects.create(space=otro, title='De otro Espacio')

        self.client.force_authenticate(user=self.duena)
        r = self.client.patch(self.url(pk=ajena.pk), {'state': 'lista'}, format='json')
        self.assertEqual(r.status_code, 404)
        ajena.refresh_from_db()
        self.assertEqual(ajena.state, 'pendiente')


class CreacionTests(BaseTareas):

    def test_la_tarea_nace_pendiente_y_con_autor(self):
        r = self.crear()
        tarea = Task.objects.get(pk=r.data['id'])
        self.assertEqual(tarea.state, 'pendiente')
        self.assertEqual(tarea.created_by_id, self.duena.id)
        self.assertEqual(tarea.space_id, self.espacio.id)

    def test_sin_titulo_no_se_crea(self):
        r = self.crear(title='   ')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Task.objects.count(), 0)

    def test_se_asigna_un_agente_del_espacio(self):
        r = self.crear(agent=self.agente.id)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Task.objects.get(pk=r.data['id']).agent_id, self.agente.id)

    def test_no_se_asigna_un_agente_que_el_espacio_no_alcanza(self):
        """Asignar y ejecutar seria la forma de poner a trabajar a un agente ajeno."""
        r = self.crear(agent=self.otro_agente.id)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Task.objects.count(), 0)

    def test_un_espacio_sin_agentes_propios_acepta_cualquiera_de_la_empresa(self):
        """Misma salvedad que `alcance_de_agente`: si no, los Espacios que ya existen
        se quedan sin poder asignar nada."""
        pelado = Space.objects.create(workspace=self.ws, name='General')
        self.client.force_authenticate(user=self.duena)
        r = self.client.post(
            self.url(espacio=pelado),
            {'title': 'Algo', 'agent': self.otro_agente.id}, format='json',
        )
        self.assertEqual(r.status_code, 201)

    def test_no_se_asigna_un_agente_de_otra_empresa(self):
        otra_org = Organization.objects.create(owner=self.ajeno, name='Muebles Ltda')
        ajeno = Agent.objects.create(organization=otra_org, name='Ajeno')
        r = self.crear(agent=ajeno.id)
        self.assertEqual(r.status_code, 400)

    def test_se_asigna_una_persona_del_workspace(self):
        r = self.crear(assignee=self.colega.id)
        self.assertEqual(Task.objects.get(pk=r.data['id']).assignee_id, self.colega.id)

    def test_no_se_asigna_alguien_de_fuera_del_workspace(self):
        r = self.crear(assignee=self.ajeno.id)
        self.assertEqual(r.status_code, 400)


class ListaTests(BaseTareas):

    def test_las_pendientes_van_arriba_y_las_listas_al_final(self):
        """El `Meta` del modelo ordenaria por el TEXTO del estado, o sea al reves."""
        Task.objects.create(space=self.espacio, title='Ya hecha', state='lista')
        Task.objects.create(space=self.espacio, title='Trabajando', state='en_curso')
        Task.objects.create(space=self.espacio, title='Falta', state='pendiente')

        self.client.force_authenticate(user=self.duena)
        estados = [t['state'] for t in self.client.get(self.url()).data['results']]
        self.assertEqual(estados, ['pendiente', 'en_curso', 'lista'])

    def test_cuenta_las_pendientes(self):
        Task.objects.create(space=self.espacio, title='Ya hecha', state='lista')
        Task.objects.create(space=self.espacio, title='Falta', state='pendiente')

        self.client.force_authenticate(user=self.duena)
        datos = self.client.get(self.url()).data
        self.assertEqual(datos['count'], 2)
        self.assertEqual(datos['pendientes'], 1)

    def test_no_muestra_las_tareas_de_otro_espacio(self):
        otro = Space.objects.create(workspace=self.ws, name='Compras')
        Task.objects.create(space=otro, title='De Compras')
        Task.objects.create(space=self.espacio, title='De Finanzas')

        self.client.force_authenticate(user=self.duena)
        titulos = [t['title'] for t in self.client.get(self.url()).data['results']]
        self.assertEqual(titulos, ['De Finanzas'])


class EdicionTests(BaseTareas):

    def setUp(self):
        super().setUp()
        self.tarea = Task.objects.create(
            space=self.espacio, title='Revisar facturas', created_by=self.duena,
        )

    def patch(self, quien=None, **datos):
        self.client.force_authenticate(user=quien or self.duena)
        return self.client.patch(self.url(pk=self.tarea.pk), datos, format='json')

    def test_se_marca_lista(self):
        r = self.patch(state='lista')
        self.assertEqual(r.status_code, 200)
        self.tarea.refresh_from_db()
        self.assertTrue(self.tarea.esta_lista)

    def test_un_estado_inventado_no_pasa(self):
        r = self.patch(state='terminadisima')
        self.assertEqual(r.status_code, 400)
        self.tarea.refresh_from_db()
        self.assertEqual(self.tarea.state, 'pendiente')

    def test_un_patch_parcial_no_borra_lo_que_no_nombro(self):
        self.tarea.description = 'El detalle'
        self.tarea.agent = self.agente
        self.tarea.save()

        self.patch(state='en_curso')
        self.tarea.refresh_from_db()
        self.assertEqual(self.tarea.description, 'El detalle')
        self.assertEqual(self.tarea.agent_id, self.agente.id)

    def test_se_puede_desasignar_mandando_nulo(self):
        self.tarea.assignee = self.colega
        self.tarea.save()
        self.patch(assignee=None)
        self.tarea.refresh_from_db()
        self.assertIsNone(self.tarea.assignee_id)

    def test_cualquier_miembro_completa_la_tarea_de_otro(self):
        """El trabajo del Espacio es del equipo, no del que la escribio."""
        r = self.patch(self.colega, state='lista')
        self.assertEqual(r.status_code, 200)

    def test_se_borra(self):
        self.client.force_authenticate(user=self.duena)
        r = self.client.delete(self.url(pk=self.tarea.pk))
        self.assertEqual(r.status_code, 204)
        self.assertEqual(Task.objects.count(), 0)

    def test_borrar_el_espacio_se_lleva_sus_tareas(self):
        self.espacio.delete()
        self.assertEqual(Task.objects.count(), 0)


class EjecucionTests(BaseTareas):
    """«Todo lo que puede hacer una persona en un Espacio, tambien un agente.»"""

    def setUp(self):
        super().setUp()
        self.tarea = Task.objects.create(
            space=self.espacio, title='Resumen de cobranza',
            description='Arma el resumen de facturas vencidas.',
            agent=self.agente, created_by=self.duena,
        )

    def ejecutar(self, quien=None):
        self.client.force_authenticate(user=quien or self.duena)
        return self.client.post(self.url(pk=self.tarea.pk, sufijo='ejecutar/'), {}, format='json')

    def test_el_agente_la_hace_y_el_resultado_queda_en_la_tarea(self):
        with mock.patch(
            'services.automation_runner._run_prompt', return_value='Hay 3 facturas vencidas.',
        ):
            r = self.ejecutar()
        self.assertEqual(r.status_code, 200)
        self.tarea.refresh_from_db()
        self.assertEqual(self.tarea.resultado, 'Hay 3 facturas vencidas.')
        self.assertEqual(self.tarea.state, 'lista')
        self.assertIsNotNone(self.tarea.ejecutada_at)

    def test_la_descripcion_es_la_instruccion_del_agente(self):
        with mock.patch('services.automation_runner._run_prompt', return_value='ok') as corrio:
            self.ejecutar()
        self.assertEqual(corrio.call_args[0][2], 'Arma el resumen de facturas vencidas.')
        self.assertEqual(corrio.call_args[0][3], self.agente)

    def test_sin_descripcion_la_instruccion_es_el_titulo(self):
        self.tarea.description = ''
        self.tarea.save()
        with mock.patch('services.automation_runner._run_prompt', return_value='ok') as corrio:
            self.ejecutar()
        self.assertEqual(corrio.call_args[0][2], 'Resumen de cobranza')

    def test_sin_agente_no_se_ejecuta(self):
        self.tarea.agent = None
        self.tarea.save()
        r = self.ejecutar()
        self.assertEqual(r.status_code, 400)

    def test_si_el_modelo_falla_la_tarea_vuelve_a_pendiente(self):
        """No puede quedar trabada en «en curso» para siempre."""
        with mock.patch(
            'services.automation_runner._run_prompt', side_effect=RuntimeError('modelo caido'),
        ):
            with self.assertLogs('apps.workspaces.tareas', level='ERROR'):
                r = self.ejecutar()
        self.assertEqual(r.status_code, 502)
        self.tarea.refresh_from_db()
        self.assertEqual(self.tarea.state, 'pendiente')
        self.assertIn('modelo caido', self.tarea.resultado_error)

    def test_un_resultado_gigante_se_recorta(self):
        with mock.patch('services.automation_runner._run_prompt', return_value='x' * 20_000):
            self.ejecutar()
        self.tarea.refresh_from_db()
        self.assertEqual(len(self.tarea.resultado), 8000)

    def test_una_ejecucion_nueva_limpia_el_error_anterior(self):
        self.tarea.resultado_error = 'lo de antes'
        self.tarea.save()
        with mock.patch('services.automation_runner._run_prompt', return_value='ahora si'):
            self.ejecutar()
        self.tarea.refresh_from_db()
        self.assertEqual(self.tarea.resultado_error, '')

    def test_no_se_ejecuta_una_tarea_de_un_espacio_que_no_veo(self):
        reservado = Space.objects.create(
            workspace=self.ws, name='Directorio', visibility=VISIBILITY_RESTRICTED,
        )
        secreta = Task.objects.create(space=reservado, title='Secreta', agent=self.agente)
        self.client.force_authenticate(user=self.colega)
        r = self.client.post(
            f'/api/v1/workspaces/{self.ws.slug}/espacios/{reservado.slug}/tareas/'
            f'{secreta.pk}/ejecutar/', {}, format='json',
        )
        self.assertEqual(r.status_code, 404)


class LimpiezaDeLaRespuestaTests(TestCase):
    """El resultado de una tarea no puede traer la tripa del modelo.

    `gpt-oss` intenta invocar herramientas ESCRIBIENDO la llamada, porque no usa el
    campo `tool_calls`. El chat ya lo limpiaba, pero recién después de extraer la
    acción; por el camino de Tareas y Automatizaciones salía crudo y se vio en el
    resultado de una tarea ejecutada por un agente.
    """

    def test_se_saca_la_llamada_que_el_modelo_escribio_como_texto(self):
        from services.automation_runner import _limpiar_para_leer

        sucio = (
            '__ACTION__{"type":"search","query":"reglamento feriado"}__'
            'El feriado se pide con treinta dias de anticipacion.'
        )
        salida = _limpiar_para_leer(sucio)
        self.assertNotIn('__ACTION__', salida)
        self.assertNotIn('"query"', salida)
        self.assertIn('treinta dias', salida)

    def test_no_toca_un_json_que_es_parte_de_la_respuesta(self):
        """Un agente que devuelve datos en JSON no puede quedar mutilado."""
        from services.automation_runner import _limpiar_para_leer

        salida = _limpiar_para_leer('Las ventas fueron: {"enero": 120, "febrero": 95}')
        self.assertIn('"enero": 120', salida)

    def test_el_chat_sigue_recibiendo_la_accion_intacta(self):
        """Limpiar dentro de `chat_direct` romperia el alta de empresa: el chat extrae
        la accion DESPUES de esa llamada."""
        from services import agent_service
        from apps.agents.views import _extract_action

        crudo = 'Perfecto. __ACTION__{"type":"create_org","name":"Cocinas SpA"}__'
        with mock.patch.object(agent_service, '_chat_ollama', return_value=crudo):
            with mock.patch.object(agent_service, 'resolve_model', return_value=('ollama', 'x')):
                salida = agent_service.chat_direct([{'role': 'user', 'content': 'hola'}])

        accion = _extract_action(salida)
        self.assertIsNotNone(accion)
        self.assertEqual(accion['type'], 'create_org')

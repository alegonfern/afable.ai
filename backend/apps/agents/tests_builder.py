"""Pruebas del constructor de agentes.

Lo que cubren, en orden de importancia: que la politica del Workspace decida de
verdad quien crea (era el permiso que el endpoint viejo no consultaba nunca), que
la empresa NO se pueda elegir desde el cuerpo del pedido, y que no se pueda
enganchar un sistema, una Habilidad o un Espacio que no le corresponde.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.agents.models import Agent, AgentConfig, Skill
from apps.organizations.models import Organization, SystemConnection
from apps.workspaces.models import (
    ROLE_ADMIN, ROLE_EDITOR, ROLE_MEMBER, Space, Workspace,
)

User = get_user_model()

URL = '/api/v1/agents/constructor/'
URL_OPCIONES = '/api/v1/agents/constructor/opciones/'


class BaseConstructor(TestCase):
    """Una empresa con su Workspace, tres personas y otra empresa ajena."""

    def setUp(self):
        self.client = APIClient()

        self.admin = User.objects.create_user(
            username='admin@afable.test', email='admin@afable.test', password='afable123',
        )
        self.editor = User.objects.create_user(
            username='editor@afable.test', email='editor@afable.test', password='afable123',
        )
        self.miembro = User.objects.create_user(
            username='miembro@afable.test', email='miembro@afable.test', password='afable123',
        )

        self.org = Organization.objects.create(owner=self.admin, name='Cocinas SpA')
        self.ws = Workspace.objects.create(name='Cocinas SpA', organization=self.org)
        self.ws.add_member(self.admin, ROLE_ADMIN)
        self.ws.add_member(self.editor, ROLE_EDITOR)
        self.ws.add_member(self.miembro, ROLE_MEMBER)

        self.odoo = SystemConnection.objects.create(
            organization=self.org, name='Odoo Ventas', connector_type='odoo',
        )
        self.habilidad = Skill.objects.create(
            organization=self.org, name='Tono corporativo', instructions='Trate de usted.',
        )
        self.espacio = Space.objects.create(workspace=self.ws, name='Finanzas')

        # Empresa ajena, con sus propias cosas: nada de esto puede engancharse.
        self.ajeno = User.objects.create_user(
            username='ajeno@afable.test', email='ajeno@afable.test', password='afable123',
        )
        self.org_ajena = Organization.objects.create(owner=self.ajeno, name='Muebles Ltda')
        self.ws_ajeno = Workspace.objects.create(name='Muebles Ltda', organization=self.org_ajena)
        self.ws_ajeno.add_member(self.ajeno, ROLE_ADMIN)
        self.sistema_ajeno = SystemConnection.objects.create(
            organization=self.org_ajena, name='SAP Ajeno', connector_type='mssql',
        )
        self.habilidad_ajena = Skill.objects.create(
            organization=self.org_ajena, name='Tono ajeno', instructions='...',
        )
        self.espacio_ajeno = Space.objects.create(workspace=self.ws_ajeno, name='Ajeno')

    def crear(self, quien, **extra):
        self.client.force_authenticate(user=quien)
        cuerpo = {'workspace': self.ws.slug, 'name': 'Analista de Cobranzas'}
        cuerpo.update(extra)
        return self.client.post(URL, cuerpo, format='json')


class PermisoParaCrearTests(BaseConstructor):
    """`Workspace.agent_creation_policy` cruzado con el rol. El default es 'editores'."""

    def test_un_administrador_crea(self):
        r = self.crear(self.admin)
        self.assertEqual(r.status_code, 201)

    def test_un_editor_crea_con_la_politica_por_defecto(self):
        r = self.crear(self.editor)
        self.assertEqual(r.status_code, 201)

    def test_un_miembro_no_crea_con_la_politica_por_defecto(self):
        r = self.crear(self.miembro)
        self.assertEqual(r.status_code, 403)
        self.assertFalse(Agent.objects.filter(name='Analista de Cobranzas').exists())

    def test_con_la_politica_abierta_un_miembro_crea(self):
        self.ws.agent_creation_policy = 'todos'
        self.ws.save(update_fields=['agent_creation_policy'])
        r = self.crear(self.miembro)
        self.assertEqual(r.status_code, 201)

    def test_con_la_politica_cerrada_solo_el_administrador_crea(self):
        self.ws.agent_creation_policy = 'admins'
        self.ws.save(update_fields=['agent_creation_policy'])
        self.assertEqual(self.crear(self.editor).status_code, 403)
        self.assertEqual(self.crear(self.admin).status_code, 201)

    def test_quien_no_es_miembro_no_ve_que_el_workspace_existe(self):
        """404 y no 403: no tiene por que enterarse de que hay un Workspace ahi."""
        r = self.crear(self.ajeno)
        self.assertEqual(r.status_code, 404)

    def test_sin_workspace_no_se_adivina(self):
        self.client.force_authenticate(user=self.admin)
        r = self.client.post(URL, {'name': 'Suelto'}, format='json')
        self.assertEqual(r.status_code, 400)


class CreacionTests(BaseConstructor):

    def test_el_agente_queda_en_la_empresa_del_workspace(self):
        r = self.crear(self.admin)
        agente = Agent.objects.get(pk=r.data['id'])
        self.assertEqual(agente.organization_id, self.org.id)
        self.assertEqual(agente.created_by_id, self.admin.id)

    def test_la_empresa_no_se_elige_desde_el_cuerpo(self):
        """El agujero del endpoint viejo: apuntar a otra empresa mandando su id."""
        r = self.crear(self.admin, organization=self.org_ajena.id)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Agent.objects.get(pk=r.data['id']).organization_id, self.org.id)

    def test_el_handle_se_arma_solo(self):
        r = self.crear(self.admin, name='Analista de Cobranzas')
        self.assertEqual(r.data['handle'], 'analista-de-cobranzas')

    def test_nace_pendiente_en_admin(self):
        """Sin esto no aparece en Admin › Agentes y nadie le entrega el contexto."""
        r = self.crear(self.admin)
        self.assertTrue(AgentConfig.objects.filter(agent_id=r.data['id']).exists())

    def test_sin_nombre_no_se_crea(self):
        r = self.crear(self.admin, name='   ')
        self.assertEqual(r.status_code, 400)

    def test_no_se_repite_el_nombre_en_la_misma_empresa(self):
        self.crear(self.admin)
        r = self.crear(self.admin)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Agent.objects.filter(organization=self.org).count(), 1)

    def test_el_mismo_nombre_en_otra_empresa_si_se_puede(self):
        self.crear(self.admin)
        self.client.force_authenticate(user=self.ajeno)
        r = self.client.post(
            URL, {'workspace': self.ws_ajeno.slug, 'name': 'Analista de Cobranzas'}, format='json',
        )
        self.assertEqual(r.status_code, 201)

    def test_las_instrucciones_largas_se_recortan(self):
        """Pegar un libro entero entraria en CADA respuesta del agente."""
        r = self.crear(self.admin, instructions='x' * 50_000)
        self.assertEqual(len(Agent.objects.get(pk=r.data['id']).instructions), 20_000)


class EngancheTests(BaseConstructor):

    def test_engancha_sistemas_habilidades_y_espacios(self):
        r = self.crear(
            self.admin,
            system_ids=[self.odoo.id],
            skill_ids=[self.habilidad.id],
            space_ids=[self.espacio.id],
        )
        agente = Agent.objects.get(pk=r.data['id'])
        self.assertEqual(list(agente.systems.values_list('id', flat=True)), [self.odoo.id])
        self.assertEqual(list(agente.skills.values_list('id', flat=True)), [self.habilidad.id])
        self.assertEqual(list(agente.spaces.values_list('id', flat=True)), [self.espacio.id])

    def test_no_engancha_nada_de_otra_empresa(self):
        r = self.crear(
            self.admin,
            system_ids=[self.sistema_ajeno.id],
            skill_ids=[self.habilidad_ajena.id],
            space_ids=[self.espacio_ajeno.id],
        )
        agente = Agent.objects.get(pk=r.data['id'])
        self.assertEqual(agente.systems.count(), 0)
        self.assertEqual(agente.skills.count(), 0)
        self.assertEqual(agente.spaces.count(), 0)

    def test_un_espacio_restringido_ajeno_no_se_alcanza(self):
        """Meter un agente propio en un Espacio restringido seria alcanzar sus datos."""
        from apps.workspaces.models import VISIBILITY_RESTRICTED

        reservado = Space.objects.create(
            workspace=self.ws, name='Directorio', visibility=VISIBILITY_RESTRICTED,
        )
        r = self.crear(self.editor, space_ids=[reservado.id])
        self.assertEqual(Agent.objects.get(pk=r.data['id']).spaces.count(), 0)

    def test_una_lista_con_basura_no_rompe(self):
        r = self.crear(self.admin, system_ids=['abc', None, self.odoo.id])
        self.assertEqual(r.status_code, 201)
        self.assertEqual(
            list(Agent.objects.get(pk=r.data['id']).systems.values_list('id', flat=True)),
            [self.odoo.id],
        )


class EdicionTests(BaseConstructor):

    def setUp(self):
        super().setUp()
        r = self.crear(self.admin, system_ids=[self.odoo.id], skill_ids=[self.habilidad.id])
        self.agente = Agent.objects.get(pk=r.data['id'])
        self.url = f'{URL}{self.agente.pk}/'

    def patch(self, quien, **datos):
        self.client.force_authenticate(user=quien)
        return self.client.patch(self.url, {'workspace': self.ws.slug, **datos}, format='json')

    def test_se_lee_el_agente_para_llenar_el_formulario(self):
        self.client.force_authenticate(user=self.admin)
        r = self.client.get(self.url, {'workspace': self.ws.slug})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['system_ids'], [self.odoo.id])
        self.assertEqual(r.data['skill_ids'], [self.habilidad.id])

    def test_se_edita_el_nombre_y_las_instrucciones(self):
        r = self.patch(self.admin, name='Cobranzas', instructions='Nueva regla.')
        self.assertEqual(r.status_code, 200)
        self.agente.refresh_from_db()
        self.assertEqual(self.agente.name, 'Cobranzas')
        self.assertEqual(self.agente.instructions, 'Nueva regla.')

    def test_renombrar_no_cambia_el_handle(self):
        """Es con lo que se lo menciona: cambiarlo rompe los hilos que ya lo nombran."""
        antes = self.agente.handle
        self.patch(self.admin, name='Otro Nombre Del Todo')
        self.agente.refresh_from_db()
        self.assertEqual(self.agente.handle, antes)

    def test_un_patch_parcial_no_borra_lo_que_no_nombro(self):
        self.patch(self.admin, name='Cobranzas')
        self.agente.refresh_from_db()
        self.assertEqual(list(self.agente.systems.values_list('id', flat=True)), [self.odoo.id])

    def test_una_lista_vacia_si_vacia_la_coleccion(self):
        self.patch(self.admin, system_ids=[])
        self.assertEqual(self.agente.systems.count(), 0)

    def test_un_miembro_no_edita_con_la_politica_por_defecto(self):
        r = self.patch(self.miembro, name='Secuestrado')
        self.assertEqual(r.status_code, 403)
        self.agente.refresh_from_db()
        self.assertNotEqual(self.agente.name, 'Secuestrado')

    def test_no_se_edita_un_agente_de_otra_empresa(self):
        ajeno = Agent.objects.create(organization=self.org_ajena, name='Ajeno')
        self.client.force_authenticate(user=self.admin)
        r = self.client.patch(
            f'{URL}{ajeno.pk}/', {'workspace': self.ws.slug, 'name': 'Robado'}, format='json',
        )
        self.assertEqual(r.status_code, 404)

    def test_no_se_le_pone_el_nombre_de_otro_agente(self):
        Agent.objects.create(organization=self.org, name='Ya Existe')
        r = self.patch(self.admin, name='Ya Existe')
        self.assertEqual(r.status_code, 400)

    def test_puede_quedarse_con_su_propio_nombre(self):
        """La comprobacion de nombre repetido no puede chocar contra si mismo."""
        r = self.patch(self.admin, name=self.agente.name, instructions='Otra cosa.')
        self.assertEqual(r.status_code, 200)


class OpcionesTests(BaseConstructor):

    def test_trae_todo_lo_que_el_formulario_necesita(self):
        self.client.force_authenticate(user=self.admin)
        r = self.client.get(URL_OPCIONES, {'workspace': self.ws.slug})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data['puede_crear'])
        self.assertEqual([s['id'] for s in r.data['sistemas']], [self.odoo.id])
        self.assertEqual([h['id'] for h in r.data['habilidades']], [self.habilidad.id])
        self.assertEqual([e['id'] for e in r.data['espacios']], [self.espacio.id])
        self.assertIn('models', r.data['modelos'])

    def test_no_ofrece_nada_de_otra_empresa(self):
        self.client.force_authenticate(user=self.admin)
        r = self.client.get(URL_OPCIONES, {'workspace': self.ws.slug})
        self.assertNotIn(self.sistema_ajeno.id, [s['id'] for s in r.data['sistemas']])
        self.assertNotIn(self.habilidad_ajena.id, [h['id'] for h in r.data['habilidades']])
        self.assertNotIn(self.espacio_ajeno.id, [e['id'] for e in r.data['espacios']])

    def test_un_miembro_ve_las_opciones_pero_no_puede_crear(self):
        """La pantalla necesita poder decir por que no, no un 403 pelado."""
        self.client.force_authenticate(user=self.miembro)
        r = self.client.get(URL_OPCIONES, {'workspace': self.ws.slug})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data['puede_crear'])


class EndpointViejoTests(BaseConstructor):
    """`POST /agents/` resolvia el permiso por dueño y no miraba la politica."""

    def test_ahora_respeta_la_politica_del_workspace(self):
        self.client.force_authenticate(user=self.miembro)
        r = self.client.post(
            '/api/v1/agents/',
            {'organization': self.org.id, 'name': 'Por la puerta de atras'},
            format='json',
        )
        self.assertEqual(r.status_code, 403)

    def test_no_se_crea_en_una_empresa_de_la_que_no_se_es_miembro(self):
        self.client.force_authenticate(user=self.admin)
        r = self.client.post(
            '/api/v1/agents/',
            {'organization': self.org_ajena.id, 'name': 'Invasor'},
            format='json',
        )
        self.assertEqual(r.status_code, 404)
        self.assertFalse(Agent.objects.filter(name='Invasor').exists())

    def test_un_editor_sigue_creando(self):
        self.client.force_authenticate(user=self.editor)
        r = self.client.post(
            '/api/v1/agents/', {'organization': self.org.id, 'name': 'Legado'}, format='json',
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Agent.objects.get(name='Legado').created_by_id, self.editor.id)


class ModelosOfrecidosTests(TestCase):
    """El selector no puede ofrecer un modelo que no sabe conversar."""

    def test_no_ofrece_el_modelo_de_embeddings(self):
        """Vive en el mismo Ollama y sale en /api/tags, pero solo vectoriza texto."""
        from unittest import mock

        from django.test import override_settings

        from apps.agents.views import modelos_disponibles

        respuesta = mock.Mock(status_code=200)
        respuesta.json.return_value = {'models': [
            {'name': 'qwen2.5:7b'}, {'name': 'embeddinggemma:latest'},
        ]}
        with override_settings(EMBEDDINGS_MODEL='embeddinggemma'):
            with mock.patch('requests.get', return_value=respuesta):
                ids = [m['id'] for m in modelos_disponibles()['models']]
        self.assertIn('qwen2.5:7b', ids)
        self.assertNotIn('embeddinggemma:latest', ids)
        self.assertNotIn('embeddinggemma', ids)


class QuienVeElLapizTests(BaseConstructor):
    """`editable` en la galería tiene que coincidir con lo que el constructor permite.

    Si no, hay agentes que se pueden editar por API y no tienen por dónde abrirse.
    """

    def setUp(self):
        super().setUp()
        # Un agente sembrado: sin autor, como los que crea `seed_agentes_base`.
        self.sembrado = Agent.objects.create(organization=self.org, name='Afable')
        self.crear(self.editor, name='Del Editor')

    def galeria(self, quien):
        self.client.force_authenticate(user=quien)
        r = self.client.get('/api/v1/agents/gallery/', {'workspace': self.ws.slug})
        return {a['name']: a['editable'] for a in r.data['results']}

    def test_un_administrador_edita_cualquiera(self):
        editables = self.galeria(self.admin)
        self.assertTrue(editables['Afable'])
        self.assertTrue(editables['Del Editor'])

    def test_un_editor_solo_edita_los_suyos(self):
        editables = self.galeria(self.editor)
        self.assertTrue(editables['Del Editor'])
        self.assertFalse(editables['Afable'])

    def test_un_miembro_no_edita_ninguno(self):
        self.assertFalse(any(self.galeria(self.miembro).values()))

    def test_la_pestana_de_editables_le_muestra_todos_al_administrador(self):
        self.client.force_authenticate(user=self.admin)
        r = self.client.get(
            '/api/v1/agents/gallery/', {'workspace': self.ws.slug, 'tab': 'editables'},
        )
        nombres = [a['name'] for a in r.data['results']]
        self.assertIn('Afable', nombres)
        self.assertIn('Del Editor', nombres)

    def test_la_pestana_de_editables_le_muestra_los_suyos_al_editor(self):
        self.client.force_authenticate(user=self.editor)
        r = self.client.get(
            '/api/v1/agents/gallery/', {'workspace': self.ws.slug, 'tab': 'editables'},
        )
        nombres = [a['name'] for a in r.data['results']]
        self.assertEqual(nombres, ['Del Editor'])

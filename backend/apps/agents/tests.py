"""Pruebas de la mención de agentes: `@ventas` dentro de la conversación.

Cubren lo que se rompe callado: que el handle se arme solo y no choque, que una
mención apunte al agente correcto, y sobre todo que NO alcance agentes de otra
empresa — una mención que cruza la frontera de la organización es una fuga de
datos, no un error de tipeo.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.agents.models import Agent
from apps.agents.views import _agente_mencionado
from apps.organizations.models import Organization

User = get_user_model()


class HandleDeAgenteTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='duena@afable.test', email='duena@afable.test', password='afable123',
        )
        self.org = Organization.objects.create(owner=self.user, name='Cocinas SpA')

    def test_el_handle_se_arma_desde_el_nombre(self):
        agente = Agent.objects.create(organization=self.org, name='Ventas Chile')
        self.assertEqual(agente.handle, 'ventas-chile')

    def test_dos_agentes_con_el_mismo_nombre_no_chocan(self):
        primero = Agent.objects.create(organization=self.org, name='Ventas')
        segundo = Agent.objects.create(organization=self.org, name='Ventas')
        self.assertEqual(primero.handle, 'ventas')
        self.assertEqual(segundo.handle, 'ventas-2')

    def test_renombrar_no_cambia_el_handle(self):
        """Cambiarlo rompería las menciones ya escritas en los hilos."""
        agente = Agent.objects.create(organization=self.org, name='Ventas')
        agente.name = 'Comercial'
        agente.save()
        agente.refresh_from_db()
        self.assertEqual(agente.handle, 'ventas')


class MencionTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='duena@afable.test', email='duena@afable.test', password='afable123',
        )
        self.otra = User.objects.create_user(
            username='ajeno@afable.test', email='ajeno@afable.test', password='afable123',
        )
        self.org = Organization.objects.create(owner=self.user, name='Cocinas SpA')
        self.org_ajena = Organization.objects.create(owner=self.otra, name='Otra SpA')

        self.ventas = Agent.objects.create(organization=self.org, name='Ventas')
        self.finanzas = Agent.objects.create(organization=self.org, name='Finanzas')
        self.ajeno = Agent.objects.create(organization=self.org_ajena, name='Secretos')

    def test_una_mencion_al_principio_resuelve_el_agente(self):
        self.assertEqual(_agente_mencionado(self.user, '@ventas cómo vamos este mes'), self.ventas)

    def test_la_mencion_tambien_vale_en_medio_de_la_frase(self):
        self.assertEqual(
            _agente_mencionado(self.user, 'consultale a @finanzas por el flujo'), self.finanzas,
        )

    def test_manda_la_primera_mencion_cuando_hay_varias(self):
        self.assertEqual(_agente_mencionado(self.user, '@finanzas y @ventas'), self.finanzas)

    def test_un_correo_no_es_una_mencion(self):
        self.assertIsNone(_agente_mencionado(self.user, 'escribile a pepe@ventas.cl'))

    def test_una_mencion_que_no_existe_se_ignora(self):
        self.assertIsNone(_agente_mencionado(self.user, '@inventado hola'))

    def test_no_se_puede_mencionar_un_agente_de_otra_empresa(self):
        self.assertIsNone(_agente_mencionado(self.user, '@secretos qué guardan'))

    def test_un_agente_desactivado_no_se_puede_mencionar(self):
        self.ventas.is_active = False
        self.ventas.save()
        self.assertIsNone(_agente_mencionado(self.user, '@ventas hola'))

    def test_sin_texto_no_hay_mencion(self):
        self.assertIsNone(_agente_mencionado(self.user, ''))
        self.assertIsNone(_agente_mencionado(self.user, None))


class HabilidadesTests(TestCase):
    """Las Habilidades: bloques de instrucciones compartidos entre agentes."""

    def setUp(self):
        from apps.agents.models import Skill, habilidades_como_contexto

        self.Skill = Skill
        self.como_contexto = habilidades_como_contexto

        self.user = User.objects.create_user(
            username='duena@afable.test', email='duena@afable.test', password='afable123',
        )
        self.org = Organization.objects.create(owner=self.user, name='Cocinas SpA')
        self.ventas = Agent.objects.create(organization=self.org, name='Ventas')
        self.soporte = Agent.objects.create(organization=self.org, name='Soporte')

        self.tono = Skill.objects.create(
            organization=self.org, name='Tono corporativo',
            instructions='Trate de usted y no prometa plazos.',
        )

    def test_sin_habilidades_el_bloque_va_vacio(self):
        self.assertEqual(self.como_contexto(self.ventas), '')

    def test_una_habilidad_enganchada_entra_al_prompt(self):
        self.tono.agents.add(self.ventas)
        bloque = self.como_contexto(self.ventas)
        self.assertIn('Tono corporativo', bloque)
        self.assertIn('no prometa plazos', bloque)

    def test_la_misma_habilidad_sirve_para_varios_agentes(self):
        self.tono.agents.add(self.ventas, self.soporte)
        self.assertIn('Tono corporativo', self.como_contexto(self.ventas))
        self.assertIn('Tono corporativo', self.como_contexto(self.soporte))

    def test_editarla_cambia_a_todos_los_que_la_usan(self):
        """La razón de ser de la Habilidad: un solo lugar donde corregir."""
        self.tono.agents.add(self.ventas, self.soporte)
        self.tono.instructions = 'Trate de usted y sea breve.'
        self.tono.save()
        for agente in (self.ventas, self.soporte):
            self.assertIn('sea breve', self.como_contexto(agente))

    def test_una_habilidad_desactivada_no_entra(self):
        self.tono.agents.add(self.ventas)
        self.tono.is_active = False
        self.tono.save()
        self.assertEqual(self.como_contexto(self.ventas), '')

    def test_la_api_no_engancha_agentes_de_otra_empresa(self):
        otra_duena = User.objects.create_user(
            username='ajena@afable.test', email='ajena@afable.test', password='afable123',
        )
        org_ajena = Organization.objects.create(owner=otra_duena, name='Otra SpA')
        agente_ajeno = Agent.objects.create(organization=org_ajena, name='Secretos')

        client = APIClient()
        client.force_authenticate(user=self.user)
        resp = client.post(
            '/api/v1/agents/habilidades/',
            {'name': 'Nueva', 'instructions': 'Algo.', 'agent_ids': [agente_ajeno.id]},
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        creada = self.Skill.objects.get(pk=resp.json()['id'])
        self.assertEqual(creada.agents.count(), 0)

    def test_una_habilidad_sin_instrucciones_se_rechaza(self):
        client = APIClient()
        client.force_authenticate(user=self.user)
        resp = client.post(
            '/api/v1/agents/habilidades/', {'name': 'Vacía', 'instructions': '   '}, format='json',
        )
        self.assertEqual(resp.status_code, 400)

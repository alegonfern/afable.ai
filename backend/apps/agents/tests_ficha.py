"""La identidad y la ficha del agente.

Los agentes son el centro de lo que Afable ofrece, y hasta acá se presentaban como una
fila de texto: diez tarjetas con el mismo robot gris y una frase. Estas pruebas cubren lo
que hace que un agente sea reconocible (su cara) y elegible (su ficha).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.agents.models import Agent
from apps.organizations.models import CompanyDocument, Organization
from apps.workspaces.models import ROLE_ADMIN, Workspace

User = get_user_model()


class CadaAgenteTieneCaraTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='rosa@afable.test', email='rosa@afable.test', password='afable123',
        )
        self.org = Organization.objects.create(owner=self.user, name='Panadería')

    def test_un_agente_sin_cara_igual_recibe_un_color(self):
        """Si cayera vacío volvería al robot gris, que es lo que se vino a arreglar."""
        agente = Agent.objects.create(organization=self.org, name='Cobranza')
        self.assertTrue(agente.cara['accent'])

    def test_el_color_es_SIEMPRE_el_mismo_para_el_mismo_agente(self):
        """Un color que cambia entre pantallas no sirve para reconocer a nadie."""
        agente = Agent.objects.create(organization=self.org, name='Cobranza')
        primero = agente.cara['accent']
        agente.refresh_from_db()
        self.assertEqual(agente.cara['accent'], primero)

    def test_dos_agentes_distintos_no_se_ven_igual(self):
        uno = Agent.objects.create(organization=self.org, name='Cobranza')
        otro = Agent.objects.create(organization=self.org, name='Inventario')
        self.assertNotEqual(uno.cara['accent'], otro.cara['accent'])

    def test_se_respeta_el_emoji_que_eligio_la_persona(self):
        agente = Agent.objects.create(
            organization=self.org, name='Cobranza', icon='💰', accent='#123456',
        )
        self.assertEqual(agente.cara, {'icon': '💰', 'accent': '#123456'})


class LosHandlesCortosTests(TestCase):
    """`@agente-de-contabilidad` es impronunciable, y en un producto donde se invoca con
    `@` el handle ES la interfaz."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='rosa@afable.test', email='rosa@afable.test', password='afable123',
        )
        self.org = Organization.objects.create(owner=self.user, name='Panadería')
        self.agente = Agent.objects.create(
            organization=self.org, name='Agente de Contabilidad',
        )

    def test_se_acorta(self):
        from apps.agents.agentes_base import acortar_handles

        self.assertEqual(self.agente.handle, 'agente-de-contabilidad')
        self.assertEqual(acortar_handles(self.org), 1)
        self.agente.refresh_from_db()
        self.assertEqual(self.agente.handle, 'contabilidad')

    def test_NO_se_acorta_si_ya_lo_mencionaron(self):
        """⚠️ Un `@` que dejó de resolver es un mensaje del pasado que cambia de significado."""
        from apps.agents.agentes_base import acortar_handles
        from apps.agents.models import Conversation, Message

        conv = Conversation.objects.create(agent=self.agente, user=self.user)
        Message.objects.create(
            conversation=conv, role='user',
            content='@agente-de-contabilidad revisa el balance',
        )
        self.assertEqual(acortar_handles(self.org), 0)
        self.agente.refresh_from_db()
        self.assertEqual(self.agente.handle, 'agente-de-contabilidad')


class LaFichaDiceAQueAlcanzaTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='rosa@afable.test', email='rosa@afable.test', password='afable123',
        )
        self.ajeno = User.objects.create_user(
            username='otro@afable.test', email='otro@afable.test', password='afable123',
        )
        self.org = Organization.objects.create(owner=self.user, name='Panadería')
        Workspace.objects.create(organization=self.org, name='General')
        self.org.agregar_miembro(self.user, ROLE_ADMIN)
        self.agente = Agent.objects.create(
            organization=self.org, name='Afable', handle='afable',
            description='Busca en todo lo que la empresa tiene conectado.',
        )
        CompanyDocument.objects.create(
            organization=self.org, title='Lista de precios agosto',
            extracted_text='Pan amasado $2.190', content_type='text/plain',
        )

    def ficha(self, quien=None):
        self.client.force_authenticate(quien or self.user)
        return self.client.get(
            f'/api/v1/agents/{self.agente.pk}/ficha/', {'workspace': self.org.slug},
        )

    def test_nombra_los_documentos_que_alcanza(self):
        """Es la diferencia entre «una IA» y «la IA de mi empresa»."""
        r = self.ficha()
        self.assertEqual(r.status_code, 200)
        self.assertIn('Lista de precios agosto', r.data['alcance']['documentos'])
        self.assertFalse(r.data['alcance']['sin_fuentes'])

    def test_las_preguntas_de_ejemplo_usan_SUS_documentos(self):
        """Genéricas no enseñan nada; con el nombre del documento se entiende de golpe."""
        r = self.ficha()
        self.assertTrue(
            any('Lista de precios agosto' in p for p in r.data['preguntas']),
            r.data['preguntas'],
        )

    def test_sin_fuentes_se_avisa_en_vez_de_prometer(self):
        """⚠️ Quien cree que le contestan con SUS datos toma decisiones sobre arena."""
        CompanyDocument.objects.all().delete()
        r = self.ficha()
        self.assertTrue(r.data['alcance']['sin_fuentes'])
        self.assertTrue(r.data['preguntas'])   # igual se ofrece algo que sí puede hacer

    def test_un_ajeno_no_ve_la_ficha(self):
        self.client.force_authenticate(self.ajeno)
        r = self.client.get(
            f'/api/v1/agents/{self.agente.pk}/ficha/', {'workspace': self.org.slug},
        )
        self.assertIn(r.status_code, (403, 404))

    def test_cuenta_el_trabajo_registrado_y_no_lo_estima(self):
        from apps.agents.models import Conversation, Message

        conv = Conversation.objects.create(agent=self.agente, user=self.user)
        Message.objects.create(
            conversation=conv, role='assistant', content='Listo', agent=self.agente,
            artefactos=[{'id': 1, 'titulo': 'Cotización', 'accion': 'creado'}],
        )
        r = self.ficha()
        self.assertEqual(r.data['trabajo']['respuestas'], 1)
        self.assertEqual(r.data['trabajo']['documentos'], 1)

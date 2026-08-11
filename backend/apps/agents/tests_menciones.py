"""El `@` es la interfaz del producto: a quién le habla un mensaje.

Tres cosas que se pidieron mirando cómo funciona Dust, y ninguna existía:

- que **varios agentes** contesten en la misma conversación;
- que mencionar a un **compañero** le avise, y no dispare al agente;
- que un hilo compartido lo pueda **leer** el equipo, no solo escribirlo.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.agents.menciones import (
    MAX_AGENTES, agentes_mencionados, handle_de_persona, personas_mencionadas,
)
from apps.agents.models import Agent, Conversation, Message
from apps.notificaciones.models import Notificacion
from apps.organizations.models import Organization
from apps.sesiones.models import Sesion, SesionMiembro
from apps.workspaces.models import ROLE_ADMIN, Workspace

User = get_user_model()


class Base(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.ana = User.objects.create_user(
            username='ana@afable.test', email='ana@afable.test', password='afable123',
            first_name='Ana', last_name='Pérez',
        )
        self.beto = User.objects.create_user(
            username='beto@afable.test', email='beto@afable.test', password='afable123',
            first_name='Beto', last_name='Soto',
        )
        self.org = Organization.objects.create(owner=self.ana, name='Panadería')
        self.ws = Workspace.objects.create(organization=self.org, name='General')
        self.org.agregar_miembro(self.ana, ROLE_ADMIN)
        self.org.agregar_miembro(self.beto, ROLE_ADMIN)
        self.analisis = Agent.objects.create(
            organization=self.org, name='Análisis', handle='analisis',
        )
        self.datos = Agent.objects.create(
            organization=self.org, name='Datos', handle='datos',
        )
        self.sesion = Sesion.objects.create(
            workspace=self.ws, name='Cliente Rever', slug='cliente-rever',
        )
        SesionMiembro.objects.create(sesion=self.sesion, user=self.ana)
        SesionMiembro.objects.create(sesion=self.sesion, user=self.beto)


class VariosAgentesEnLaMismaConversacionTests(Base):

    def test_se_devuelven_todos_en_orden(self):
        """Antes contestaba el PRIMERO y el otro se descartaba en silencio."""
        elegidos = agentes_mencionados(
            self.org.agents.all(), '@datos hazme el gráfico y @analisis revisalo',
        )
        self.assertEqual([a.handle for a in elegidos], ['datos', 'analisis'])

    def test_hay_un_tope(self):
        """⚠️ Cada agente es una llamada al modelo: sin tope, seis menciones son seis
        consultas y un minuto de espera sin explicación."""
        for i in range(MAX_AGENTES + 2):
            Agent.objects.create(organization=self.org, name=f'Agente {i}', handle=f'a{i}')
        texto = ' '.join(f'@a{i}' for i in range(MAX_AGENTES + 2))
        self.assertEqual(len(agentes_mencionados(self.org.agents.all(), texto)), MAX_AGENTES)

    def test_una_mencion_que_no_es_un_agente_no_rompe(self):
        self.assertEqual(agentes_mencionados(self.org.agents.all(), 'escríbeme a @gmail'), [])


class MencionarAUnCompaneroTests(Base):

    def test_el_handle_sale_del_nombre(self):
        self.assertEqual(handle_de_persona(self.ana), 'ana-perez')

    def test_se_lo_encuentra_en_el_equipo(self):
        encontrados = personas_mencionadas('@ana-perez ¿lo revisas?', [self.ana, self.beto])
        self.assertEqual(encontrados, [self.ana])

    def test_si_dos_colisionan_se_avisa_a_LOS_DOS(self):
        """Adivinar haría que el pedido le llegue a quien no correspondía y nadie se entere."""
        gemela = User.objects.create_user(
            username='ana2@afable.test', email='ana2@afable.test', password='afable123',
            first_name='Ana', last_name='Pérez',
        )
        encontrados = personas_mencionadas('@ana-perez ¿lo ves?', [self.ana, gemela])
        self.assertEqual(len(encontrados), 2)

    def test_mencionar_a_una_persona_NO_dispara_al_agente(self):
        """⚠️ La regla era «¿hay un @ en el texto?», así que pedirle algo a un colega
        hacía contestar a la IA encima."""
        from apps.agents.hilos import le_hablan_a_la_ia

        self.assertFalse(le_hablan_a_la_ia(
            '@ana-perez ¿puedes revisar esto?', hay_mas_de_uno=True,
            agentes_alcanzables=self.org.agents.all(),
        ))
        self.assertTrue(le_hablan_a_la_ia(
            '@analisis ¿cuánto vendimos?', hay_mas_de_uno=True,
            agentes_alcanzables=self.org.agents.all(),
        ))


class ElAgenteEscuchaYNoInterrumpeTests(Base):
    """⚠️ La regla estaba escrita y probada desde que se construyó el chat grupal, y no
    la llamaba NADIE: el agente contestaba los 8 de 8 mensajes de un hilo entre personas."""

    def setUp(self):
        super().setUp()
        self.hilo = Conversation.objects.create(
            agent=self.analisis, user=self.ana, workspace=self.ws, sesion=self.sesion,
        )

    def test_sin_mencion_el_agente_no_contesta(self):
        self.client.force_authenticate(self.ana)
        r = self.client.post('/api/v1/agents/direct-chat/', {
            'message': 'dale, yo lo reviso mañana',
            'conversation_id': self.hilo.pk,
        }, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data.get('escucha'))
        # El mensaje SÍ queda: el agente escucha, no ignora.
        self.assertEqual(self.hilo.messages.filter(role='user').count(), 1)
        self.assertEqual(self.hilo.messages.filter(role='assistant').count(), 0)

    def test_al_mencionar_a_alguien_le_llega_el_aviso(self):
        self.client.force_authenticate(self.ana)
        self.client.post('/api/v1/agents/direct-chat/', {
            'message': '@beto-soto ¿puedes revisar esta respuesta?',
            'conversation_id': self.hilo.pk,
        }, format='json')
        aviso = Notificacion.objects.filter(user=self.beto).first()
        self.assertIsNotNone(aviso)
        self.assertIn('te mencionó', aviso.titulo)


class UnHiloCompartidoSePuedeLEERTests(Base):
    """⚠️ `messages/` filtraba por `user=request.user`: compartir dejaba ver el hilo en la
    lista y daba 404 al abrirlo."""

    def test_un_companero_de_la_sesion_lo_abre(self):
        hilo = Conversation.objects.create(
            agent=self.analisis, user=self.ana, workspace=self.ws, sesion=self.sesion,
        )
        Message.objects.create(conversation=hilo, role='user', content='hola', user=self.ana)

        self.client.force_authenticate(self.beto)
        r = self.client.get(f'/api/v1/agents/conversations/{hilo.pk}/messages/')
        self.assertEqual(r.status_code, 200)

    def test_un_hilo_personal_sigue_siendo_privado(self):
        privado = Conversation.objects.create(agent=self.analisis, user=self.ana)
        self.client.force_authenticate(self.beto)
        r = self.client.get(f'/api/v1/agents/conversations/{privado.pk}/messages/')
        self.assertEqual(r.status_code, 404)

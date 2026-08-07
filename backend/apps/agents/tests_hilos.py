"""Varias personas en el mismo hilo con la IA.

Hasta acá una conversación era de una sola persona (`user=request.user` en la consulta),
así que compartirla en una Sesión servía para LEER y no para participar.

⭐ Lo que estas pruebas protegen, y es lo único que no se puede romper: **la respuesta se
arma con lo que alcanza quien PREGUNTA, no quien abrió el hilo.** Sin eso, un hilo
compartido sería la forma más cómoda de leer lo que uno no puede ver — basta que alguien
con más acceso lo abra e invite— y rompería sin dejar rastro la propiedad que el producto
promete: nadie puede usar un agente para alcanzar lo que él no alcanza.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import NotFound
from rest_framework.test import APIClient

from apps.organizations.models import Organization
from apps.sesiones.models import Sesion, SesionMiembro
from apps.workspaces.models import ROLE_ADMIN, ROLE_MEMBER, Workspace

from .hilos import hilo_para_escribir, le_hablan_a_la_ia
from .models import Agent, Conversation, Message

User = get_user_model()


def usuario(email):
    return User.objects.create_user(username=email, email=email, password='afable123')


class QuienEscribeEnUnHiloTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.duena = usuario('duena@afable.test')
        self.companera = usuario('companera@afable.test')
        self.ajena = usuario('ajena@afable.test')

        self.org = Organization.objects.create(owner=self.duena, name='Cocinas SpA')
        for quien, rol in [(self.duena, ROLE_ADMIN), (self.companera, ROLE_MEMBER)]:
            self.org.agregar_miembro(quien, rol)
        self.ws = Workspace.objects.create(organization=self.org, name='General')
        self.agente = Agent.objects.create(organization=self.org, name='Afable')

        self.sesion = Sesion.objects.create(
            workspace=self.ws, name='Cliente Rever', created_by=self.duena,
        )
        self.hilo_de_equipo = Conversation.objects.create(
            agent=self.agente, user=self.duena, sesion=self.sesion, title='Plazos',
        )
        self.hilo_personal = Conversation.objects.create(
            agent=self.agente, user=self.duena, title='Mis cosas',
        )

    # ── Quién entra ──────────────────────────────────────────────────────────

    def test_quien_lo_abrio_escribe_en_su_hilo_personal(self):
        self.assertEqual(
            hilo_para_escribir(self.duena, self.hilo_personal.id).id, self.hilo_personal.id,
        )

    def test_un_hilo_personal_no_lo_escribe_nadie_mas(self):
        """Compartir es una decisión: mientras no esté en una Sesión, es privado."""
        with self.assertRaises(NotFound):
            hilo_para_escribir(self.companera, self.hilo_personal.id)

    def test_en_un_hilo_de_la_sesion_escribe_el_equipo(self):
        """Es el cambio: antes la compañera podía leerlo y recibía 404 al responder."""
        self.assertEqual(
            hilo_para_escribir(self.companera, self.hilo_de_equipo.id).id,
            self.hilo_de_equipo.id,
        )

    def test_alguien_de_otra_empresa_no_entra(self):
        with self.assertRaises(NotFound):
            hilo_para_escribir(self.ajena, self.hilo_de_equipo.id)

    def test_una_sesion_restringida_no_deja_entrar_a_quien_no_esta_dentro(self):
        self.sesion.visibility = 'restringida'
        self.sesion.save()
        SesionMiembro.objects.create(sesion=self.sesion, user=self.duena, role='editor')

        with self.assertRaises(NotFound):
            hilo_para_escribir(self.companera, self.hilo_de_equipo.id)

    # ── Quién dijo qué ───────────────────────────────────────────────────────

    def test_cada_mensaje_queda_firmado(self):
        """Sin el autor, un hilo de equipo es una lista de frases sin dueño."""
        mio = Message.objects.create(
            conversation=self.hilo_de_equipo, role='user', content='¿Y el plazo?',
            user=self.companera,
        )
        del_agente = Message.objects.create(
            conversation=self.hilo_de_equipo, role='assistant', content='45 días.',
            agent=self.agente,
        )
        self.assertEqual(mio.user, self.companera)
        self.assertIsNone(del_agente.user, 'la respuesta la firma el agente, no una persona')

    # ── Cuándo contesta la IA ────────────────────────────────────────────────

    def test_en_un_hilo_de_una_persona_contesta_siempre(self):
        self.assertTrue(le_hablan_a_la_ia('¿cuánto vendimos?', hay_mas_de_uno=False))

    def test_en_un_hilo_de_equipo_contesta_solo_si_la_mencionan(self):
        """Un asistente que responde cada mensaje de cinco personas termina apagado."""
        self.assertFalse(le_hablan_a_la_ia('dale, yo lo reviso mañana', hay_mas_de_uno=True))
        self.assertTrue(le_hablan_a_la_ia('@afable ¿cuánto vendimos?', hay_mas_de_uno=True))


class ConQuePermisosSeContestaTests(TestCase):
    """⭐ La respuesta se arma con lo que alcanza QUIEN PREGUNTA."""

    def setUp(self):
        self.duena = usuario('duena@afable.test')
        self.companera = usuario('companera@afable.test')
        self.org = Organization.objects.create(owner=self.duena, name='Cocinas SpA')
        self.org.agregar_miembro(self.duena, ROLE_ADMIN)
        self.org.agregar_miembro(self.companera, ROLE_MEMBER)

    def test_el_contexto_sale_de_quien_pregunta_y_no_del_dueno_del_hilo(self):
        from apps.organizations.models import CompanyDocument
        from apps.workspaces.permissions import membership_por_organizacion

        from .views import _build_onboarding_context

        # Un documento restringido: sólo lo alcanza quien lo subió.
        reservado = CompanyDocument.objects.create(
            organization=self.org, title='Sueldos 2026', file='s.pdf',
            content_type='application/pdf', restringido=True, uploaded_by=self.duena,
        )

        contexto_companera = _build_onboarding_context(self.companera, consulta='sueldos')
        self.assertNotIn(
            reservado.title, contexto_companera['system_prompt'],
            'un hilo compartido no puede ser la vía para leer lo que no se alcanza',
        )

        contexto_duena = _build_onboarding_context(self.duena, consulta='sueldos')
        self.assertIn(reservado.title, contexto_duena['system_prompt'])
        # La membresía de cada una es la que decide, no quién abrió el hilo.
        self.assertIsNotNone(membership_por_organizacion(self.companera, self.org))

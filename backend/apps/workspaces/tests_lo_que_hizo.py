""""Mientras no estaba": la evidencia de que los agentes trabajaron solos.

Lo que fijan estas pruebas:

- **Cuenta lo que quedó registrado, no lo que alguien pidió.** Una conversación que abrió
  una persona no aparece; una que abrió un Disparador, sí.
- **Respeta los permisos.** Si mostrara lo que pasó en un Workspace al que no se entra,
  este resumen sería la forma más tonta de filtrar lo que el resto de la app cuida.
- **Sin nada que contar, devuelve vacío** — y la pantalla no se dibuja.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.agents.models import Agent, Conversation
from apps.organizations.models import Organization
from apps.sesiones.models import Sesion, Task

from .lo_que_hizo_afable import lo_que_hizo
from .models import ROLE_ADMIN, ROLE_MEMBER, VISIBILITY_RESTRICTED, Workspace
from .permissions import membership_por_organizacion

User = get_user_model()


class LoQueHizoAfableTests(TestCase):

    def setUp(self):
        self.jefa = User.objects.create_user(
            username='jefa@afable.test', email='jefa@afable.test', password='afable123',
        )
        self.equipo = User.objects.create_user(
            username='equipo@afable.test', email='equipo@afable.test', password='afable123',
        )
        self.empresa = Organization.objects.create(owner=self.jefa, name='Cocinas SpA')
        self.empresa.agregar_miembro(self.jefa, ROLE_ADMIN)
        self.empresa.agregar_miembro(self.equipo, ROLE_MEMBER)

        self.general = Workspace.objects.create(organization=self.empresa, name='General')
        self.agente = Agent.objects.create(organization=self.empresa, name='Agente SII')
        self.sesion = Sesion.objects.create(
            workspace=self.general, name='Cliente Rever', created_by=self.jefa,
        )

    def resumen(self, quien):
        return lo_que_hizo(membership_por_organizacion(quien, self.empresa))

    # ── Qué cuenta ───────────────────────────────────────────────────────────

    def test_sin_nada_que_contar_no_hay_nada_que_mostrar(self):
        """Un panel que dice "0 esta semana" es un recordatorio de que no sirve."""
        self.assertEqual(self.resumen(self.jefa)['items'], [])

    def test_cuenta_lo_que_publico_un_agente_por_su_cuenta(self):
        Conversation.objects.create(
            agent=self.agente, user=self.jefa, sesion=self.sesion,
            title='Resumen de ventas', autonoma=True,
        )
        datos = self.resumen(self.jefa)

        self.assertEqual(datos['total'], 1)
        self.assertEqual(datos['items'][0]['tipo'], 'publicacion')
        self.assertEqual(datos['items'][0]['quien'], 'Agente SII')
        self.assertEqual(datos['items'][0]['donde'], 'Cliente Rever')

    def test_lo_que_escribio_una_persona_no_cuenta(self):
        """El panel es sobre trabajo AUTÓNOMO: si contara todo, no probaría nada."""
        Conversation.objects.create(
            agent=self.agente, user=self.jefa, sesion=self.sesion, title='Yo pregunté',
        )
        self.assertEqual(self.resumen(self.jefa)['items'], [])

    def test_cuenta_la_tarea_que_ejecuto_un_agente(self):
        Task.objects.create(
            sesion=self.sesion, title='Revisar el tracker', agent=self.agente,
            ejecutada_at=timezone.now(), created_by=self.jefa,
        )
        datos = self.resumen(self.jefa)

        self.assertEqual(datos['items'][0]['tipo'], 'tarea')
        self.assertEqual(datos['items'][0]['titulo'], 'Revisar el tracker')

    def test_una_tarea_sin_ejecutar_todavia_no_es_algo_que_paso(self):
        Task.objects.create(
            sesion=self.sesion, title='Pendiente', agent=self.agente, created_by=self.jefa,
        )
        self.assertEqual(self.resumen(self.jefa)['items'], [])

    # ── Permisos ─────────────────────────────────────────────────────────────

    def test_no_muestra_lo_que_paso_en_un_workspace_al_que_no_se_entra(self):
        reservado = Workspace.objects.create(
            organization=self.empresa, name='Directorio', visibility=VISIBILITY_RESTRICTED,
        )
        reservado.members.add(self.jefa)
        sesion_reservada = Sesion.objects.create(
            workspace=reservado, name='Sueldos', created_by=self.jefa,
        )
        Conversation.objects.create(
            agent=self.agente, user=self.jefa, sesion=sesion_reservada,
            title='Ajuste de sueldos', autonoma=True,
        )

        # La administradora entra a todos los Workspaces.
        self.assertEqual(self.resumen(self.jefa)['total'], 1)
        # El equipo no: para él, eso no pasó.
        self.assertEqual(self.resumen(self.equipo)['items'], [])

    # ── Ventana de tiempo ────────────────────────────────────────────────────

    def test_lo_viejo_queda_fuera_de_la_semana(self):
        vieja = Conversation.objects.create(
            agent=self.agente, user=self.jefa, sesion=self.sesion,
            title='De hace un mes', autonoma=True,
        )
        Conversation.objects.filter(pk=vieja.pk).update(
            created_at=timezone.now() - timezone.timedelta(days=30),
        )
        membership = membership_por_organizacion(self.jefa, self.empresa)

        self.assertEqual(lo_que_hizo(membership, dias=7)['items'], [])
        self.assertEqual(lo_que_hizo(membership, dias=60)['total'], 1)

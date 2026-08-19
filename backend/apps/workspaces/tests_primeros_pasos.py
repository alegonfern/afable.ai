"""Pruebas de la primera hora.

Lo que fijan, que es lo que hace que el panel sirva:

- **El avance sale del estado real**, así que se puede DESHACER: quien borra su única
  conexión vuelve a ver el paso pendiente. Es la razón de no guardar tildes.
- **Sólo lo ve el administrador**: los seis pasos son cosas que nadie más puede hacer.
- Cerrarlo dura, y se puede volver a abrir.
- Un agente de fábrica no cuenta como haber armado uno; una conversación que abrió un
  Disparador solo, tampoco cuenta como haber preguntado.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.agents.models import Agent, Conversation, Message
from apps.organizations.models import CompanyDocument, SystemConnection

from apps.organizations.models import Organization

from .models import ROLE_EDITOR, Workspace

User = get_user_model()

URL = '/api/v1/workspaces/{}/primeros-pasos/'


class PrimerosPasosTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username='dueña@afable.test', email='dueña@afable.test',
            password='afable123', first_name='Alexis',
        )
        # Como al registrarse: el Workspace se crea solo, con nombre automático y una
        # sola persona adentro.
        self.org = Organization.crear_para_dueno(self.admin)
        # El General que `crear_para_dueno` deja listo.
        self.ws = Workspace.general_de(self.org)

    def pasos(self, usuario=None):
        self.client.force_authenticate(usuario or self.admin)
        r = self.client.get(URL.format(self.org.slug))
        self.assertEqual(r.status_code, 200)
        return {p['id']: p['hecho'] for p in r.data['pasos']}, r.data

    # ── El estado de recién registrado ───────────────────────────────────────────

    def test_recien_registrado_no_tiene_nada_hecho(self):
        hechos, datos = self.pasos()
        self.assertEqual(datos['hechos'], 0)
        self.assertEqual(datos['total'], 6)
        self.assertFalse(datos['terminado'])
        self.assertFalse(any(hechos.values()))

    def test_el_nombre_automatico_no_cuenta_como_presentarse(self):
        """`Workspace de Alexis` es el nombre que puso el sistema, no la empresa."""
        self.assertTrue(self.org.name.startswith('Empresa de '))
        hechos, _ = self.pasos()
        self.assertFalse(hechos['empresa'])

    def test_cambiar_solo_el_nombre_no_alcanza(self):
        """Sin rubro, descripción ni logo, el agente no sabe de qué se trata la empresa."""
        self.org.name = 'Cocinas SpA'
        self.org.save()
        hechos, _ = self.pasos()
        self.assertFalse(hechos['empresa'])

    def test_nombre_mas_rubro_completa_el_paso(self):
        self.org.name = 'Cocinas SpA'
        self.org.sector = 'retail'
        self.org.save()
        hechos, _ = self.pasos()
        self.assertTrue(hechos['empresa'])

    # ── Se calcula, así que se puede deshacer ────────────────────────────────────

    def test_borrar_la_unica_conexion_devuelve_el_paso_a_pendiente(self):
        """⭐ La razón de calcular en vez de guardar: el panel no puede mentir."""
        conexion = SystemConnection.objects.create(
            organization=self.org, name='Odoo', connector_type='odoo',
        )
        hechos, _ = self.pasos()
        self.assertTrue(hechos['conocimiento'])

        conexion.delete()
        hechos, _ = self.pasos()
        self.assertFalse(hechos['conocimiento'], 'sin conexión, el paso vuelve a faltar')

    def test_un_documento_tambien_alcanza(self):
        CompanyDocument.objects.create(
            organization=self.org, title='Reglamento', file='r.pdf',
            content_type='application/pdf',
        )
        hechos, datos = self.pasos()
        self.assertTrue(hechos['conocimiento'])
        detalle = next(p['detalle'] for p in datos['pasos'] if p['id'] == 'conocimiento')
        self.assertEqual(detalle, '1 documento · 0 conexiones')

    # ── Lo que NO cuenta ─────────────────────────────────────────────────────────

    def test_un_agente_de_fabrica_no_cuenta_como_haber_armado_uno(self):
        """Los sembrados vienen sin `created_by`: tenerlos no es haberlo hecho."""
        Agent.objects.create(organization=self.org, name='Agente SII')
        hechos, _ = self.pasos()
        self.assertFalse(hechos['agente'])

        Agent.objects.create(organization=self.org, name='Cotizador', created_by=self.admin)
        hechos, _ = self.pasos()
        self.assertTrue(hechos['agente'])

    def test_preguntar_sin_respuesta_no_es_haber_probado(self):
        agente = Agent.objects.create(organization=self.org, name='Afable')
        conv = Conversation.objects.create(agent=agente, user=self.admin, title='hola')
        Message.objects.create(conversation=conv, role='user', content='¿cuánto vendí?')

        hechos, _ = self.pasos()
        self.assertFalse(hechos['pregunta'])

        Message.objects.create(conversation=conv, role='assistant', content='$3.000.000')
        hechos, _ = self.pasos()
        self.assertTrue(hechos['pregunta'])

    def test_lo_que_publica_un_disparador_solo_no_cuenta_como_preguntar(self):
        """Que un agente publique por su cuenta no significa que la persona haya probado."""
        agente = Agent.objects.create(organization=self.org, name='Afable')
        conv = Conversation.objects.create(
            agent=agente, user=self.admin, title='Resumen diario', autonoma=True,
        )
        Message.objects.create(conversation=conv, role='assistant', content='Ventas de ayer...')

        hechos, _ = self.pasos()
        self.assertFalse(hechos['pregunta'])

    def test_una_invitacion_sin_aceptar_ya_cuenta_como_invitar(self):
        """Invitó: que la otra persona todavía no entre no es cosa suya."""
        hechos, _ = self.pasos()
        self.assertFalse(hechos['equipo'])

        self.org.invitations.create(
            email='nuevo@afable.test', token='tok-inv', expires_at='2030-01-01T00:00:00Z',
            invited_by=self.admin,
        )
        hechos, _ = self.pasos()
        self.assertTrue(hechos['equipo'])

    def test_un_segundo_miembro_tambien_completa_el_paso(self):
        """Da igual cómo entró: si el equipo ya está adentro, el paso está hecho."""
        otro = User.objects.create_user(
            username='otro@afable.test', email='otro@afable.test', password='afable123',
        )
        self.org.agregar_miembro(otro, ROLE_EDITOR)
        hechos, _ = self.pasos()
        self.assertTrue(hechos['equipo'])

    # ── Quién lo ve ──────────────────────────────────────────────────────────────

    def test_un_editor_no_ve_los_primeros_pasos(self):
        """Una lista de tareas que no puede completar es una lista de frustraciones."""
        editor = User.objects.create_user(
            username='editor@afable.test', email='editor@afable.test', password='afable123',
        )
        self.org.agregar_miembro(editor, ROLE_EDITOR)
        self.client.force_authenticate(editor)
        r = self.client.get(URL.format(self.org.slug))
        self.assertEqual(r.status_code, 403)

    def test_alguien_de_afuera_no_ve_que_el_workspace_existe(self):
        ajeno = User.objects.create_user(
            username='ajeno@afable.test', email='ajeno@afable.test', password='afable123',
        )
        self.client.force_authenticate(ajeno)
        self.assertEqual(self.client.get(URL.format(self.org.slug)).status_code, 404)

    # ── Cerrarlo ─────────────────────────────────────────────────────────────────

    def test_cerrarlo_dura_y_se_puede_volver_a_abrir(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(URL.format(self.org.slug), {})
        self.assertTrue(r.data['oculto'])

        _, datos = self.pasos()
        self.assertTrue(datos['oculto'], 'el cierre tiene que sobrevivir a recargar')

        self.client.force_authenticate(self.admin)
        r = self.client.post(URL.format(self.org.slug), {'mostrar': True})
        self.assertFalse(r.data['oculto'])

    def test_completar_todo_lo_marca_terminado(self):
        self.org.name = 'Cocinas SpA'
        self.org.sector = 'retail'
        self.org.save()
        SystemConnection.objects.create(
            organization=self.org, name='Odoo', connector_type='odoo',
        )
        agente = Agent.objects.create(
            organization=self.org, name='Cotizador', created_by=self.admin,
        )
        conv = Conversation.objects.create(agent=agente, user=self.admin)
        Message.objects.create(conversation=conv, role='assistant', content='listo')
        self.org.invitations.create(
            email='nuevo@afable.test', token='t1', expires_at='2030-01-01T00:00:00Z',
            invited_by=self.admin,
        )
        from apps.payments.models import Plan, Subscription
        plan = Plan.objects.create(id='p1', name='Growth', price_clp=299_000, price_usd=299)
        Subscription.objects.create(
            organization=self.org, plan=plan, aprobada=True,
            status=Subscription.ESTADO_ACTIVA,
        )

        _, datos = self.pasos()
        self.assertEqual(datos['hechos'], 6)
        self.assertTrue(datos['terminado'])

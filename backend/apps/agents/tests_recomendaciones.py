"""Las recomendaciones que se calculan.

La prueba que sostiene todo el diseño es `test_no_llama_al_modelo_ni_una_vez`. Si alguna
vez alguien agrega una recomendación «inteligente» que le pregunta a la IA qué sugerir, esa
prueba falla — y tiene que fallar, porque ese es el momento exacto en que el producto se
convierte en una máquina de quemar tokens de fondo.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.agents.models import Agent
from apps.archivos.models import Carpeta, SolicitudDePublicacion
from apps.organizations.models import CompanyDocument, Organization, SystemConnection
from apps.workspaces.models import ROLE_ADMIN, ROLE_MEMBER, Membership
from services.estructura_inicial import carpeta_personal, crear_estructura
from services.propuestas_de_agente import UMBRAL_DOCUMENTOS
from services.recomendaciones import TOPE, para

User = get_user_model()


class RecomendacionesTests(TestCase):
    def setUp(self):
        self.duena = User.objects.create_user(
            username='duena@afable.test', email='duena@afable.test', password='x',
        )
        self.empleado = User.objects.create_user(
            username='empleado@afable.test', email='empleado@afable.test', password='x',
        )
        self.org = Organization.objects.create(owner=self.duena, name='Cocinas SpA')
        self.org.agregar_miembro(self.duena, ROLE_ADMIN)
        self.m_duena = Membership.objects.get(organization=self.org, user=self.duena)

    def _sumar_empleado(self):
        self.org.agregar_miembro(self.empleado, ROLE_MEMBER)
        return Membership.objects.get(organization=self.org, user=self.empleado)

    def claves(self, usuario=None, membership=None):
        recomendaciones = para(self.org, usuario or self.duena, membership or self.m_duena)
        return [r['clave'] for r in recomendaciones]

    # ── lo que no cuesta ─────────────────────────────────────────────────────

    def test_no_llama_al_modelo_ni_una_vez(self):
        """El corazón del diseño: recomendar es una consulta, solo actuar cuesta."""
        crear_estructura(self.org, 'general', self.duena)
        carpeta = Carpeta.objects.get(organization=self.org, name='Facturación')
        for i in range(UMBRAL_DOCUMENTOS):
            CompanyDocument.objects.create(
                organization=self.org, title=f'F{i}', file=f'f{i}.pdf', carpeta=carpeta,
            )

        with mock.patch('services.agent_service.chat_direct') as llamada:
            para(self.org, self.duena, self.m_duena)

        llamada.assert_not_called()

    # ── qué se recomienda, y cuándo ──────────────────────────────────────────

    def test_una_empresa_vacia_recibe_el_primer_paso(self):
        self.assertIn('armar_empresa', self.claves())

    def test_con_la_empresa_armada_ya_no_se_ofrece_armarla(self):
        crear_estructura(self.org, 'general', self.duena)
        self.assertNotIn('armar_empresa', self.claves())

    def test_una_carpeta_con_material_ofrece_su_agente(self):
        crear_estructura(self.org, 'general', self.duena)
        carpeta = Carpeta.objects.get(organization=self.org, name='Facturación')
        for i in range(UMBRAL_DOCUMENTOS):
            CompanyDocument.objects.create(
                organization=self.org, title=f'F{i}', file=f'f{i}.pdf', carpeta=carpeta,
            )

        self.assertIn(f'agente_{carpeta.pk}', self.claves())

    def test_lo_que_espera_aprobacion_se_avisa(self):
        crear_estructura(self.org, 'general', self.duena)
        membership = self._sumar_empleado()
        mia = carpeta_personal(self.org, self.empleado)
        destino = Carpeta.objects.get(organization=self.org, name='Contabilidad')
        doc = CompanyDocument.objects.create(
            organization=self.org, title='Gastos', file='g.xlsx',
            uploaded_by=self.empleado, carpeta=mia,
        )
        SolicitudDePublicacion.objects.create(
            document=doc, solicitada_por=self.empleado, destino=destino,
        )

        self.assertIn('aprobar_publicaciones', self.claves())
        # Al empleado no le toca aprobar nada: es cosa de quien puede editar.
        self.assertNotIn('aprobar_publicaciones', self.claves(self.empleado, membership))

    def test_a_quien_esta_solo_se_le_dice(self):
        crear_estructura(self.org, 'general', self.duena)
        self.assertIn('invitar', self.claves())

        self._sumar_empleado()
        self.assertNotIn('invitar', self.claves())

    def test_documentos_sin_una_sola_pregunta(self):
        crear_estructura(self.org, 'general', self.duena)
        carpeta = Carpeta.objects.get(organization=self.org, name='Legal')
        CompanyDocument.objects.create(
            organization=self.org, title='Contrato', file='c.pdf', carpeta=carpeta,
        )

        self.assertIn('primera_pregunta', self.claves())

    def test_conectar_va_al_final_y_desaparece_al_conectar(self):
        """El producto entra por documentos y equipo: empujar la integración antes es la
        estrategia anterior."""
        crear_estructura(self.org, 'general', self.duena)
        self.assertIn('conectar', [r['clave'] for r in para(self.org, self.duena, self.m_duena)]
                      or self.claves())

        SystemConnection.objects.create(
            organization=self.org, name='Odoo', connector_type='odoo', category='erp',
        )
        self.assertNotIn('conectar', self.claves())

    # ── a quién se le habla ──────────────────────────────────────────────────

    def test_a_un_miembro_no_se_le_ofrece_lo_que_no_puede_hacer(self):
        """Una lista de tareas que no se pueden completar es una lista de frustraciones."""
        membership = self._sumar_empleado()

        claves = self.claves(self.empleado, membership)
        self.assertNotIn('armar_empresa', claves)
        self.assertNotIn('invitar', claves)
        self.assertNotIn('conectar', claves)

    def test_al_miembro_sin_nada_se_le_ofrece_lo_suyo(self):
        crear_estructura(self.org, 'general', self.duena)
        membership = self._sumar_empleado()

        self.assertIn('subir_lo_mio', self.claves(self.empleado, membership))

    # ── cuántas ──────────────────────────────────────────────────────────────

    def test_nunca_mas_de_tres(self):
        """Una lista larga de consejos deja de leerse y pasa a ser decoración."""
        crear_estructura(self.org, 'general', self.duena)
        for nombre in ('Facturación', 'Legal', 'Ventas', 'Clientes'):
            carpeta = Carpeta.objects.get(organization=self.org, name=nombre)
            for i in range(UMBRAL_DOCUMENTOS):
                CompanyDocument.objects.create(
                    organization=self.org, title=f'{nombre} {i}',
                    file=f'{nombre}{i}.pdf', carpeta=carpeta,
                )

        self.assertLessEqual(len(para(self.org, self.duena, self.m_duena)), TOPE)

    def test_cuando_no_falta_nada_no_se_inventa_nada(self):
        """Un producto que siempre tiene algo que decirte deja de decir algo cuando importa."""
        crear_estructura(self.org, 'general', self.duena)
        self._sumar_empleado()
        SystemConnection.objects.create(
            organization=self.org, name='Odoo', connector_type='odoo', category='erp',
        )
        carpeta = Carpeta.objects.get(organization=self.org, name='Facturación')
        doc = CompanyDocument.objects.create(
            organization=self.org, title='F1', file='f1.pdf', carpeta=carpeta,
        )
        agente = Agent.objects.create(organization=self.org, name='Facturación', carpeta=carpeta)
        from apps.agents.models import Conversation
        Conversation.objects.create(agent=agente, user=self.duena)

        self.assertEqual(para(self.org, self.duena, self.m_duena), [])


class EndpointDeRecomendacionesTests(TestCase):
    def setUp(self):
        from rest_framework.test import APIClient

        self.client = APIClient()
        self.duena = User.objects.create_user(
            username='d@afable.test', email='d@afable.test', password='x',
        )
        self.org = Organization.objects.create(owner=self.duena, name='Cocinas SpA')
        self.org.agregar_miembro(self.duena, ROLE_ADMIN)
        self.client.force_authenticate(self.duena)

    def test_devuelve_las_recomendaciones_con_su_mensaje(self):
        r = self.client.get('/api/v1/agents/recomendaciones/', {'workspace': self.org.slug})

        self.assertEqual(r.status_code, 200)
        primera = r.data['recomendaciones'][0]
        self.assertTrue(primera['texto'])
        # `mensaje` es lo que se manda al chat al tocarla: sin eso el atajo no hace nada.
        self.assertTrue(primera['mensaje'])

    def test_sin_empresa_no_responde(self):
        r = self.client.get('/api/v1/agents/recomendaciones/')
        self.assertEqual(r.status_code, 400)

    def test_hay_que_estar_autenticado(self):
        self.client.force_authenticate(None)
        r = self.client.get('/api/v1/agents/recomendaciones/', {'workspace': self.org.slug})
        self.assertIn(r.status_code, (401, 403))

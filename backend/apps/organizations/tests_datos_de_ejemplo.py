"""La empresa de ejemplo: poder probar Afable antes de cargar nada.

Lo que fijan estas pruebas es lo que hace que el ejemplo sirva y no engañe:

- Son **documentos de verdad**, así que recorren el mismo camino que los de un cliente y
  el agente los puede citar. Un "modo demo" con respuestas simuladas no probaría nada.
- Van **marcados** y se quitan de una sola vez. Si quedaran mezclados con los datos
  reales, el agente citaría un contrato inventado como si fuera de la empresa — la peor
  forma posible de perder la confianza de un cliente.
- **No se duplican** al pedirlos dos veces.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.workspaces.models import ROLE_ADMIN, ROLE_MEMBER, Workspace

from .datos_de_ejemplo import WORKSPACE_EJEMPLO, crear_para, quitar_de
from .models import CompanyDocument, Organization

User = get_user_model()


class DatosDeEjemploTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username='admin@afable.test', email='admin@afable.test', password='afable123',
        )
        self.miembro = User.objects.create_user(
            username='miembro@afable.test', email='miembro@afable.test', password='afable123',
        )
        self.empresa = Organization.objects.create(owner=self.admin, name='Cocinas SpA')
        self.empresa.agregar_miembro(self.admin, ROLE_ADMIN)
        self.empresa.agregar_miembro(self.miembro, ROLE_MEMBER)

    def url(self):
        return f'/api/v1/workspaces/{self.empresa.slug}/ejemplo/'

    # ── Lo que deja ──────────────────────────────────────────────────────────

    def test_deja_documentos_de_verdad_en_su_propio_workspace(self):
        workspace, creados = crear_para(self.empresa, creado_por=self.admin)

        self.assertEqual(creados, 5)
        self.assertEqual(workspace.name, WORKSPACE_EJEMPLO)
        self.assertEqual(workspace.documents.count(), 5)

        # Con texto extraído: es lo que el agente lee y cita. Sin esto el ejemplo sería
        # una lista de títulos vacíos.
        for doc in workspace.documents.all():
            self.assertTrue(doc.extracted_text.strip())
            self.assertEqual(doc.source, 'ejemplo')

    def test_los_documentos_se_cruzan_entre_si(self):
        """La gracia del ejemplo es poder preguntar algo que obligue a mirar dos."""
        crear_para(self.empresa)
        textos = ' '.join(
            CompanyDocument.objects.filter(organization=self.empresa).values_list(
                'extracted_text', flat=True,
            )
        )
        # El descuento por volumen aparece en la lista de precios y en el contrato.
        self.assertIn('22%', textos)
        self.assertIn('Comercial Andes', textos)

    def test_no_se_duplican_al_pedirlos_dos_veces(self):
        crear_para(self.empresa)
        _, segunda = crear_para(self.empresa)

        self.assertEqual(segunda, 0)
        self.assertEqual(
            CompanyDocument.objects.filter(organization=self.empresa, source='ejemplo').count(), 5,
        )

    # ── Que se puedan sacar ──────────────────────────────────────────────────

    def test_se_quitan_de_una_sola_vez(self):
        """Mezclados con los datos reales, el agente citaría un contrato inventado."""
        crear_para(self.empresa)
        borrados = quitar_de(self.empresa)

        self.assertEqual(borrados, 5)
        self.assertEqual(CompanyDocument.objects.filter(organization=self.empresa).count(), 0)
        self.assertFalse(
            Workspace.objects.filter(organization=self.empresa, name=WORKSPACE_EJEMPLO).exists(),
        )

    def test_quitarlos_no_toca_los_documentos_reales(self):
        crear_para(self.empresa)
        mio = CompanyDocument.objects.create(
            organization=self.empresa, title='Mi contrato', file='c.pdf',
            content_type='application/pdf', extracted_text='lo mio',
        )

        quitar_de(self.empresa)

        self.assertTrue(CompanyDocument.objects.filter(pk=mio.pk).exists())

    # ── Quién puede ──────────────────────────────────────────────────────────

    def test_el_administrador_los_carga_desde_la_api(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(self.url())

        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['documentos'], 5)
        # Las preguntas sugeridas viajan con la respuesta: quien recién llega no tiene
        # que inventar qué preguntar, que es donde la gente se traba.
        self.assertTrue(r.data['preguntas'])

    def test_un_miembro_no_llena_la_empresa_de_datos_falsos(self):
        self.client.force_authenticate(self.miembro)
        self.assertEqual(self.client.post(self.url()).status_code, 403)

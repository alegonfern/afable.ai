"""Que lo que el agente deja ESCRITO llegue siempre al mensaje.

Sin esto el agente escribe un documento, lo cuenta en una frase, y la persona tiene que
salir a otra pantalla a buscarlo y confiar en que está. La tarjeta del chat es lo que
cierra ese recorrido — y por eso no puede depender de que el modelo se porte bien.

Ninguna prueba habla con un modelo: se ejecutan las herramientas directo.
"""
import unittest.mock as mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.organizations.models import CompanyDocument, Organization
from apps.workspaces.models import ROLE_ADMIN, Workspace
from services import agent_service, agent_tools

User = get_user_model()


class LoEscritoViajaConLaRespuestaTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='ana@afable.test', email='ana@afable.test', password='afable123',
        )
        self.org = Organization.objects.create(owner=self.user, name='Panadería')
        Workspace.objects.create(organization=self.org, name='General')
        self.org.agregar_miembro(self.user, ROLE_ADMIN)

    def test_crear_un_documento_deja_su_tarjeta(self):
        artifacts = {}
        r = agent_tools.execute_tool(
            'crear_documento', {'titulo': 'Cotización', 'contenido': 'Total: $52.670'},
            self.org, [], None, artifacts,
        )
        self.assertEqual(
            artifacts['documentos'],
            [{'id': r['id'], 'titulo': 'Cotización', 'accion': 'creado'}],
        )

    def test_si_el_modelo_se_cae_DESPUES_de_escribir_la_tarjeta_sale_igual(self):
        """⚠️ El trabajo ya está hecho: el documento existe.

        Si el aviso se perdiera por un tropiezo del modelo, la persona veria un error y
        no sabria que ademas quedo un documento suyo dando vueltas.
        """
        eventos = []

        def falso_post(*a, **k):
            raise agent_service.requests.exceptions.ConnectionError('modelo caído')

        with mock.patch.object(agent_service, '_post_chat', falso_post):
            for e in agent_service.run_agent_live_events(
                [{'role': 'user', 'content': 'hola'}], self.org, 'prompt',
                'gpt-oss:120b-cloud',
            ):
                eventos.append(e)

        final = [e for e in eventos if 'final' in e][-1]
        # Aunque no haya documentos en este caso, la CLAVE tiene que venir siempre: si
        # faltara, la pantalla no sabría distinguir "no escribió nada" de "se perdió".
        self.assertIn('documentos', final)

    def test_las_figuras_no_se_mezclan_con_los_documentos(self):
        """⚠️ Regresión real: la lista de documentos se pegaba en el mensaje como imagen.

        `artifacts` dejó de ser solo figuras, y `_embed_figures` recorría todas las claves:
        la persona veía `![Gráfico](data:image/png;base64,[{'id': 36, ...}])` en medio de
        su respuesta.
        """
        texto = agent_service._embed_figures(
            'Listo, quedó guardada.',
            {'documentos': [{'id': 36, 'titulo': 'Cotización', 'accion': 'creado'}]},
        )
        self.assertEqual(texto, 'Listo, quedó guardada.')
        self.assertNotIn('base64', texto)

    def test_una_figura_de_verdad_si_se_dibuja(self):
        texto = agent_service._embed_figures(
            'Mira el gráfico [[FIGURA_1]]',
            {'[[FIGURA_1]]': 'QUJD', 'documentos': [{'id': 1, 'titulo': 'x', 'accion': 'creado'}]},
        )
        self.assertIn('data:image/png;base64,QUJD', texto)
        self.assertNotIn("'id': 1", texto)


class LaCitaNoSeRepiteTests(TestCase):
    """La cita de un documento salía «Documento X·Documento X»: sin tablas, se usaba el
    propio nombre del sistema como si fuera una tabla. Está al pie de CADA respuesta."""

    def test_sin_tablas_la_fuente_se_nombra_una_vez(self):
        cita = agent_tools.build_citation([
            {'system': 'Documento «Cotización»', 'category': 'otro',
             'tables': None, 'rows': None, 'at': '16:39'},
        ])
        self.assertIn('Documento «Cotización»', cita)
        self.assertNotIn('Cotización»·Documento', cita)

    def test_con_tablas_se_siguen_nombrando(self):
        cita = agent_tools.build_citation([
            {'system': 'Odoo', 'category': 'erp', 'tables': ['sale.order'],
             'rows': 3, 'at': '16:40'},
        ])
        self.assertIn('ERP·Odoo·sale.order', cita)

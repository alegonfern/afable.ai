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
        from apps.workspaces.models import ROLE_ADMIN
        self.org.agregar_miembro(self.user, ROLE_ADMIN)

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
        from apps.workspaces.models import ROLE_ADMIN
        self.org.agregar_miembro(self.user, ROLE_ADMIN)
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
        from apps.workspaces.models import ROLE_ADMIN
        self.org.agregar_miembro(self.user, ROLE_ADMIN)
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

    def test_repetir_el_nombre_avisa_en_vez_de_reventar(self):
        """La base ya lo impedía, pero saltaba como IntegrityError: la persona veía un
        error del sistema donde correspondía "ya tiene una con ese nombre"."""
        client = APIClient()
        client.force_authenticate(user=self.user)
        datos = {'name': 'Tono formal', 'instructions': 'Trate de usted.'}

        self.assertEqual(client.post('/api/v1/agents/habilidades/', datos, format='json').status_code, 201)
        repetida = client.post('/api/v1/agents/habilidades/', datos, format='json')
        self.assertEqual(repetida.status_code, 400)
        self.assertIn('nombre', str(repetida.data).lower())

    def test_el_nombre_repetido_no_distingue_mayusculas(self):
        client = APIClient()
        client.force_authenticate(user=self.user)
        client.post('/api/v1/agents/habilidades/',
                    {'name': 'Tono formal', 'instructions': 'x'}, format='json')
        r = client.post('/api/v1/agents/habilidades/',
                        {'name': 'TONO FORMAL', 'instructions': 'x'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_una_habilidad_sin_instrucciones_se_rechaza(self):
        client = APIClient()
        client.force_authenticate(user=self.user)
        resp = client.post(
            '/api/v1/agents/habilidades/', {'name': 'Vacía', 'instructions': '   '}, format='json',
        )
        self.assertEqual(resp.status_code, 400)


class AlcanceDeEspacioTests(TestCase):
    """Lo que hace que crear un Espacio sirva para algo: recorta lo que ve el agente.

    Si estas pruebas se rompen, el Espacio vuelve a ser una carpeta de etiquetas y
    el agente de Ventas puede leer las carpetas de Personas sin que nadie se entere.
    """

    def setUp(self):
        from apps.organizations.models import CompanyDocument, SystemConnection
        from apps.workspaces.models import ROLE_ADMIN, Workspace
        from apps.workspaces.permissions import alcance_de_agente

        self.alcance = alcance_de_agente

        self.user = User.objects.create_user(
            username='duena@afable.test', email='duena@afable.test', password='afable123',
        )
        self.org = Organization.objects.create(owner=self.user, name='Cocinas SpA')
        from apps.workspaces.models import ROLE_ADMIN
        self.org.agregar_miembro(self.user, ROLE_ADMIN)
        self.workspace = Workspace.objects.create(organization=self.org, name='General')
        self.org.agregar_miembro(self.user, ROLE_ADMIN)

        self.odoo = SystemConnection.objects.create(
            organization=self.org, name='Odoo Ventas', connector_type='odoo',
        )
        self.sap = SystemConnection.objects.create(
            organization=self.org, name='SAP Personas', connector_type='mssql',
        )
        self.contrato = CompanyDocument.objects.create(
            organization=self.org, title='Contratos', file='x.pdf', extracted_text='confidencial',
        )
        self.catalogo = CompanyDocument.objects.create(
            organization=self.org, title='Catálogo', file='y.pdf', extracted_text='precios',
        )

        # El alcance documental sale de la CARPETA del agente; las conexiones, del Espacio.
        from apps.archivos.models import Carpeta
        self.carpeta_ventas = Carpeta.objects.create(organization=self.org, name='Ventas')
        self.catalogo.carpeta = self.carpeta_ventas
        self.catalogo.save(update_fields=['carpeta'])

        self.ventas = Agent.objects.create(
            organization=self.org, name='Ventas', carpeta=self.carpeta_ventas,
        )
        self.espacio_ventas = Workspace.objects.create(organization=self.org, name='Ventas')
        self.espacio_ventas.connections.add(self.odoo)
        self.espacio_ventas.agents.add(self.ventas)

    def test_un_agente_sin_espacio_no_queda_restringido(self):
        """Compatibilidad: un agente sin carpeta ni Espacio sigue viendo todo lo suyo."""
        suelto = Agent.objects.create(organization=self.org, name='Suelto')
        self.assertEqual(self.alcance(suelto), (None, None))

    def test_un_agente_en_un_espacio_solo_alcanza_sus_fuentes(self):
        conns, docs = self.alcance(self.ventas)
        self.assertEqual(conns, [self.odoo.id])
        self.assertEqual(docs, [self.catalogo.id])

    def test_lo_que_esta_fuera_del_espacio_no_entra(self):
        conns, docs = self.alcance(self.ventas)
        self.assertNotIn(self.sap.id, conns)
        self.assertNotIn(self.contrato.id, docs)

    def test_el_alcance_es_la_union_de_varios_espacios(self):
        from apps.workspaces.models import Workspace

        otro = Workspace.objects.create(organization=self.org, name='Personas')
        otro.connections.add(self.sap)
        otro.agents.add(self.ventas)

        conns, _ = self.alcance(self.ventas)
        self.assertCountEqual(conns, [self.odoo.id, self.sap.id])

    def test_un_espacio_vacio_deja_al_agente_sin_conexiones(self):
        """El silencio es la respuesta correcta: no se cae de vuelta a toda la empresa.

        Ojo con la segunda mitad: el agente está en un Espacio pero NO tiene carpeta, así
        que su alcance documental es `None` —sin restricción— y no `[]`. No es un descuido:
        desde el 31-08 los documentos los decide la carpeta, y este agente no eligió
        ninguna. Restringirlo por un Espacio vacío lo dejaría mudo sin que nadie lo haya
        pedido, que es justo lo que la compatibilidad evita.
        """
        from apps.workspaces.models import Workspace

        pelado = Workspace.objects.create(organization=self.org, name='Recién creado')
        nuevo = Agent.objects.create(organization=self.org, name='Nuevo')
        pelado.agents.add(nuevo)

        conns, docs = self.alcance(nuevo)
        self.assertEqual(conns, [])
        self.assertIsNone(docs)

    def test_una_carpeta_vacia_deja_al_agente_sin_documentos(self):
        """Acá sí manda el silencio: la carpeta fue elegida, y está vacía."""
        from apps.archivos.models import Carpeta

        vacia = Carpeta.objects.create(organization=self.org, name='Recién creada')
        nuevo = Agent.objects.create(organization=self.org, name='Nuevo', carpeta=vacia)

        _, docs = self.alcance(nuevo)
        self.assertEqual(docs, [])

    def test_el_agente_alcanza_las_subcarpetas(self):
        """Quien pregunta por Contabilidad espera que mire adentro de Contabilidad/Facturas."""
        from apps.archivos.models import Carpeta
        from apps.organizations.models import CompanyDocument

        madre = Carpeta.objects.create(organization=self.org, name='Contabilidad')
        hija = Carpeta.objects.create(organization=self.org, name='Facturas', parent=madre)
        nieta = Carpeta.objects.create(organization=self.org, name='2026', parent=hija)

        doc_hija = CompanyDocument.objects.create(
            organization=self.org, title='Factura 1', file='f1.pdf', carpeta=hija,
        )
        doc_nieta = CompanyDocument.objects.create(
            organization=self.org, title='Factura 2', file='f2.pdf', carpeta=nieta,
        )
        agente = Agent.objects.create(organization=self.org, name='Conta', carpeta=madre)

        _, docs = self.alcance(agente)
        self.assertCountEqual(docs, [doc_hija.id, doc_nieta.id])
        # Y lo que está fuera de la rama no entra.
        self.assertNotIn(self.contrato.id, docs)

    def test_el_prompt_no_nombra_los_documentos_de_otro_espacio(self):
        from apps.agents.views import _build_onboarding_context

        contexto = _build_onboarding_context(self.user, self.ventas)
        prompt = contexto['system_prompt']
        self.assertIn('Catálogo', prompt)
        self.assertNotIn('Contratos', prompt)

    def test_el_prompt_no_nombra_los_sistemas_de_otro_espacio(self):
        from apps.agents.views import _build_onboarding_context

        contexto = _build_onboarding_context(self.user, self.ventas)
        self.assertIn('Odoo Ventas', contexto['system_prompt'])
        self.assertNotIn('SAP Personas', contexto['system_prompt'])

    def test_el_alcance_del_espacio_viaja_a_las_herramientas(self):
        from apps.agents.views import _build_onboarding_context

        contexto = _build_onboarding_context(self.user, self.ventas)
        self.assertEqual(contexto['allowed_ids'], [self.odoo.id])
        self.assertEqual(contexto['allowed_doc_ids'], [self.catalogo.id])

    def test_las_herramientas_no_leen_un_documento_de_otro_espacio(self):
        from services.agent_tools import execute_tool

        prov = []
        fuera = execute_tool(
            'read_company_document', {'id': self.contrato.id}, self.org, prov,
            allowed_ids=[self.odoo.id], allowed_doc_ids=[self.catalogo.id],
        )
        self.assertIn('error', fuera)

        dentro = execute_tool(
            'read_company_document', {'id': self.catalogo.id}, self.org, prov,
            allowed_ids=[self.odoo.id], allowed_doc_ids=[self.catalogo.id],
        )
        self.assertNotIn('error', dentro)

    def test_el_sistema_elegido_a_mano_no_saca_al_agente_de_su_espacio(self):
        """Intersecta, no reemplaza: `agent.systems` no puede ampliar el Espacio."""
        from apps.agents.views import _build_onboarding_context

        self.ventas.systems.add(self.sap)
        contexto = _build_onboarding_context(self.user, self.ventas)
        self.assertNotIn(self.sap.id, contexto['allowed_ids'] or [])


class EspacioEnElChatTests(TestCase):
    """Trabajar EN un Espacio: qué agentes se ofrecen y dónde queda la conversación."""

    def setUp(self):
        from apps.workspaces.models import ROLE_ADMIN, ROLE_MEMBER, Workspace, Workspace

        self.Workspace = Workspace

        self.duena = User.objects.create_user(
            username='duena@afable.test', email='duena@afable.test', password='afable123',
        )
        self.companero = User.objects.create_user(
            username='companero@afable.test', email='companero@afable.test', password='afable123',
        )
        self.ajeno = User.objects.create_user(
            username='ajeno@afable.test', email='ajeno@afable.test', password='afable123',
        )

        self.org = Organization.objects.create(owner=self.duena, name='Cocinas SpA')
        self.workspace = Workspace.objects.create(organization=self.org, name='General')
        self.org.agregar_miembro(self.duena, ROLE_ADMIN)
        self.org.agregar_miembro(self.companero, ROLE_MEMBER)
        self.org.agregar_miembro(self.ajeno, ROLE_MEMBER)

        self.ventas = Agent.objects.create(organization=self.org, name='Ventas')
        self.personas = Agent.objects.create(organization=self.org, name='Personas')

        self.espacio = Workspace.objects.create(organization=self.org, name='Ventas')
        self.espacio.agents.add(self.ventas)
        self.espacio.members.add(self.duena, self.companero)

    def _cliente(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def test_la_galeria_filtrada_solo_trae_los_agentes_del_espacio(self):
        resp = self._cliente(self.duena).get(
            '/api/v1/agents/gallery/',
            {'workspace': self.org.slug, 'espacio': self.espacio.slug},
        )
        self.assertEqual(resp.status_code, 200)
        nombres = [a['name'] for a in resp.json()['results']]
        self.assertEqual(nombres, ['Ventas'])

    def test_sin_espacio_la_galeria_trae_todos(self):
        resp = self._cliente(self.duena).get(
            '/api/v1/agents/gallery/', {'workspace': self.org.slug},
        )
        nombres = {a['name'] for a in resp.json()['results']}
        self.assertEqual(nombres, {'Ventas', 'Personas'})

    def test_pedir_los_agentes_de_un_espacio_restringido_ajeno_es_404(self):
        self.espacio.visibility = 'restringido'
        self.espacio.save()
        resp = self._cliente(self.ajeno).get(
            '/api/v1/agents/gallery/',
            {'workspace': self.org.slug, 'espacio': self.espacio.slug},
        )
        self.assertEqual(resp.status_code, 404)

    def test_la_conversacion_del_espacio_la_ve_un_companero(self):
        from apps.agents.models import Conversation

        conv = Conversation.objects.create(
            agent=self.ventas, user=self.duena, workspace=self.espacio, title='Cierre de mes',
        )
        resp = self._cliente(self.companero).get(
            f'/api/v1/workspaces/{self.org.slug}/espacios/{self.espacio.slug}/conversaciones/'
        )
        self.assertEqual(resp.status_code, 200)
        cuerpo = resp.json()
        self.assertEqual([c['id'] for c in cuerpo], [conv.id])
        # Y sabe que no es suya: el hilo es del equipo, pero se ve de quién salió.
        self.assertFalse(cuerpo[0]['es_mia'])
        self.assertEqual(cuerpo[0]['agent_handle'], 'ventas')

    def test_una_conversacion_personal_no_aparece_en_el_espacio(self):
        from apps.agents.models import Conversation

        Conversation.objects.create(agent=self.ventas, user=self.duena, title='Mía y de nadie más')
        resp = self._cliente(self.companero).get(
            f'/api/v1/workspaces/{self.org.slug}/espacios/{self.espacio.slug}/conversaciones/'
        )
        self.assertEqual(resp.json(), [])

    def test_quien_no_entra_al_espacio_restringido_no_ve_sus_conversaciones(self):
        from apps.agents.models import Conversation

        self.espacio.visibility = 'restringido'
        self.espacio.save()
        Conversation.objects.create(
            agent=self.ventas, user=self.duena, workspace=self.espacio, title='Confidencial',
        )
        resp = self._cliente(self.ajeno).get(
            f'/api/v1/workspaces/{self.org.slug}/espacios/{self.espacio.slug}/conversaciones/'
        )
        self.assertEqual(resp.status_code, 404)

    def test_el_espacio_que_manda_el_chat_queda_en_la_conversacion(self):
        from apps.agents.views import _espacio_del_pedido

        class PedidoFalso:
            def __init__(self, user, data):
                self.user = user
                self.data = data

        pedido = PedidoFalso(
            self.duena, {'workspace': self.org.slug, 'space': self.espacio.slug},
        )
        self.assertEqual(_espacio_del_pedido(pedido), self.espacio)

    def test_mandar_el_slug_de_un_espacio_ajeno_deja_la_conversacion_personal(self):
        """No se cae con error: el resultado seguro es un hilo personal."""
        from apps.agents.views import _espacio_del_pedido

        class PedidoFalso:
            def __init__(self, user, data):
                self.user = user
                self.data = data

        self.espacio.visibility = 'restringido'
        self.espacio.save()
        pedido = PedidoFalso(
            self.ajeno, {'workspace': self.org.slug, 'space': self.espacio.slug},
        )
        self.assertIsNone(_espacio_del_pedido(pedido))

    def test_con_espacio_activo_contesta_un_agente_del_espacio(self):
        """Si no, "trabajo en Finanzas" lo responde un agente que ve toda la empresa."""
        from apps.agents.views import _agente_inicial

        class PedidoFalso:
            def __init__(self, user, data):
                self.user = user
                self.data = data

        suelto = Agent.objects.create(organization=self.org, name='Por omisión')
        pedido = PedidoFalso(self.duena, {})
        elegido = _agente_inicial(pedido, 'hola', self.espacio, suelto)
        self.assertEqual(elegido, self.ventas)

    def test_la_mencion_le_gana_al_agente_del_espacio(self):
        from apps.agents.views import _agente_inicial

        class PedidoFalso:
            def __init__(self, user, data):
                self.user = user
                self.data = data

        suelto = Agent.objects.create(organization=self.org, name='Por omisión')
        pedido = PedidoFalso(self.duena, {})
        elegido = _agente_inicial(pedido, '@personas quién entró este mes', self.espacio, suelto)
        self.assertEqual(elegido, self.personas)

    def test_sin_espacio_sigue_contestando_el_de_siempre(self):
        from apps.agents.views import _agente_inicial

        class PedidoFalso:
            def __init__(self, user, data):
                self.user = user
                self.data = data

        suelto = Agent.objects.create(organization=self.org, name='Por omisión')
        pedido = PedidoFalso(self.duena, {})
        self.assertEqual(_agente_inicial(pedido, 'hola', None, suelto), suelto)

    def test_un_espacio_sin_agentes_cae_al_de_siempre(self):
        from apps.agents.views import _agente_inicial

        class PedidoFalso:
            def __init__(self, user, data):
                self.user = user
                self.data = data

        pelado = self.Workspace.objects.create(organization=self.org, name='Vacío')
        suelto = Agent.objects.create(organization=self.org, name='Por omisión')
        pedido = PedidoFalso(self.duena, {})
        self.assertEqual(_agente_inicial(pedido, 'hola', pelado, suelto), suelto)


class CitaDeDocumentosTests(TestCase):
    """Citar el documento que sustenta la respuesta.

    El agente contesta con el contenido que ya venía en el prompt, sin llamar
    herramientas, así que no hay `provenance` y la respuesta salía sin fuente.
    """

    def setUp(self):
        from apps.agents.views import citar_documentos_del_prompt

        self.citar = citar_documentos_del_prompt
        self.docs = [
            {'id': 1, 'title': 'Política de vacaciones'},
            {'id': 2, 'title': 'Catálogo 2026'},
        ]

    def test_cita_el_documento_que_la_respuesta_nombra(self):
        texto = 'Según la Política de vacaciones, son 15 días hábiles.'
        self.assertIn('_[Fuente: Política de vacaciones]_', self.citar(texto, self.docs))

    def test_no_cita_lo_que_la_respuesta_no_nombra(self):
        texto = 'Según la Política de vacaciones, son 15 días hábiles.'
        self.assertNotIn('Catálogo 2026', self.citar(texto, self.docs))

    def test_cita_varios_sin_repetir(self):
        texto = 'La Política de vacaciones y el Catálogo 2026. Insisto: Catálogo 2026.'
        salida = self.citar(texto, self.docs)
        self.assertIn('_[Fuente: Política de vacaciones, Catálogo 2026]_', salida)
        # En la línea de fuente aparece una sola vez, aunque el texto lo repita.
        linea = salida.split('_[Fuente: ')[1]
        self.assertEqual(linea.count('Catálogo 2026'), 1)

    def test_no_pisa_una_cita_que_ya_existe(self):
        """Si las herramientas ya citaron, no se duplica la línea."""
        texto = 'Ahí va.\n\n_[Fuente: Odoo·sale_order · consultado 10:00]_'
        self.assertEqual(self.citar(texto, self.docs), texto)

    def test_sin_documentos_no_agrega_nada(self):
        texto = 'Una respuesta cualquiera.'
        self.assertEqual(self.citar(texto, []), texto)
        self.assertEqual(self.citar(texto, None), texto)

    def test_no_inventa_una_fuente_cuando_no_hay_coincidencia(self):
        """Una fuente que el agente no usó es peor que ninguna."""
        texto = 'No tengo ese dato.'
        self.assertEqual(self.citar(texto, self.docs), texto)


class RamificarYEditarTests(TestCase):
    """Ramificar un hilo desde un mensaje, y corregir la propia pregunta."""

    def setUp(self):
        from apps.agents.models import Conversation, Message

        self.Conversation = Conversation
        self.Message = Message

        self.duena = User.objects.create_user(
            username='duena@afable.test', email='duena@afable.test', password='afable123',
        )
        self.ajena = User.objects.create_user(
            username='ajena@afable.test', email='ajena@afable.test', password='afable123',
        )
        self.org = Organization.objects.create(owner=self.duena, name='Cocinas SpA')
        self.agente = Agent.objects.create(organization=self.org, name='Ventas')

        self.conv = Conversation.objects.create(
            agent=self.agente, user=self.duena, title='Cierre de mes',
        )
        self.m1 = Message.objects.create(conversation=self.conv, role='user', content='¿Cómo vamos?')
        self.m2 = Message.objects.create(
            conversation=self.conv, role='assistant', content='Vamos bien.', agent=self.agente,
        )
        self.m3 = Message.objects.create(conversation=self.conv, role='user', content='¿Y el margen?')

        self.client_duena = APIClient()
        self.client_duena.force_authenticate(user=self.duena)

    def test_ramificar_copia_el_hilo_hasta_ese_mensaje(self):
        resp = self.client_duena.post(
            f'/api/v1/agents/conversations/{self.conv.id}/ramificar/',
            {'message_id': self.m2.id}, format='json',
        )
        self.assertEqual(resp.status_code, 201)
        rama = self.Conversation.objects.get(pk=resp.json()['id'])
        self.assertEqual(
            [m.content for m in rama.messages.order_by('id')],
            ['¿Cómo vamos?', 'Vamos bien.'],
        )

    def test_ramificar_no_toca_la_conversacion_original(self):
        self.client_duena.post(
            f'/api/v1/agents/conversations/{self.conv.id}/ramificar/',
            {'message_id': self.m2.id}, format='json',
        )
        self.assertEqual(self.conv.messages.count(), 3)

    def test_la_rama_conserva_el_espacio_de_la_original(self):
        from apps.workspaces.models import ROLE_ADMIN, Workspace

        workspace = Workspace.objects.create(organization=self.org, name='General')
        self.org.agregar_miembro(self.duena, ROLE_ADMIN)
        espacio = Workspace.objects.create(organization=workspace.organization, name='Ventas')
        self.conv.workspace = espacio
        self.conv.save()

        resp = self.client_duena.post(
            f'/api/v1/agents/conversations/{self.conv.id}/ramificar/', {}, format='json',
        )
        rama = self.Conversation.objects.get(pk=resp.json()['id'])
        self.assertEqual(rama.workspace, espacio)

    def test_no_se_puede_ramificar_una_conversacion_ajena(self):
        client = APIClient()
        client.force_authenticate(user=self.ajena)
        resp = client.post(
            f'/api/v1/agents/conversations/{self.conv.id}/ramificar/', {}, format='json',
        )
        self.assertEqual(resp.status_code, 404)

    def test_corregir_corta_el_hilo_desde_ese_mensaje(self):
        """Se borra la pregunta vieja y todo lo posterior; el cliente reenvía.

        Si el mensaje editado sobreviviera, quedaría la pregunta corregida guardada
        Y la reenviada: la misma pregunta dos veces seguidas en el historial.
        """
        resp = self.client_duena.patch(
            f'/api/v1/agents/conversations/{self.conv.id}/messages/{self.m1.id}/',
            {'content': '¿Cómo vamos con el margen?'}, format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['borrados'], 3)
        self.assertEqual(resp.json()['contenido'], '¿Cómo vamos con el margen?')
        self.assertEqual(self.conv.messages.count(), 0)

    def test_no_se_puede_editar_la_respuesta_del_agente(self):
        resp = self.client_duena.patch(
            f'/api/v1/agents/conversations/{self.conv.id}/messages/{self.m2.id}/',
            {'content': 'Vamos pésimo.'}, format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.m2.refresh_from_db()
        self.assertEqual(self.m2.content, 'Vamos bien.')
        self.assertEqual(self.conv.messages.count(), 3)

    def test_un_mensaje_no_puede_quedar_vacio(self):
        resp = self.client_duena.patch(
            f'/api/v1/agents/conversations/{self.conv.id}/messages/{self.m1.id}/',
            {'content': '   '}, format='json',
        )
        self.assertEqual(resp.status_code, 400)


class DisparadoresTests(TestCase):
    """Los disparadores nuevos: a una hora fija y cuando avisa otro sistema."""

    def setUp(self):
        from apps.agents.models import Automation

        self.Automation = Automation
        self.user = User.objects.create_user(
            username='duena@afable.test', email='duena@afable.test', password='afable123',
        )
        self.org = Organization.objects.create(owner=self.user, name='Cocinas SpA')
        from apps.workspaces.models import ROLE_ADMIN
        self.org.agregar_miembro(self.user, ROLE_ADMIN)

    def _horario(self, **config):
        return self.Automation.objects.create(
            user=self.user, organization=self.org, name='Reporte',
            prompt='Resumen de ventas', notify_email='a@b.cl',
            trigger_type='schedule', schedule_config=config,
        )

    def test_los_lunes_a_las_ocho_no_corre_un_martes(self):
        from datetime import datetime

        from django.utils import timezone as tz

        auto = self._horario(dias=[0], hora=8, minuto=0)
        martes = tz.make_aware(datetime(2026, 8, 4, 8, 5))
        self.assertFalse(auto.is_due(martes))

    def test_los_lunes_a_las_ocho_corre_el_lunes(self):
        from datetime import datetime

        from django.utils import timezone as tz

        auto = self._horario(dias=[0], hora=8, minuto=0)
        lunes = tz.make_aware(datetime(2026, 8, 3, 8, 5))
        self.assertTrue(auto.is_due(lunes))

    def test_todavia_no_es_la_hora(self):
        from datetime import datetime

        from django.utils import timezone as tz

        auto = self._horario(dias=[0], hora=8, minuto=0)
        lunes_temprano = tz.make_aware(datetime(2026, 8, 3, 7, 30))
        self.assertFalse(auto.is_due(lunes_temprano))

    def test_la_ventana_se_cierra_pasada_la_hora(self):
        """Sin tope, una automatización de las 8 correría a las 23."""
        from datetime import datetime

        from django.utils import timezone as tz

        auto = self._horario(dias=[0], hora=8, minuto=0)
        lunes_tarde = tz.make_aware(datetime(2026, 8, 3, 23, 0))
        self.assertFalse(auto.is_due(lunes_tarde))

    def test_no_corre_dos_veces_el_mismo_dia(self):
        from datetime import datetime

        from django.utils import timezone as tz

        auto = self._horario(dias=[0], hora=8, minuto=0)
        lunes = tz.make_aware(datetime(2026, 8, 3, 8, 5))
        auto.last_run_at = lunes
        auto.save()
        self.assertFalse(auto.is_due(tz.make_aware(datetime(2026, 8, 3, 8, 40))))

    def test_sin_dias_corre_todos_los_dias(self):
        from datetime import datetime

        from django.utils import timezone as tz

        auto = self._horario(hora=8, minuto=0)
        for dia in (3, 4, 5):  # lunes, martes, miércoles de esa semana
            self.assertTrue(auto.is_due(tz.make_aware(datetime(2026, 8, dia, 8, 10))))

    def test_el_horario_se_explica_en_castellano(self):
        auto = self._horario(dias=[0, 4], hora=8, minuto=30)
        self.assertEqual(auto.descripcion_del_disparador(), 'Lunes, Viernes a las 08:30')

    def test_el_webhook_nace_con_token_y_nunca_le_toca_por_reloj(self):
        from datetime import datetime

        from django.utils import timezone as tz

        auto = self.Automation.objects.create(
            user=self.user, organization=self.org, name='Aviso',
            prompt='Resume el aviso', notify_email='a@b.cl', trigger_type='webhook',
        )
        self.assertTrue(auto.webhook_token)
        self.assertFalse(auto.is_due(tz.make_aware(datetime(2026, 8, 3, 8, 5))))

    def test_el_token_no_se_regenera_al_guardar(self):
        auto = self.Automation.objects.create(
            user=self.user, organization=self.org, name='Aviso',
            prompt='x', notify_email='a@b.cl', trigger_type='webhook',
        )
        token = auto.webhook_token
        auto.name = 'Aviso renombrado'
        auto.save()
        auto.refresh_from_db()
        self.assertEqual(auto.webhook_token, token)

    def test_un_token_inventado_es_404(self):
        client = APIClient()
        resp = client.post('/api/v1/agents/webhooks/no-existe/', {'a': 1}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_una_automatizacion_apagada_responde_igual_que_una_inexistente(self):
        """Quien prueba tokens al azar no puede aprender nada de la respuesta."""
        client = APIClient()
        auto = self.Automation.objects.create(
            user=self.user, organization=self.org, name='Aviso',
            prompt='x', notify_email='a@b.cl', trigger_type='webhook', is_active=False,
        )
        resp = client.post(f'/api/v1/agents/webhooks/{auto.webhook_token}/', {'a': 1}, format='json')
        self.assertEqual(resp.status_code, 404)


class CacheDePromptTests(TestCase):
    """Que la caché de prompts no se rompa sin que nadie se dé cuenta.

    La caché es coincidencia de PREFIJO: descuenta el 90% de lo que se repite, pero
    solo si el comienzo del prompt es idéntico byte a byte. Todo lo que cambie por
    persona tiene que ir DESPUÉS del corte. Si alguien vuelve a meter el nombre del
    usuario arriba, la caché sigue "funcionando" y el descuento desaparece sin un solo
    error en los registros. Estas pruebas son la alarma de eso.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='marta@afable.test', email='marta@afable.test', password='afable123',
            first_name='Marta',
        )
        self.user.role = 'Gerenta de Finanzas'
        self.user.save(update_fields=['role'])
        self.org = Organization.objects.create(owner=self.user, name='Cocinas SpA')
        from apps.workspaces.models import ROLE_ADMIN
        self.org.agregar_miembro(self.user, ROLE_ADMIN)

    def test_el_nombre_de_la_persona_no_va_en_el_prompt_compartido(self):
        from apps.agents.views import _build_onboarding_context

        ctx = _build_onboarding_context(self.user, None, consulta='¿cuánto vendimos?')
        self.assertNotIn('Marta', ctx['system_prompt'])
        self.assertNotIn('Gerenta de Finanzas', ctx['system_prompt'])
        self.assertIn('Marta', ctx['system_persona'])

    def test_dos_personas_de_la_misma_empresa_comparten_el_prompt(self):
        """Es el punto entero: con el prefijo compartido hay UNA entrada de caché para
        la empresa, no una por persona."""
        from apps.agents.views import _build_onboarding_context

        otro = User.objects.create_user(
            username='pedro@afable.test', email='pedro@afable.test', password='afable123',
            first_name='Pedro',
        )
        otro.role = 'Jefe de Bodega'
        otro.save(update_fields=['role'])
        self.org.agregar_miembro(otro, 'member')

        uno = _build_onboarding_context(self.user, None, consulta='x')
        dos = _build_onboarding_context(otro, None, consulta='x')
        self.assertEqual(uno['system_prompt'], dos['system_prompt'])
        self.assertNotEqual(uno['system_persona'], dos['system_persona'])

    def test_el_bloque_de_herramientas_pide_cache(self):
        from services.agent_service import _tools_cacheadas

        tools = [{'name': 'a'}, {'name': 'b'}, {'name': 'c'}]
        marcadas = _tools_cacheadas(tools)
        # El corte va en la ÚLTIMA: marca el final del bloque, y con eso se cachea todo
        # lo anterior. Marcar una del medio dejaría el resto fuera.
        self.assertNotIn('cache_control', marcadas[0])
        self.assertEqual(marcadas[-1]['cache_control'], {'type': 'ephemeral', 'ttl': '1h'})
        self.assertEqual(len(marcadas), 3)
        self.assertEqual(tools[-1], {'name': 'c'})  # no muta la lista original

    def test_sin_herramientas_no_revienta(self):
        from services.agent_service import _tools_cacheadas
        self.assertEqual(_tools_cacheadas([]), [])

    def test_el_sistema_va_en_dos_bloques_y_solo_el_estable_se_cachea(self):
        from services.agent_service import _sistema_anthropic

        bloques = _sistema_anthropic('lo compartido', 'Marta, Gerenta de Finanzas.')
        self.assertEqual(len(bloques), 2)
        self.assertEqual(bloques[0]['cache_control'], {'type': 'ephemeral', 'ttl': '1h'})
        self.assertNotIn('cache_control', bloques[1])
        self.assertEqual(bloques[1]['text'], 'Marta, Gerenta de Finanzas.')

    def test_sin_parte_de_persona_va_un_solo_bloque(self):
        from services.agent_service import _sistema_anthropic

        self.assertEqual(len(_sistema_anthropic('lo compartido', '')), 1)
        self.assertEqual(len(_sistema_anthropic('lo compartido', '   ')), 1)

    def test_las_herramientas_de_archivos_no_estan_descritas_dos_veces(self):
        """Estaban en el esquema Y escritas a mano en el prompt de sistema: el modelo
        leía las mismas instrucciones dos veces y se pagaban dos veces por llamada."""
        from apps.agents.views import _build_onboarding_context

        ctx = _build_onboarding_context(self.user, None, consulta='x')
        self.assertNotIn('HERRAMIENTAS DE ARCHIVOS', ctx['system_prompt'])


class BuscarConversacionesTests(TestCase):
    """La búsqueda de conversaciones: que encuentre lo que se puede abrir, y NADA más.

    Lo que se protege acá es la propiedad que el producto promete sobre permisos. Un
    buscador es la forma más cómoda de filtrar información sin que se note: alcanza con
    que devuelva un título de más. Por eso busca sobre el mismo embudo que decide quién
    entra a un hilo (`hilos_alcanzables`), y no sobre una consulta propia.
    """

    def setUp(self):
        from apps.sesiones.models import Sesion, SesionMiembro, VISIBILIDAD_RESTRINGIDA
        from apps.workspaces.models import ROLE_ADMIN, ROLE_MEMBER, Workspace

        self.duena = User.objects.create_user(
            username='duena@afable.test', email='duena@afable.test', password='afable123',
            first_name='Marta',
        )
        self.companero = User.objects.create_user(
            username='companero@afable.test', email='companero@afable.test',
            password='afable123', first_name='Pedro',
        )
        self.ajeno = User.objects.create_user(
            username='ajeno@afable.test', email='ajeno@afable.test', password='afable123',
        )
        self.org = Organization.objects.create(owner=self.duena, name='Cocinas SpA')
        ws = Workspace.objects.create(organization=self.org, name='General')
        self.org.agregar_miembro(self.duena, ROLE_ADMIN)
        self.org.agregar_miembro(self.companero, ROLE_MEMBER)
        self.org.agregar_miembro(self.ajeno, ROLE_MEMBER)
        self.agente = Agent.objects.create(organization=self.org, name='Ventas')

        # Una Sesión RESTRINGIDA donde entran Marta y Pedro, y el ajeno no.
        self.sesion = Sesion.objects.create(
            workspace=ws, name='Cierre de mes', slug='cierre-de-mes',
            visibility=VISIBILIDAD_RESTRINGIDA,
        )
        SesionMiembro.objects.create(sesion=self.sesion, user=self.duena)
        SesionMiembro.objects.create(sesion=self.sesion, user=self.companero)

        self.mio = self._hilo(self.duena, 'Precios de gabinetes',
                              'cuanto cuesta el gabinete de melamina', sesion=None)
        self.compartido = self._hilo(self.companero, 'Facturas pendientes',
                                     'revisar la melamina que quedo sin facturar',
                                     sesion=self.sesion)
        # De otra persona y sin Sesión: nadie más que su autor lo alcanza.
        self.privado_ajeno = self._hilo(self.ajeno, 'Notas privadas',
                                        'la melamina de mi casa', sesion=None)

    def _hilo(self, user, titulo, texto, sesion=None):
        from apps.agents.models import Conversation, Message

        conv = Conversation.objects.create(
            agent=self.agente, user=user, title=titulo, sesion=sesion,
        )
        Message.objects.create(conversation=conv, role='user', content=texto, user=user)
        return conv

    def _buscar(self, user, **params):
        client = APIClient()
        client.force_authenticate(user=user)
        return client.get('/api/v1/agents/conversations/', params)

    # ── Lo que tiene que encontrar ────────────────────────────────────

    def test_busca_en_el_contenido_y_no_solo_en_el_titulo(self):
        """Los títulos se arman con los primeros 120 caracteres del primer mensaje, así
        que lo que uno recuerda de una conversación casi nunca está en el título."""
        r = self._buscar(self.duena, q='melamina')
        ids = [c['id'] for c in r.data]
        self.assertIn(self.mio.id, ids)          # calza por contenido, no por titulo
        r2 = self._buscar(self.duena, q='gabinetes')
        self.assertIn(self.mio.id, [c['id'] for c in r2.data])   # y por titulo tambien

    def test_encuentra_el_hilo_que_el_equipo_compartio_en_su_sesion(self):
        r = self._buscar(self.duena, q='melamina', compartidos=1)
        ids = [c['id'] for c in r.data]
        self.assertIn(self.compartido.id, ids)

    def test_el_hilo_ajeno_viene_marcado_y_dice_quien_lo_escribio(self):
        """Una lista que mezcla lo propio con lo ajeno sin decirlo se lee como si todo
        fuera propio."""
        r = self._buscar(self.duena, q='melamina', compartidos=1)
        fila = next(c for c in r.data if c['id'] == self.compartido.id)
        self.assertTrue(fila['compartido_conmigo'])
        self.assertEqual(fila['autor_nombre'], 'Pedro')
        self.assertEqual(fila['sesion_nombre'], 'Cierre de mes')

    def test_el_hilo_propio_no_viene_marcado(self):
        r = self._buscar(self.duena, q='melamina', compartidos=1)
        fila = next(c for c in r.data if c['id'] == self.mio.id)
        self.assertFalse(fila['compartido_conmigo'])

    # ── Lo que NO tiene que encontrar (es el punto) ───────────────────

    def test_no_encuentra_el_hilo_privado_de_otra_persona(self):
        r = self._buscar(self.duena, q='melamina', compartidos=1)
        self.assertNotIn(self.privado_ajeno.id, [c['id'] for c in r.data])

    def test_quien_no_alcanza_la_sesion_no_encuentra_su_hilo(self):
        """El ajeno es miembro de la empresa, pero la Sesión es restringida y no está
        invitado. Si el buscador se lo mostrara, sería la puerta de atrás."""
        r = self._buscar(self.ajeno, q='melamina', compartidos=1)
        ids = [c['id'] for c in r.data]
        self.assertNotIn(self.compartido.id, ids)
        self.assertNotIn(self.mio.id, ids)
        self.assertIn(self.privado_ajeno.id, ids)   # el suyo si

    def test_sin_el_parametro_la_barra_sigue_mostrando_solo_lo_propio(self):
        """La barra lateral es el historial de cada uno y no cambia: lo compartido se
        pide explícitamente, y solo lo pide el buscador."""
        r = self._buscar(self.duena, q='melamina')
        ids = [c['id'] for c in r.data]
        self.assertIn(self.mio.id, ids)
        self.assertNotIn(self.compartido.id, ids)

    # ── El límite ─────────────────────────────────────────────────────

    def test_el_limite_lo_aplica_el_servidor(self):
        """Antes se pedían TODAS las conversaciones para mostrar diez en la barra."""
        for i in range(5):
            self._hilo(self.duena, f'Hilo {i}', 'melamina otra vez')
        self.assertEqual(len(self._buscar(self.duena, q='melamina', limite=2).data), 2)
        self.assertGreater(len(self._buscar(self.duena, q='melamina').data), 2)

    def test_un_limite_invalido_no_revienta(self):
        r = self._buscar(self.duena, limite='hola')
        self.assertEqual(r.status_code, 200)

    def test_sin_texto_devuelve_el_historial(self):
        r = self._buscar(self.duena)
        self.assertIn(self.mio.id, [c['id'] for c in r.data])

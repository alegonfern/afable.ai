"""El agente que nace propuesto.

Dos cosas se prueban acá por encima del resto. Que **no se proponga nada sobre una carpeta
vacía** —un agente que contesta que no sabe nada es la primera impresión que hace que
alguien no vuelva— y que **el fallo del proveedor de IA no deje al producto sin agentes**:
si el modelo se cae, la propuesta sale igual, peor redactada, y la persona puede seguir.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.agents.models import Agent
from apps.archivos.models import Carpeta
from apps.organizations.models import CompanyDocument, Organization
from apps.workspaces.models import ROLE_ADMIN, ROLE_MEMBER, Membership
from services.estructura_inicial import carpeta_personal, crear_estructura
from services.propuestas_de_agente import (
    UMBRAL_DOCUMENTOS,
    carpetas_con_material,
    crear_desde_propuesta,
    redactar,
)

User = get_user_model()

RESPUESTA_DEL_MODELO = (
    '{"nombre": "Facturación", '
    '"descripcion": "Responde sobre las facturas emitidas y sus vencimientos.", '
    '"instrucciones": "Revisas las facturas de la carpeta y avisas cuáles vencen.", '
    '"icono": "🧾"}'
)


class ProponerAgenteTests(TestCase):
    def setUp(self):
        self.duena = User.objects.create_user(
            username='duena@afable.test', email='duena@afable.test', password='x',
        )
        self.empleado = User.objects.create_user(
            username='empleado@afable.test', email='empleado@afable.test', password='x',
        )
        self.org = Organization.objects.create(owner=self.duena, name='Cocinas SpA')
        self.org.agregar_miembro(self.duena, ROLE_ADMIN)
        self.org.agregar_miembro(self.empleado, ROLE_MEMBER)
        self.m_duena = Membership.objects.get(organization=self.org, user=self.duena)
        self.m_empleado = Membership.objects.get(organization=self.org, user=self.empleado)

        crear_estructura(self.org, 'general', self.duena)
        # Una carpeta con nombre vago a propósito: es el caso que el diseño resuelve.
        self.cosas = Carpeta.objects.get(organization=self.org, name='Facturación')

    def _llenar(self, carpeta, cuantos):
        for i in range(cuantos):
            CompanyDocument.objects.create(
                organization=self.org, title=f'Factura {i + 1}', file=f'f{i}.pdf',
                carpeta=carpeta,
            )

    # ── a quién se le propone ────────────────────────────────────────────────

    def test_no_se_propone_nada_sobre_una_carpeta_vacia(self):
        """Un agente que contesta que no sabe nada es la razón por la que alguien no vuelve."""
        self.assertEqual(carpetas_con_material(self.org, self.duena, self.m_duena), [])

    def test_hace_falta_pasar_el_umbral(self):
        self._llenar(self.cosas, UMBRAL_DOCUMENTOS - 1)
        self.assertEqual(carpetas_con_material(self.org, self.duena, self.m_duena), [])

        self._llenar(self.cosas, 1)
        self.assertIn(self.cosas, carpetas_con_material(self.org, self.duena, self.m_duena))

    def test_cuentan_los_documentos_de_las_subcarpetas(self):
        """Quien llena Facturación/2026 llenó Facturación."""
        hija = Carpeta.objects.create(
            organization=self.org, name='2026', parent=self.cosas, created_by=self.duena,
        )
        self._llenar(hija, UMBRAL_DOCUMENTOS)

        self.assertIn(self.cosas, carpetas_con_material(self.org, self.duena, self.m_duena))

    def test_una_carpeta_que_ya_tiene_agente_no_se_vuelve_a_proponer(self):
        self._llenar(self.cosas, UMBRAL_DOCUMENTOS)
        Agent.objects.create(organization=self.org, name='El que ya está', carpeta=self.cosas)

        self.assertNotIn(self.cosas, carpetas_con_material(self.org, self.duena, self.m_duena))

    def test_no_se_proponen_agentes_sobre_carpetas_personales(self):
        """Lo de cada uno es de cada uno: ahí no va un agente de la empresa."""
        mia = carpeta_personal(self.org, self.empleado)
        self._llenar(mia, UMBRAL_DOCUMENTOS)

        self.assertNotIn(mia, carpetas_con_material(self.org, self.empleado, self.m_empleado))

    def test_no_se_propone_lo_que_la_persona_no_puede_editar(self):
        """Ofrecerlo revelaría que esa carpeta existe, y además no podría aceptarlo."""
        remuneraciones = Carpeta.objects.get(organization=self.org, name='Remuneraciones')
        self._llenar(remuneraciones, UMBRAL_DOCUMENTOS)

        candidatas = carpetas_con_material(self.org, self.empleado, self.m_empleado)
        self.assertNotIn(remuneraciones, candidatas)
        self.assertIn(
            remuneraciones, carpetas_con_material(self.org, self.duena, self.m_duena),
        )

    # ── qué se propone ───────────────────────────────────────────────────────

    def test_el_nombre_sale_del_contenido_no_de_la_carpeta(self):
        """Una carpeta «cosas» con doce facturas tiene que dar un agente de facturación."""
        vaga = Carpeta.objects.create(
            organization=self.org, name='cosas', created_by=self.duena,
        )
        self._llenar(vaga, UMBRAL_DOCUMENTOS)

        with mock.patch('services.agent_service.chat_direct', return_value=RESPUESTA_DEL_MODELO):
            propuesta = redactar(vaga)

        self.assertEqual(propuesta['nombre'], 'Facturación')
        self.assertEqual(propuesta['icono'], '🧾')
        self.assertFalse(propuesta['de_respaldo'])

    def test_lee_el_json_aunque_venga_en_un_bloque_de_codigo(self):
        self._llenar(self.cosas, UMBRAL_DOCUMENTOS)
        envuelto = f'Claro, acá va:\n```json\n{RESPUESTA_DEL_MODELO}\n```'

        with mock.patch('services.agent_service.chat_direct', return_value=envuelto):
            propuesta = redactar(self.cosas)

        self.assertEqual(propuesta['nombre'], 'Facturación')

    def test_si_el_modelo_se_cae_igual_hay_propuesta(self):
        """Un problema del proveedor no puede dejar al producto sin forma de crear agentes."""
        self._llenar(self.cosas, UMBRAL_DOCUMENTOS)

        with mock.patch('services.agent_service.chat_direct', side_effect=RuntimeError('502')):
            propuesta = redactar(self.cosas)

        self.assertTrue(propuesta['de_respaldo'])
        self.assertEqual(propuesta['nombre'], 'Facturación')   # el de la carpeta
        self.assertTrue(propuesta['instrucciones'])

    def test_si_el_modelo_contesta_cualquier_cosa_tambien(self):
        self._llenar(self.cosas, UMBRAL_DOCUMENTOS)

        with mock.patch('services.agent_service.chat_direct', return_value='No entendí la pregunta.'):
            propuesta = redactar(self.cosas)

        self.assertTrue(propuesta['de_respaldo'])

    def test_un_json_a_medias_se_completa_con_el_respaldo(self):
        self._llenar(self.cosas, UMBRAL_DOCUMENTOS)

        with mock.patch('services.agent_service.chat_direct', return_value='{"nombre": "Cobranzas"}'):
            propuesta = redactar(self.cosas)

        self.assertEqual(propuesta['nombre'], 'Cobranzas')
        self.assertTrue(propuesta['instrucciones'])   # vino del respaldo

    # ── aceptar ──────────────────────────────────────────────────────────────

    def test_aceptar_crea_el_agente_colgado_de_la_carpeta(self):
        self._llenar(self.cosas, UMBRAL_DOCUMENTOS)

        with mock.patch('services.agent_service.chat_direct', return_value=RESPUESTA_DEL_MODELO):
            agente = crear_desde_propuesta(self.cosas, self.duena, membership=self.m_duena)

        self.assertEqual(agente.carpeta_id, self.cosas.pk)
        self.assertEqual(agente.name, 'Facturación')
        self.assertEqual(agente.created_by, self.duena)
        self.assertTrue(agente.instructions)

    def test_el_agente_nace_viendo_lo_de_su_carpeta(self):
        """El alcance no se elige: viene con el sitio del que cuelga."""
        from apps.workspaces.permissions import alcance_de_agente

        self._llenar(self.cosas, UMBRAL_DOCUMENTOS)
        with mock.patch('services.agent_service.chat_direct', return_value=RESPUESTA_DEL_MODELO):
            agente = crear_desde_propuesta(self.cosas, self.duena, membership=self.m_duena)

        _, docs = alcance_de_agente(agente)
        self.assertEqual(len(docs), UMBRAL_DOCUMENTOS)

    def test_aceptar_dos_veces_no_duplica(self):
        self._llenar(self.cosas, UMBRAL_DOCUMENTOS)
        propuesta = {'nombre': 'Facturación', 'descripcion': '', 'instrucciones': '', 'icono': ''}

        primero = crear_desde_propuesta(self.cosas, self.duena, propuesta, self.m_duena)
        segundo = crear_desde_propuesta(self.cosas, self.duena, propuesta, self.m_duena)

        self.assertEqual(primero.pk, segundo.pk)
        self.assertEqual(Agent.objects.filter(carpeta=self.cosas).count(), 1)

    def test_no_se_puede_aceptar_sobre_una_carpeta_ajena(self):
        """Se comprueba de nuevo al aceptar: entre proponer y aceptar la carpeta pudo cambiar."""
        remuneraciones = Carpeta.objects.get(organization=self.org, name='Remuneraciones')
        self._llenar(remuneraciones, UMBRAL_DOCUMENTOS)
        propuesta = {'nombre': 'Sueldos', 'descripcion': '', 'instrucciones': '', 'icono': ''}

        with self.assertRaises(PermissionError):
            crear_desde_propuesta(remuneraciones, self.empleado, propuesta, self.m_empleado)

        self.assertFalse(Agent.objects.filter(carpeta=remuneraciones).exists())


class EndpointsDePropuestasTests(TestCase):
    """Los tres endpoints, y sobre todo quién NO pasa por ellos."""

    def setUp(self):
        from rest_framework.test import APIClient

        self.client = APIClient()
        self.duena = User.objects.create_user(
            username='duena@afable.test', email='duena@afable.test', password='x',
        )
        self.empleado = User.objects.create_user(
            username='empleado@afable.test', email='empleado@afable.test', password='x',
        )
        self.org = Organization.objects.create(owner=self.duena, name='Cocinas SpA')
        self.org.agregar_miembro(self.duena, ROLE_ADMIN)
        self.org.agregar_miembro(self.empleado, ROLE_MEMBER)

        crear_estructura(self.org, 'general', self.duena)
        self.carpeta = Carpeta.objects.get(organization=self.org, name='Facturación')
        for i in range(UMBRAL_DOCUMENTOS):
            CompanyDocument.objects.create(
                organization=self.org, title=f'Factura {i}', file=f'f{i}.pdf',
                carpeta=self.carpeta,
            )

    def test_la_lista_dice_que_carpetas_estan_listas(self):
        self.client.force_authenticate(self.duena)
        r = self.client.get('/api/v1/agents/propuestas/', {'workspace': self.org.slug})

        self.assertEqual(r.status_code, 200)
        rutas = [c['nombre'] for c in r.data['carpetas']]
        self.assertIn('Facturación', rutas)
        self.assertEqual(r.data['umbral'], UMBRAL_DOCUMENTOS)

    def test_sin_empresa_no_responde(self):
        self.client.force_authenticate(self.duena)
        r = self.client.get('/api/v1/agents/propuestas/')
        self.assertEqual(r.status_code, 400)

    def test_redactar_devuelve_el_borrador_sin_crear_nada(self):
        self.client.force_authenticate(self.duena)
        with mock.patch('services.agent_service.chat_direct', return_value=RESPUESTA_DEL_MODELO):
            r = self.client.post('/api/v1/agents/propuestas/redactar/', {
                'workspace': self.org.slug, 'carpeta': self.carpeta.pk,
            }, format='json')

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['nombre'], 'Facturación')
        self.assertFalse(Agent.objects.filter(carpeta=self.carpeta).exists())

    def test_no_se_redacta_sobre_una_carpeta_sin_material(self):
        vacia = Carpeta.objects.get(organization=self.org, name='Legal')
        self.client.force_authenticate(self.duena)
        r = self.client.post('/api/v1/agents/propuestas/redactar/', {
            'workspace': self.org.slug, 'carpeta': vacia.pk,
        }, format='json')

        self.assertEqual(r.status_code, 400)

    def test_una_carpeta_de_otra_empresa_no_existe(self):
        otra_duena = User.objects.create_user(username='o@x.test', email='o@x.test', password='x')
        otra = Organization.objects.create(owner=otra_duena, name='Ajena SpA')
        ajena = Carpeta.objects.create(organization=otra, name='Secretos')

        self.client.force_authenticate(self.duena)
        r = self.client.post('/api/v1/agents/propuestas/redactar/', {
            'workspace': self.org.slug, 'carpeta': ajena.pk,
        }, format='json')

        self.assertEqual(r.status_code, 404)

    def test_aceptar_crea_el_agente(self):
        self.client.force_authenticate(self.duena)
        r = self.client.post('/api/v1/agents/propuestas/aceptar/', {
            'workspace': self.org.slug, 'carpeta': self.carpeta.pk,
            'nombre': 'Facturación', 'instrucciones': 'Revisas las facturas.', 'icono': '🧾',
        }, format='json')

        self.assertEqual(r.status_code, 201)
        agente = Agent.objects.get(carpeta=self.carpeta)
        self.assertEqual(agente.name, 'Facturación')
        self.assertEqual(r.data['carpeta'], 'Cocinas SpA / Facturación')

    def test_se_puede_corregir_lo_que_propuso_afable(self):
        """La propuesta es un punto de partida: lo que se evitaba era la pantalla en blanco."""
        self.client.force_authenticate(self.duena)
        self.client.post('/api/v1/agents/propuestas/aceptar/', {
            'workspace': self.org.slug, 'carpeta': self.carpeta.pk,
            'nombre': 'Cobranzas', 'instrucciones': 'Persigues los pagos atrasados.',
        }, format='json')

        self.assertEqual(Agent.objects.get(carpeta=self.carpeta).name, 'Cobranzas')

    def test_sin_nombre_no_crea(self):
        self.client.force_authenticate(self.duena)
        r = self.client.post('/api/v1/agents/propuestas/aceptar/', {
            'workspace': self.org.slug, 'carpeta': self.carpeta.pk, 'nombre': '  ',
        }, format='json')

        self.assertEqual(r.status_code, 400)
        self.assertFalse(Agent.objects.filter(carpeta=self.carpeta).exists())

    def test_hay_que_estar_autenticado(self):
        r = self.client.get('/api/v1/agents/propuestas/', {'workspace': self.org.slug})
        self.assertIn(r.status_code, (401, 403))


class OrigenesTests(TestCase):
    """Sobre qué puede trabajar un agente nuevo.

    Es la mitad que evita que la Fase 4 prometa algo imposible: la ficha de Odoo ofrece «un
    agente que consulta su Odoo», y ese agente no cuelga de ninguna carpeta. Si los orígenes
    fueran solo carpetas, ese agente no se podría crear por ninguna puerta.
    """

    def setUp(self):
        from rest_framework.test import APIClient

        self.client = APIClient()
        self.duena = User.objects.create_user(
            username='duena@afable.test', email='duena@afable.test', password='x',
        )
        self.org = Organization.objects.create(owner=self.duena, name='Cocinas SpA')
        self.org.agregar_miembro(self.duena, ROLE_ADMIN)
        crear_estructura(self.org, 'general', self.duena)
        self.client.force_authenticate(self.duena)

    def _pedir(self):
        return self.client.get('/api/v1/agents/propuestas/origenes/', {'workspace': self.org.slug})

    def test_sin_nada_la_respuesta_viene_vacia(self):
        """Y la pantalla dice qué hacer primero, en vez de un formulario que no se sabe llenar."""
        r = self._pedir()

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['carpetas'], [])
        self.assertEqual(r.data['herramientas'], [])

    def test_aparecen_las_carpetas_con_material(self):
        carpeta = Carpeta.objects.get(organization=self.org, name='Facturación')
        for i in range(UMBRAL_DOCUMENTOS):
            CompanyDocument.objects.create(
                organization=self.org, title=f'F{i}', file=f'f{i}.pdf', carpeta=carpeta,
            )

        nombres = [c['nombre'] for c in self._pedir().data['carpetas']]
        self.assertIn('Facturación', nombres)

    def test_aparecen_las_herramientas_conectadas(self):
        from apps.organizations.models import SystemConnection

        SystemConnection.objects.create(
            organization=self.org, name='Odoo Chile', connector_type='odoo', category='erp',
        )

        herramientas = self._pedir().data['herramientas']
        self.assertEqual(len(herramientas), 1)
        self.assertEqual(herramientas[0]['nombre'], 'Odoo Chile')

    def test_una_herramienta_apagada_no_se_ofrece(self):
        """Se apagó por algo: proponer un agente sobre ella daría un agente mudo."""
        from apps.organizations.models import SystemConnection

        SystemConnection.objects.create(
            organization=self.org, name='Odoo viejo', connector_type='odoo',
            category='erp', is_active=False,
        )

        self.assertEqual(self._pedir().data['herramientas'], [])


class ConstructorConOrigenTests(TestCase):
    """El constructor ahora acepta la carpeta de la que cuelga el agente."""

    def setUp(self):
        from rest_framework.test import APIClient

        self.client = APIClient()
        self.duena = User.objects.create_user(
            username='duena@afable.test', email='duena@afable.test', password='x',
        )
        self.empleado = User.objects.create_user(
            username='empleado@afable.test', email='empleado@afable.test', password='x',
        )
        self.org = Organization.objects.create(owner=self.duena, name='Cocinas SpA')
        self.org.agregar_miembro(self.duena, ROLE_ADMIN)
        self.org.agregar_miembro(self.empleado, ROLE_MEMBER)
        crear_estructura(self.org, 'general', self.duena)
        self.carpeta = Carpeta.objects.get(organization=self.org, name='Facturación')

    def test_el_agente_queda_colgado_de_la_carpeta(self):
        self.client.force_authenticate(self.duena)
        r = self.client.post('/api/v1/agents/constructor/', {
            'workspace': self.org.slug, 'name': 'Facturación', 'carpeta': self.carpeta.pk,
        }, format='json')

        self.assertEqual(r.status_code, 201)
        self.assertEqual(Agent.objects.get(name='Facturación').carpeta_id, self.carpeta.pk)

    def test_no_se_puede_colgar_de_una_carpeta_que_no_se_puede_editar(self):
        remuneraciones = Carpeta.objects.get(organization=self.org, name='Remuneraciones')
        self.client.force_authenticate(self.empleado)

        r = self.client.post('/api/v1/agents/constructor/', {
            'workspace': self.org.slug, 'name': 'Sueldos', 'carpeta': remuneraciones.pk,
        }, format='json')

        self.assertEqual(r.status_code, 403)
        self.assertFalse(Agent.objects.filter(name='Sueldos').exists())

    def test_una_carpeta_de_otra_empresa_no_existe(self):
        otra_duena = User.objects.create_user(username='o@x.test', email='o@x.test', password='x')
        otra = Organization.objects.create(owner=otra_duena, name='Ajena SpA')
        ajena = Carpeta.objects.create(organization=otra, name='Secretos')

        self.client.force_authenticate(self.duena)
        r = self.client.post('/api/v1/agents/constructor/', {
            'workspace': self.org.slug, 'name': 'Espía', 'carpeta': ajena.pk,
        }, format='json')

        self.assertEqual(r.status_code, 404)


class ModeloDeTrabajoAutonomoTests(TestCase):
    """Lo que Afable hace sin que se lo pidan corre en el modelo más barato.

    Es una decisión de negocio, no técnica: ese trabajo lo paga la casa. Si corriera en el
    modelo del chat, el trabajo de fondo se llevaría el presupuesto de quien sí está
    preguntando — y el gasto crecería con cada carpeta que alguien crea, sin que nadie lo
    haya pedido.
    """

    def setUp(self):
        self.duena = User.objects.create_user(
            username='d@afable.test', email='d@afable.test', password='x',
        )
        self.org = Organization.objects.create(owner=self.duena, name='Cocinas SpA')
        self.org.agregar_miembro(self.duena, ROLE_ADMIN)
        crear_estructura(self.org, 'general', self.duena)
        self.carpeta = Carpeta.objects.get(organization=self.org, name='Facturación')
        for i in range(UMBRAL_DOCUMENTOS):
            CompanyDocument.objects.create(
                organization=self.org, title=f'Factura {i}', file=f'f{i}.pdf',
                carpeta=self.carpeta,
            )

    def test_el_default_es_el_mas_barato_de_deepseek(self):
        from services.agent_service import modelo_autonomo

        self.assertEqual(modelo_autonomo(), 'deepseek-v4-flash')

    def test_la_propuesta_no_usa_el_modelo_del_chat(self):
        """Se pasa explícito: si se dejara al default global, correría en `AI_PROVIDER`."""
        from services.agent_service import modelo_autonomo

        with mock.patch('services.agent_service.chat_direct',
                        return_value=RESPUESTA_DEL_MODELO) as llamada:
            redactar(self.carpeta)

        self.assertEqual(llamada.call_args.kwargs['model'], modelo_autonomo())

    def test_el_modelo_economico_tiene_tarifa_cargada(self):
        """Sin tarifa, todo el trabajo de fondo se registraría en cero y sería invisible."""
        from apps.payments.models import TarifaModelo

        from django.core.management import call_command
        call_command('seed_tarifas')

        self.assertTrue(
            TarifaModelo.objects.filter(modelo='deepseek-v4-flash').exists(),
            'El modelo de la capa autónoma tiene que estar tarifado o su gasto no se mide.',
        )

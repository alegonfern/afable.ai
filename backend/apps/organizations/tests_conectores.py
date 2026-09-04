"""Los conectores: la ficha, la carpeta que crean, y que no se puedan borrar.

La prueba que más importa acá es la de `test_borrar_un_conector_lo_apaga_pero_no_lo_borra`.
Es la regla que protege la consistencia de todo lo que entró por un sistema: si un conector
se pudiera eliminar, quedarían documentos sin origen y agentes apuntando a algo que ya no
existe, y esa estructura es justamente lo que le da valor al repositorio.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.archivos.models import Carpeta
from apps.organizations.models import Organization, SystemConnection
from apps.workspaces.models import ROLE_ADMIN, ROLE_MEMBER
from services.conectores import DISPONIBLE, PRONTO, carpeta_del_conector, catalogo, ficha
from services.estructura_inicial import crear_estructura

User = get_user_model()


class CatalogoTests(TestCase):
    def test_cada_ficha_contesta_las_tres_preguntas(self):
        """Qué trae, qué voy a poder preguntar y qué agente aparece. Sin eso no se ofrece."""
        for c in catalogo():
            self.assertTrue(c['titular'], c['clave'])
            self.assertTrue(c['que_trae'], c['clave'])
            self.assertTrue(c['que_podra_preguntar'], c['clave'])

    def test_lo_que_no_esta_construido_se_marca_como_tal(self):
        """Prometer un conector que no existe se paga en la primera reunión."""
        self.assertEqual(ficha('hubspot')['estado'], PRONTO)
        self.assertEqual(ficha('whatsapp')['estado'], PRONTO)
        self.assertEqual(ficha('odoo')['estado'], DISPONIBLE)

    def test_los_disponibles_son_los_que_el_modelo_sabe_conectar(self):
        tipos = dict(SystemConnection.CONNECTOR_TYPES)
        for c in catalogo(solo_disponibles=True):
            self.assertIn(c['clave'], tipos, f"{c['clave']} se ofrece pero no existe")


class CarpetaDelConectorTests(TestCase):
    def setUp(self):
        self.duena = User.objects.create_user(
            username='d@afable.test', email='d@afable.test', password='x',
        )
        self.org = Organization.objects.create(owner=self.duena, name='Cocinas SpA')
        self.org.agregar_miembro(self.duena, ROLE_ADMIN)
        crear_estructura(self.org, 'general', self.duena)

    def test_el_conector_crea_su_carpeta_dentro_de_la_empresa(self):
        carpeta = carpeta_del_conector(self.org, 'odoo', self.duena)

        self.assertEqual(carpeta.name, 'Odoo')
        self.assertEqual(carpeta.parent.name, 'Cocinas SpA')

    def test_no_la_duplica_si_ya_estaba(self):
        primera = carpeta_del_conector(self.org, 'odoo', self.duena)
        self.assertEqual(carpeta_del_conector(self.org, 'odoo', self.duena).pk, primera.pk)

    def test_los_que_no_traen_material_no_ensucian_el_arbol(self):
        """Slack y WhatsApp llevan avisos hacia afuera; una carpeta suya nunca se llenaría."""
        self.assertIsNone(carpeta_del_conector(self.org, 'slack', self.duena))
        self.assertIsNone(carpeta_del_conector(self.org, 'whatsapp', self.duena))

    def test_un_conector_desconocido_no_revienta(self):
        self.assertIsNone(carpeta_del_conector(self.org, 'lo-que-sea', self.duena))


class EndpointsDeConectoresTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.duena = User.objects.create_user(
            username='d@afable.test', email='d@afable.test', password='x',
        )
        self.org = Organization.objects.create(owner=self.duena, name='Cocinas SpA')
        self.org.agregar_miembro(self.duena, ROLE_ADMIN)
        crear_estructura(self.org, 'general', self.duena)
        self.client.force_authenticate(self.duena)

    def _conectar(self):
        return self.client.post('/api/v1/organizations/connections/', {
            'organization': self.org.pk, 'name': 'Odoo Chile',
            'connector_type': 'odoo', 'category': 'erp', 'config': {},
        }, format='json')

    def test_el_catalogo_se_publica_con_las_fichas(self):
        r = self.client.get('/api/v1/organizations/connections/catalogo/')

        self.assertEqual(r.status_code, 200)
        claves = {c['clave'] for c in r.data['conectores']}
        self.assertIn('odoo', claves)
        odoo = next(c for c in r.data['conectores'] if c['clave'] == 'odoo')
        self.assertTrue(odoo['que_podra_preguntar'])

    def test_conectar_crea_la_carpeta_del_conector(self):
        """Lo que entra por un sistema necesita dónde vivir, igual que lo que se sube a mano."""
        r = self._conectar()

        self.assertEqual(r.status_code, 201)
        self.assertTrue(
            Carpeta.objects.filter(organization=self.org, name='Odoo').exists()
        )

    def test_borrar_un_conector_lo_apaga_pero_no_lo_borra(self):
        conn_id = self._conectar().data['id']

        r = self.client.delete(f'/api/v1/organizations/connections/{conn_id}/')

        self.assertEqual(r.status_code, 200)
        conn = SystemConnection.objects.get(pk=conn_id)   # sigue existiendo
        self.assertFalse(conn.is_active)

    def test_el_conector_de_prueba_si_se_descarta(self):
        """Un intento fallido no puede quedar como fantasma apagado en la lista."""
        conn_id = self._conectar().data['id']

        r = self.client.delete(f'/api/v1/organizations/connections/{conn_id}/?descartar=1')

        self.assertEqual(r.status_code, 204)
        self.assertFalse(SystemConnection.objects.filter(pk=conn_id).exists())

    def test_descartar_no_sirve_de_atajo_para_borrar_uno_en_uso(self):
        """La guarda: si ya sincronizó, dejó de ser un intento y pasa a apagarse."""
        conn_id = self._conectar().data['id']
        SystemConnection.objects.filter(pk=conn_id).update(last_synced_at=timezone.now())

        r = self.client.delete(f'/api/v1/organizations/connections/{conn_id}/?descartar=1')

        self.assertEqual(r.status_code, 200)
        self.assertTrue(SystemConnection.objects.filter(pk=conn_id, is_active=False).exists())

    def test_se_puede_volver_a_encender(self):
        conn_id = self._conectar().data['id']
        self.client.delete(f'/api/v1/organizations/connections/{conn_id}/')

        r = self.client.post(
            f'/api/v1/organizations/connections/{conn_id}/estado/',
            {'is_active': True}, format='json',
        )

        self.assertEqual(r.status_code, 200)
        self.assertTrue(SystemConnection.objects.get(pk=conn_id).is_active)

    def test_un_miembro_no_apaga_los_conectores_de_la_empresa(self):
        conn_id = self._conectar().data['id']
        otro = User.objects.create_user(username='o@x.test', email='o@x.test', password='x')
        self.org.agregar_miembro(otro, ROLE_MEMBER)
        self.client.force_authenticate(otro)

        r = self.client.post(
            f'/api/v1/organizations/connections/{conn_id}/estado/',
            {'is_active': False}, format='json',
        )

        self.assertIn(r.status_code, (403, 404))
        self.assertTrue(SystemConnection.objects.get(pk=conn_id).is_active)

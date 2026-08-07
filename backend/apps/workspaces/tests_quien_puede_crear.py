"""Quién puede crear qué dentro de una empresa.

Lo que fijan estas pruebas es el arreglo de un atajo que estaba en dos lados: resolver la
empresa por **propiedad** (`filter(owner=user)`) en vez de por **rol**. Ese atajo tiene dos
filos y los dos muerden:

- el administrador que NO fundó la empresa no podía conectar un sistema;
- quien la fundó podía, aunque le hubieran bajado el rol a miembro.

La propiedad es un accidente de quién apretó "crear"; el rol es la decisión.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.organizations.models import Organization, SystemConnection

from .models import ROLE_ADMIN, ROLE_EDITOR, ROLE_MEMBER

User = get_user_model()


def crear_usuario(email):
    return User.objects.create_user(username=email, email=email, password='afable123')


class QuienPuedeCrearTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.duena = crear_usuario('duena@afable.test')
        self.admin = crear_usuario('admin@afable.test')
        self.editor = crear_usuario('editor@afable.test')
        self.miembro = crear_usuario('miembro@afable.test')
        self.ajeno = crear_usuario('ajeno@afable.test')

        self.org = Organization.objects.create(owner=self.duena, name='Cocinas SpA')
        self.org.agregar_miembro(self.duena, ROLE_MEMBER)   # fundó, pero hoy es miembro
        self.org.agregar_miembro(self.admin, ROLE_ADMIN)
        self.org.agregar_miembro(self.editor, ROLE_EDITOR)
        self.org.agregar_miembro(self.miembro, ROLE_MEMBER)

    def _conectar(self, quien):
        self.client.force_authenticate(quien)
        return self.client.post('/api/v1/organizations/connections/', {
            'organization': self.org.id, 'name': 'Odoo', 'connector_type': 'odoo',
            'config': {'url': 'https://odoo.test'},
        }, format='json')

    # ── Conexiones ───────────────────────────────────────────────────────────

    def test_un_editor_conecta_un_sistema(self):
        self.assertEqual(self._conectar(self.editor).status_code, 201)

    def test_el_administrador_conecta_aunque_no_haya_fundado_la_empresa(self):
        """El caso que el atajo por propiedad dejaba afuera."""
        self.assertEqual(self._conectar(self.admin).status_code, 201)

    def test_un_miembro_no_conecta_un_sistema(self):
        """Conectar es cargar credenciales de la empresa."""
        r = self._conectar(self.miembro)
        self.assertEqual(r.status_code, 403)
        self.assertFalse(SystemConnection.objects.exists())

    def test_haber_fundado_la_empresa_no_alcanza_si_hoy_es_miembro(self):
        """El otro filo del atajo: la propiedad sobrevivía a la baja de rol."""
        r = self._conectar(self.duena)
        self.assertEqual(r.status_code, 403)
        self.assertFalse(SystemConnection.objects.exists())

    def test_para_alguien_de_afuera_la_empresa_no_existe(self):
        self.assertEqual(self._conectar(self.ajeno).status_code, 404)

    # ── Disparadores ─────────────────────────────────────────────────────────

    def _disparador(self, quien):
        self.client.force_authenticate(quien)
        return self.client.post('/api/v1/agents/automations/', {
            'organization': self.org.id, 'name': 'Resumen diario',
            'prompt': 'Resumen de ventas', 'interval_minutes': 1440,
            'notify_email': 'jefe@afable.test',
        }, format='json')

    def test_un_miembro_no_deja_andando_un_disparador(self):
        """Corre solo, consulta los sistemas y manda correos a nombre de la empresa."""
        r = self._disparador(self.miembro)
        self.assertIn(r.status_code, (403, 404))

    def test_un_editor_si(self):
        r = self._disparador(self.editor)
        self.assertEqual(r.status_code, 201, r.data)

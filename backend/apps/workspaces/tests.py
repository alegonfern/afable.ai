"""Pruebas de la pieza de la que dependen todas las etapas siguientes.

Cubren dos cosas y nada más: que la resolución de permisos aísle de verdad un
Workspace de otro, y que el flujo de invitación no deje entrar a quien no
corresponde. Si algo de esto se rompe, se rompe callado y en producción — de ahí
que sean las primeras pruebas del proyecto.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.test import APIClient

from .models import (
    ROLE_ADMIN, ROLE_EDITOR, ROLE_MEMBER, Invitation, Membership, Workspace,
)
from .permissions import require_membership, resolve_membership

User = get_user_model()


def crear_usuario(email, first_name=''):
    return User.objects.create_user(
        username=email, email=email, password='afable123', first_name=first_name,
    )


class ResolucionDePermisosTests(TestCase):
    """El punto único de resolución: `resolve_membership` / `require_membership`."""

    def setUp(self):
        self.admin = crear_usuario('admin@afable.test', 'Ada')
        self.miembro = crear_usuario('miembro@afable.test', 'Bruno')
        self.ajeno = crear_usuario('ajeno@afable.test', 'Carla')

        self.workspace = Workspace.objects.create(name='Cocinas Atika')
        self.workspace.add_member(self.admin, ROLE_ADMIN)
        self.workspace.add_member(self.miembro, ROLE_MEMBER)

        self.otro = Workspace.objects.create(name='Meridian Nautic')
        self.otro.add_member(self.ajeno, ROLE_ADMIN)

    def test_devuelve_la_membresia_con_su_rol(self):
        membresia = resolve_membership(self.miembro, self.workspace.slug)
        self.assertIsNotNone(membresia)
        self.assertEqual(membresia.role, ROLE_MEMBER)

    def test_aisla_un_workspace_de_otro(self):
        """Ser administrador de un Workspace no da nada en el de al lado."""
        self.assertIsNone(resolve_membership(self.ajeno, self.workspace.slug))
        self.assertIsNone(resolve_membership(self.admin, self.otro.slug))

    def test_al_no_miembro_el_workspace_no_existe(self):
        """404 y no 403: un 403 confirmaría que el slug es real."""
        with self.assertRaises(NotFound):
            require_membership(self.ajeno, self.workspace.slug)

    def test_rol_insuficiente_es_403(self):
        with self.assertRaises(PermissionDenied):
            require_membership(self.miembro, self.workspace.slug, minimum_role=ROLE_EDITOR)

    def test_el_orden_de_roles_es_acumulativo(self):
        admin = resolve_membership(self.admin, self.workspace.slug)
        self.assertTrue(admin.has_at_least(ROLE_MEMBER))
        self.assertTrue(admin.has_at_least(ROLE_EDITOR))
        self.assertTrue(admin.has_at_least(ROLE_ADMIN))
        self.assertFalse(resolve_membership(self.miembro, self.workspace.slug).has_at_least(ROLE_EDITOR))

    def test_usuario_anonimo_no_resuelve(self):
        from django.contrib.auth.models import AnonymousUser
        self.assertIsNone(resolve_membership(AnonymousUser(), self.workspace.slug))


class PersonasAPITests(TestCase):
    """Los endpoints que alimentan Admin › Personas."""

    def setUp(self):
        self.client = APIClient()
        self.admin = crear_usuario('admin@afable.test', 'Ada')
        self.miembro = crear_usuario('miembro@afable.test', 'Bruno')
        self.ajeno = crear_usuario('ajeno@afable.test', 'Carla')

        self.workspace = Workspace.objects.create(name='Cocinas Atika')
        self.workspace.add_member(self.admin, ROLE_ADMIN)
        self.workspace.add_member(self.miembro, ROLE_MEMBER)

        self.base = f'/api/v1/workspaces/{self.workspace.slug}'

    def test_miembro_ve_la_lista_de_personas(self):
        self.client.force_authenticate(self.miembro)
        r = self.client.get(f'{self.base}/members/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 2)

    def test_miembro_no_puede_invitar(self):
        self.client.force_authenticate(self.miembro)
        r = self.client.post(f'{self.base}/invitations/', {'email': 'nueva@afable.test'})
        self.assertEqual(r.status_code, 403)

    def test_ajeno_no_ve_nada(self):
        self.client.force_authenticate(self.ajeno)
        self.assertEqual(self.client.get(f'{self.base}/members/').status_code, 404)
        self.assertEqual(self.client.get(f'{self.base}/invitations/').status_code, 404)

    def test_admin_invita_y_se_manda_el_correo(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'{self.base}/invitations/', {'email': 'Nueva@Afable.test', 'role': ROLE_EDITOR})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['email'], 'nueva@afable.test')  # normalizado
        self.assertEqual(r.data['status'], 'pendiente')
        self.assertTrue(r.data['emailed'])
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(Invitation.objects.get().token, mail.outbox[0].body)

    def test_no_se_invita_dos_veces_al_mismo_correo(self):
        self.client.force_authenticate(self.admin)
        self.client.post(f'{self.base}/invitations/', {'email': 'nueva@afable.test'})
        r = self.client.post(f'{self.base}/invitations/', {'email': 'nueva@afable.test'})
        self.assertEqual(r.status_code, 400)

    def test_no_se_invita_a_quien_ya_es_miembro(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(f'{self.base}/invitations/', {'email': self.miembro.email})
        self.assertEqual(r.status_code, 400)

    def test_el_ultimo_administrador_no_puede_degradarse(self):
        self.client.force_authenticate(self.admin)
        membresia = Membership.objects.get(workspace=self.workspace, user=self.admin)
        r = self.client.patch(f'{self.base}/members/{membresia.pk}/', {'role': ROLE_MEMBER})
        self.assertEqual(r.status_code, 400)
        membresia.refresh_from_db()
        self.assertEqual(membresia.role, ROLE_ADMIN)

    def test_admin_saca_a_un_miembro(self):
        self.client.force_authenticate(self.admin)
        membresia = Membership.objects.get(workspace=self.workspace, user=self.miembro)
        r = self.client.delete(f'{self.base}/members/{membresia.pk}/')
        self.assertEqual(r.status_code, 204)
        self.assertFalse(Membership.objects.filter(pk=membresia.pk).exists())


class InvitacionesTests(TestCase):
    """Aceptar el link: lo único que separa a un extraño de los datos del Workspace."""

    def setUp(self):
        self.client = APIClient()
        self.admin = crear_usuario('admin@afable.test', 'Ada')
        self.workspace = Workspace.objects.create(name='Cocinas Atika')
        self.workspace.add_member(self.admin, ROLE_ADMIN)
        self.invitacion = Invitation.create_for(
            self.workspace, 'invitada@afable.test', ROLE_EDITOR, invited_by=self.admin,
        )

    def test_la_vista_previa_es_publica_y_no_filtra_el_workspace(self):
        r = self.client.get(f'/api/v1/invitations/{self.invitacion.token}/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['workspace_name'], 'Cocinas Atika')
        self.assertEqual(r.data['status'], 'pendiente')
        self.assertNotIn('members', r.data)

    def test_aceptar_crea_la_membresia_con_el_rol_invitado(self):
        invitada = crear_usuario('invitada@afable.test', 'Dani')
        self.client.force_authenticate(invitada)
        r = self.client.post(f'/api/v1/invitations/{self.invitacion.token}/accept/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['role'], ROLE_EDITOR)

        membresia = Membership.objects.get(workspace=self.workspace, user=invitada)
        self.assertEqual(membresia.role, ROLE_EDITOR)
        self.invitacion.refresh_from_db()
        self.assertEqual(self.invitacion.status, 'aceptada')

    def test_otro_correo_no_puede_usar_el_link(self):
        colado = crear_usuario('colado@afable.test', 'Eze')
        self.client.force_authenticate(colado)
        r = self.client.post(f'/api/v1/invitations/{self.invitacion.token}/accept/')
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Membership.objects.filter(workspace=self.workspace, user=colado).exists())

    def test_una_invitacion_vencida_no_sirve(self):
        Invitation.objects.filter(pk=self.invitacion.pk).update(
            expires_at=timezone.now() - timedelta(days=1),
        )
        invitada = crear_usuario('invitada@afable.test', 'Dani')
        self.client.force_authenticate(invitada)
        r = self.client.post(f'/api/v1/invitations/{self.invitacion.token}/accept/')
        self.assertEqual(r.status_code, 400)
        self.assertIn('vencida', r.data['detail'])

    def test_reenviar_cambia_el_token(self):
        token_viejo = self.invitacion.token
        self.client.force_authenticate(self.admin)
        r = self.client.post(
            f'/api/v1/workspaces/{self.workspace.slug}/invitations/{self.invitacion.pk}/resend/'
        )
        self.assertEqual(r.status_code, 200)
        self.invitacion.refresh_from_db()
        self.assertNotEqual(self.invitacion.token, token_viejo)
        self.assertEqual(
            self.client.get(f'/api/v1/invitations/{token_viejo}/').status_code, 404,
        )

    def test_revocada_deja_de_servir(self):
        self.client.force_authenticate(self.admin)
        r = self.client.delete(
            f'/api/v1/workspaces/{self.workspace.slug}/invitations/{self.invitacion.pk}/'
        )
        self.assertEqual(r.status_code, 204)

        invitada = crear_usuario('invitada@afable.test', 'Dani')
        self.client.force_authenticate(invitada)
        r = self.client.post(f'/api/v1/invitations/{self.invitacion.token}/accept/')
        self.assertEqual(r.status_code, 400)


class PuenteConOrganizationTests(TestCase):
    """El puente que mantiene viva la app anterior mientras se migra pantalla a pantalla.

    `Organization` sigue siendo el dueño de las conexiones, los documentos y el
    contexto, y `agent_service` lee su sector para el prompt. Si el enlace o el
    espejo se rompen, editar el Workspace no tendría ningún efecto visible y nadie
    se daría cuenta.
    """

    def setUp(self):
        self.client = APIClient()
        self.admin = crear_usuario('admin@afable.test', 'Ada')
        self.client.force_authenticate(self.admin)

    def test_crear_workspace_enlaza_una_organization(self):
        r = self.client.post('/api/v1/workspaces/', {'name': 'Cocinas Atika', 'sector': 'manufactura'})
        self.assertEqual(r.status_code, 201)

        workspace = Workspace.objects.get(slug=r.data['slug'])
        self.assertIsNotNone(workspace.organization)
        self.assertEqual(workspace.organization.owner, self.admin)
        self.assertEqual(workspace.organization.name, 'Cocinas Atika')
        self.assertEqual(workspace.organization.sector, 'manufactura')

    def test_editar_el_workspace_se_refleja_en_la_organization(self):
        workspace = Workspace.create_for_owner(self.admin)
        r = self.client.patch(f'/api/v1/workspaces/{workspace.slug}/', {
            'name': 'Meridian Nautic',
            'sector': 'turismo',
            'employees': '12',
            'tax_id': '76.999.888-1',
            'description': 'Gestión náutica en Palma de Mallorca.',
        })
        self.assertEqual(r.status_code, 200)

        org = Workspace.objects.get(pk=workspace.pk).organization
        self.assertEqual(org.name, 'Meridian Nautic')
        self.assertEqual(org.sector, 'turismo')
        self.assertEqual(org.employees, '12')
        self.assertEqual(org.rut, '76.999.888-1')
        self.assertIn('Palma de Mallorca', org.description)

    def test_dos_workspaces_no_comparten_la_misma_organization(self):
        uno = Workspace.create_for_owner(self.admin, name='Uno')
        dos = Workspace.create_for_owner(self.admin, name='Dos')
        self.assertIsNotNone(uno.organization_id)
        self.assertIsNotNone(dos.organization_id)
        self.assertNotEqual(uno.organization_id, dos.organization_id)

    def test_los_sectores_del_selector_son_los_de_la_organization(self):
        from apps.organizations.models import Organization

        r = self.client.get('/api/v1/workspaces/sectores/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            [s['value'] for s in r.data],
            [v for v, _ in Organization.SECTORS],
        )


class AltaDeUsuarioTests(TestCase):
    """Cada quien estrena su propio Workspace, no la plataforma entera."""

    def test_registrarse_crea_el_workspace_propio_como_admin(self):
        client = APIClient()
        r = client.post('/api/v1/auth/register/', {
            'email': 'nuevo@afable.test', 'password': 'afable123', 'first_name': 'Nico',
        })
        self.assertEqual(r.status_code, 201)

        usuario = User.objects.get(email='nuevo@afable.test')
        membresia = Membership.objects.get(user=usuario)
        self.assertEqual(membresia.role, ROLE_ADMIN)
        self.assertEqual(membresia.workspace.name, 'Workspace de Nico')

    def test_dos_usuarios_no_comparten_workspace(self):
        client = APIClient()
        for correo in ('uno@afable.test', 'dos@afable.test'):
            client.post('/api/v1/auth/register/', {'email': correo, 'password': 'afable123'})

        uno = User.objects.get(email='uno@afable.test')
        dos = User.objects.get(email='dos@afable.test')
        self.assertEqual(Workspace.objects.count(), 2)
        self.assertNotEqual(
            Membership.objects.get(user=uno).workspace_id,
            Membership.objects.get(user=dos).workspace_id,
        )


class EspaciosTests(TestCase):
    """Los Espacios: que un Espacio restringido no se filtre, y que enganchar funcione.

    El caso que importa es el del medio: un miembro común no puede ver el Espacio
    restringido del que no forma parte, pero el administrador sí — porque tiene
    que poder administrar lo que no usa.
    """

    def setUp(self):
        from .models import Space
        from .permissions import spaces_visible_to

        self.Space = Space
        self.spaces_visible_to = spaces_visible_to

        self.admin = crear_usuario('admin-esp@afable.test', 'Ada')
        self.miembro = crear_usuario('miembro-esp@afable.test', 'Bruno')
        self.invitado = crear_usuario('invitado-esp@afable.test', 'Carla')

        self.workspace = Workspace.objects.create(name='Espacios SpA')
        self.m_admin = self.workspace.add_member(self.admin, ROLE_ADMIN)
        self.m_miembro = self.workspace.add_member(self.miembro, ROLE_MEMBER)
        self.m_invitado = self.workspace.add_member(self.invitado, ROLE_MEMBER)

        self.abierto = Space.objects.create(
            workspace=self.workspace, name='General', visibility='abierto',
        )
        self.privado = Space.objects.create(
            workspace=self.workspace, name='Personas', visibility='restringido',
        )
        self.privado.members.add(self.invitado)

    def test_el_espacio_abierto_lo_ve_cualquier_miembro(self):
        visibles = self.spaces_visible_to(self.m_miembro)
        self.assertIn(self.abierto, visibles)

    def test_el_restringido_no_se_le_filtra_a_quien_no_esta_dentro(self):
        visibles = self.spaces_visible_to(self.m_miembro)
        self.assertNotIn(self.privado, visibles)

    def test_el_restringido_lo_ve_quien_fue_agregado(self):
        self.assertIn(self.privado, self.spaces_visible_to(self.m_invitado))

    def test_el_administrador_ve_todos_los_espacios(self):
        visibles = self.spaces_visible_to(self.m_admin)
        self.assertIn(self.abierto, visibles)
        self.assertIn(self.privado, visibles)

    def test_pedir_un_espacio_que_no_ve_es_404_no_403(self):
        from rest_framework.exceptions import NotFound as NF

        from .permissions import require_space

        with self.assertRaises(NF):
            require_space(self.m_miembro, self.privado.slug)

    def test_el_slug_se_arma_solo_y_no_choca_entre_hermanos(self):
        otro = self.Space.objects.create(workspace=self.workspace, name='General')
        self.assertEqual(self.abierto.slug, 'general')
        self.assertEqual(otro.slug, 'general-2')

    def test_la_api_lista_solo_los_espacios_que_corresponden(self):
        client = APIClient()
        client.force_authenticate(user=self.miembro)
        resp = client.get(f'/api/v1/workspaces/{self.workspace.slug}/espacios/')
        self.assertEqual(resp.status_code, 200)
        nombres = [e['name'] for e in resp.json()]
        self.assertEqual(nombres, ['General'])

    def test_un_miembro_comun_no_puede_crear_un_espacio(self):
        client = APIClient()
        client.force_authenticate(user=self.miembro)
        resp = client.post(
            f'/api/v1/workspaces/{self.workspace.slug}/espacios/', {'name': 'Ventas'}, format='json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_enganchar_una_conexion_de_otra_empresa_no_hace_nada(self):
        from apps.organizations.models import Organization, SystemConnection

        ajena = Organization.objects.create(owner=self.admin, name='Otra empresa')
        conexion = SystemConnection.objects.create(
            organization=ajena, name='Odoo ajeno', connector_type='odoo',
        )
        client = APIClient()
        client.force_authenticate(user=self.admin)
        resp = client.post(
            f'/api/v1/workspaces/{self.workspace.slug}/espacios/{self.abierto.slug}/conexiones/',
            {'ids': [conexion.id]}, format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.abierto.connections.count(), 0)


class LogoDelWorkspaceTests(TestCase):
    """El logo y lo que el selector necesita para decir en qué empresa se está.

    No existía en ningún modelo —tampoco en `Organization`— y sin él el selector no podía
    distinguir dos empresas sin obligar a leer el nombre.
    """

    def setUp(self):
        self.client = APIClient()
        self.admin = crear_usuario('admin@afable.test', 'Ada')
        self.miembro = crear_usuario('miembro@afable.test', 'Bruno')
        self.workspace = Workspace.objects.create(name='Panaderia La Espiga', sector='alimentos')
        self.workspace.add_member(self.admin, ROLE_ADMIN)
        self.workspace.add_member(self.miembro, ROLE_MEMBER)
        self.url = f'/api/v1/workspaces/{self.workspace.slug}/'

    def un_png(self):
        """Un PNG mínimo de verdad: `ImageField` valida la imagen, no la extensión."""
        import io

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        buf = io.BytesIO()
        Image.new('RGB', (12, 12), (216, 120, 58)).save(buf, format='PNG')
        return SimpleUploadedFile('logo.png', buf.getvalue(), content_type='image/png')

    def test_sin_logo_la_api_devuelve_null_y_no_una_url_rota(self):
        self.client.force_authenticate(self.miembro)
        r = self.client.get(self.url)
        self.assertIsNone(r.data['logo_url'])

    def test_el_administrador_sube_un_logo(self):
        self.client.force_authenticate(self.admin)
        r = self.client.patch(self.url, {'logo': self.un_png()}, format='multipart')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data['logo_url'])

    def test_se_quita_mandando_null(self):
        self.client.force_authenticate(self.admin)
        self.client.patch(self.url, {'logo': self.un_png()}, format='multipart')
        r = self.client.patch(self.url, {'logo': None}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.data['logo_url'])

    def test_un_miembro_comun_no_cambia_el_logo(self):
        self.client.force_authenticate(self.miembro)
        r = self.client.patch(self.url, {'logo': self.un_png()}, format='multipart')
        self.assertEqual(r.status_code, 403)

    def test_lo_que_no_es_una_imagen_no_pasa(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.force_authenticate(self.admin)
        falso = SimpleUploadedFile('logo.png', b'no soy una imagen', content_type='image/png')
        r = self.client.patch(self.url, {'logo': falso}, format='multipart')
        self.assertEqual(r.status_code, 400)

    def test_el_sector_viaja_en_palabras(self):
        """El selector muestra el sector como subtítulo: 'alimentos' no se lee igual."""
        self.client.force_authenticate(self.miembro)
        r = self.client.get(self.url)
        self.assertEqual(r.data['sector'], 'alimentos')
        self.assertEqual(r.data['sector_label'], 'Alimentos y bebidas')

    def test_la_lista_del_selector_trae_todo_lo_que_muestra(self):
        """El selector pinta marca, nombre, rol y cuánta gente: los cuatro sin otro viaje."""
        self.client.force_authenticate(self.miembro)
        r = self.client.get('/api/v1/workspaces/')
        fila = r.data[0]
        for campo in ('name', 'slug', 'logo_url', 'sector_label', 'my_role', 'member_count'):
            self.assertIn(campo, fila)
        self.assertEqual(fila['my_role'], ROLE_MEMBER)
        self.assertEqual(fila['member_count'], 2)

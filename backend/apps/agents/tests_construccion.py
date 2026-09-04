"""Las herramientas con las que el chat construye.

Lo que se prueba acá es sobre todo lo que **no** deja hacer. Estas herramientas escriben
estructura y reparten acceso, así que el riesgo no es que fallen: es que funcionen para
quien no debía. Si el chat pudiera crear carpetas donde la persona no puede, o invitar
gente sin ser administrador, sería la puerta de atrás de todo el sistema de permisos.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.archivos.models import Carpeta
from apps.organizations.models import Organization
from apps.workspaces.models import (
    ROLE_ADMIN,
    ROLE_EDITOR,
    ROLE_MEMBER,
    Invitation,
)
from services.agent_tools import execute_tool
from services.estructura_inicial import carpeta_personal, crear_estructura

User = get_user_model()


class ConstruirDesdeElChatTests(TestCase):
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

    def correr(self, nombre, args, usuario):
        return execute_tool(nombre, args, self.org, [], usuario=usuario)

    # ── armar la estructura ───────────────────────────────────────────────────

    def test_el_administrador_arma_la_empresa_de_una(self):
        r = self.correr('armar_estructura_inicial', {'rubro': 'construccion'}, self.duena)

        self.assertNotIn('error', r)
        self.assertEqual(r['carpeta'], 'Cocinas SpA')
        self.assertIn('Obras', r['creadas'])
        self.assertIn('Contabilidad', r['creadas'])

    def test_un_miembro_no_puede_armar_la_estructura(self):
        r = self.correr('armar_estructura_inicial', {'rubro': 'general'}, self.empleado)

        self.assertIn('error', r)
        self.assertFalse(Carpeta.objects.filter(organization=self.org).exists())

    def test_sin_usuario_no_se_arma_nada(self):
        """Una automatización mal cableada no puede terminar creando la empresa entera."""
        r = execute_tool('armar_estructura_inicial', {'rubro': 'general'}, self.org, [])

        self.assertIn('error', r)
        self.assertFalse(Carpeta.objects.filter(organization=self.org).exists())

    def test_un_rubro_inventado_se_rechaza_y_no_crea_a_medias(self):
        r = self.correr('armar_estructura_inicial', {'rubro': 'astronáutica'}, self.duena)

        self.assertIn('error', r)
        self.assertFalse(Carpeta.objects.filter(organization=self.org).exists())

    # ── crear una carpeta ─────────────────────────────────────────────────────

    def test_crear_una_carpeta_en_la_raiz(self):
        r = self.correr('crear_carpeta', {'nombre': 'Pendientes'}, self.duena)

        self.assertNotIn('error', r)
        self.assertTrue(
            Carpeta.objects.filter(organization=self.org, name='Pendientes', parent=None).exists()
        )

    def test_crear_una_carpeta_adentro_de_otra(self):
        crear_estructura(self.org, 'general', self.duena)
        r = self.correr('crear_carpeta', {'nombre': '2026', 'dentro_de': 'Contabilidad'}, self.duena)

        self.assertNotIn('error', r)
        self.assertEqual(r['ruta'], 'Cocinas SpA / Contabilidad / 2026')

    def test_no_se_puede_crear_donde_la_persona_no_podria_a_mano(self):
        """El permiso lo resuelve el mismo motor que usa la pantalla, no una copia."""
        crear_estructura(self.org, 'general', self.duena)
        r = self.correr('crear_carpeta', {'nombre': 'Sueldos 2026',
                                          'dentro_de': 'Remuneraciones'}, self.empleado)

        self.assertIn('error', r)
        self.assertFalse(Carpeta.objects.filter(organization=self.org, name='Sueldos 2026').exists())

    def test_un_miembro_no_escribe_en_la_carpeta_de_la_empresa(self):
        """`root` es de lectura para el equipo: solo la modifica un administrador."""
        crear_estructura(self.org, 'general', self.duena)
        r = self.correr('crear_carpeta', {'nombre': 'Mía', 'dentro_de': 'Cocinas SpA'}, self.empleado)

        self.assertIn('error', r)

    def test_en_su_propia_carpeta_si_puede(self):
        mia = carpeta_personal(self.org, self.empleado)
        r = self.correr('crear_carpeta', {'nombre': 'Borradores',
                                          'dentro_de': mia.name}, self.empleado)

        self.assertNotIn('error', r)

    def test_no_duplica_una_carpeta_que_ya_esta(self):
        self.correr('crear_carpeta', {'nombre': 'Pendientes'}, self.duena)
        r = self.correr('crear_carpeta', {'nombre': 'Pendientes'}, self.duena)

        self.assertIn('error', r)
        self.assertEqual(
            Carpeta.objects.filter(organization=self.org, name='Pendientes').count(), 1,
        )

    def test_avisa_cuando_la_carpeta_madre_no_existe(self):
        r = self.correr('crear_carpeta', {'nombre': 'X', 'dentro_de': 'Marketing'}, self.duena)
        self.assertIn('error', r)

    def test_sin_nombre_no_crea(self):
        r = self.correr('crear_carpeta', {'nombre': '   '}, self.duena)
        self.assertIn('error', r)

    # ── invitar ───────────────────────────────────────────────────────────────

    def test_el_administrador_invita(self):
        r = self.correr('invitar_persona', {'correo': 'Nueva@Empresa.CL', 'rol': 'editor'}, self.duena)

        self.assertNotIn('error', r)
        invitacion = Invitation.objects.get(organization=self.org)
        self.assertEqual(invitacion.email, 'nueva@empresa.cl')   # normalizado
        self.assertEqual(invitacion.role, ROLE_EDITOR)
        self.assertEqual(invitacion.invited_by, self.duena)

    def test_un_miembro_no_invita(self):
        """Repartir acceso a los datos de la empresa es de administradores, se pida como se pida."""
        r = self.correr('invitar_persona', {'correo': 'otra@empresa.cl'}, self.empleado)

        self.assertIn('error', r)
        self.assertFalse(Invitation.objects.exists())

    def test_no_invita_a_quien_ya_esta(self):
        r = self.correr('invitar_persona', {'correo': self.empleado.email}, self.duena)

        self.assertIn('error', r)
        self.assertFalse(Invitation.objects.exists())

    def test_no_invita_dos_veces_al_mismo(self):
        self.correr('invitar_persona', {'correo': 'nueva@empresa.cl'}, self.duena)
        r = self.correr('invitar_persona', {'correo': 'nueva@empresa.cl'}, self.duena)

        self.assertIn('error', r)
        self.assertEqual(Invitation.objects.filter(organization=self.org).count(), 1)

    def test_un_correo_que_no_es_correo_se_rechaza(self):
        r = self.correr('invitar_persona', {'correo': 'juan'}, self.duena)

        self.assertIn('error', r)
        self.assertFalse(Invitation.objects.exists())

    def test_un_rol_inventado_se_rechaza(self):
        r = self.correr('invitar_persona', {'correo': 'x@y.cl', 'rol': 'jefe'}, self.duena)

        self.assertIn('error', r)
        self.assertFalse(Invitation.objects.exists())


class CatalogoDeHerramientasTests(TestCase):
    """Las herramientas de construcción tienen que estar SIEMPRE, con o sin conexiones.

    Una empresa que recién entra no tiene ningún sistema conectado — y es exactamente la
    que más necesita que el chat le arme las carpetas.
    """

    def setUp(self):
        self.duena = User.objects.create_user(
            username='d@afable.test', email='d@afable.test', password='x',
        )
        self.org = Organization.objects.create(owner=self.duena, name='Sin Nada SpA')
        self.org.agregar_miembro(self.duena, ROLE_ADMIN)

    def test_estan_disponibles_sin_ninguna_conexion(self):
        from services.agent_tools import tools_for_anthropic

        nombres = {t['name'] for t in tools_for_anthropic(self.org)}
        self.assertIn('armar_estructura_inicial', nombres)
        self.assertIn('crear_carpeta', nombres)
        self.assertIn('invitar_persona', nombres)

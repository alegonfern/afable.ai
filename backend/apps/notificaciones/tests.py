"""Pruebas de la campana.

Lo que cubren, en orden de importancia: que una notificación sea **de una persona** y
nadie pueda leer ni tocar las de otro, que **a nadie se le avise de lo que hizo él mismo**
—que es lo que convierte la campana en ruido— y que avisar nunca voltee la acción que lo
provocó.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.notificaciones.avisos import avisar, avisar_del_mensaje
from apps.notificaciones.models import TIPO_MENSAJE, Notificacion
from apps.organizations.models import Organization
from apps.sesiones.models import Sesion, SesionMiembro
from apps.workspaces.models import ROLE_ADMIN, Workspace

User = get_user_model()
URL = '/api/v1/notificaciones/'


class BaseNotis(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.ana = User.objects.create_user(
            username='ana@afable.test', email='ana@afable.test', password='afable123',
        )
        self.beto = User.objects.create_user(
            username='beto@afable.test', email='beto@afable.test', password='afable123',
        )
        self.org = Organization.objects.create(owner=self.ana, name='Cocinas SpA')
        self.ws = Workspace.objects.create(organization=self.org, name='General')
        self.org.agregar_miembro(self.ana, ROLE_ADMIN)
        self.org.agregar_miembro(self.beto, ROLE_ADMIN)
        self.sesion = Sesion.objects.create(
            workspace=self.ws, name='Cliente Rever', slug='cliente-rever',
        )
        SesionMiembro.objects.create(sesion=self.sesion, user=self.ana)
        SesionMiembro.objects.create(sesion=self.sesion, user=self.beto)


class ANadieSeLeAvisaDeLoSuyoTests(BaseNotis):
    """La regla que decide si la campana se mira o se ignora."""

    def test_quien_escribe_no_se_notifica_a_si_mismo(self):
        class HiloFalso:
            sesion = None
        hilo = HiloFalso()
        hilo.sesion = self.sesion

        creadas = avisar_del_mensaje(hilo, self.ana, 'Mandé la propuesta')
        self.assertEqual(creadas, 1)
        self.assertFalse(Notificacion.objects.filter(user=self.ana).exists())
        self.assertTrue(Notificacion.objects.filter(user=self.beto).exists())

    def test_un_hilo_personal_no_avisa_a_nadie(self):
        """Sin Sesión no hay equipo a quien avisar: sería una campana sonando sola."""
        class HiloFalso:
            sesion = None

        self.assertEqual(avisar_del_mensaje(HiloFalso(), self.ana, 'nota mía'), 0)
        self.assertEqual(Notificacion.objects.count(), 0)

    def test_el_destinatario_repetido_recibe_una_sola(self):
        creadas = avisar(
            [self.beto, self.beto], tipo=TIPO_MENSAJE, titulo='Algo pasó',
        )
        self.assertEqual(creadas, 1)


class CadaUnoVeLasSuyasTests(BaseNotis):

    def test_solo_llegan_las_propias(self):
        avisar([self.ana], tipo=TIPO_MENSAJE, titulo='Para Ana')
        avisar([self.beto], tipo=TIPO_MENSAJE, titulo='Para Beto')

        self.client.force_authenticate(self.ana)
        r = self.client.get(URL)
        self.assertEqual(r.status_code, 200)
        titulos = [n['titulo'] for n in r.data['notificaciones']]
        self.assertEqual(titulos, ['Para Ana'])
        self.assertEqual(r.data['sin_leer'], 1)

    def test_no_se_puede_marcar_leida_la_de_otro(self):
        avisar([self.beto], tipo=TIPO_MENSAJE, titulo='Para Beto')
        ajena = Notificacion.objects.get(user=self.beto)

        self.client.force_authenticate(self.ana)
        r = self.client.post(f'{URL}{ajena.pk}/leida/')
        self.assertEqual(r.status_code, 404)
        ajena.refresh_from_db()
        self.assertFalse(ajena.leida)

    def test_marcar_todas_no_toca_las_de_otro(self):
        avisar([self.ana], tipo=TIPO_MENSAJE, titulo='Para Ana')
        avisar([self.beto], tipo=TIPO_MENSAJE, titulo='Para Beto')

        self.client.force_authenticate(self.ana)
        self.client.post(URL)
        self.assertFalse(Notificacion.objects.get(user=self.beto).leida)
        self.assertTrue(Notificacion.objects.get(user=self.ana).leida)

    def test_el_contador_cuenta_todas_las_sin_leer_no_solo_las_que_se_muestran(self):
        """Un «3» que en realidad son 40 miente, y quien confía en él se pierde cosas."""
        from apps.notificaciones.views import CUANTAS

        avisar([self.ana] * 1, tipo=TIPO_MENSAJE, titulo='x')
        Notificacion.objects.bulk_create([
            Notificacion(user=self.ana, tipo=TIPO_MENSAJE, titulo=f'n{i}')
            for i in range(CUANTAS + 5)
        ])

        self.client.force_authenticate(self.ana)
        r = self.client.get(URL)
        self.assertEqual(len(r.data['notificaciones']), CUANTAS)
        self.assertEqual(r.data['sin_leer'], CUANTAS + 6)


class AvisarNoPuedeVoltearLaAccionTests(BaseNotis):
    """⚠️ Que se pierda un aviso es molesto; que no se pueda mandar un mensaje porque
    falló el aviso es un error que la persona no entiende y no puede sortear."""

    def test_si_falla_guardar_el_aviso_no_explota(self):
        import unittest.mock as mock

        with mock.patch(
            'apps.notificaciones.models.Notificacion.objects.bulk_create',
            side_effect=Exception('base caída'),
        ):
            self.assertEqual(
                avisar([self.beto], tipo=TIPO_MENSAJE, titulo='Algo'), 0,
            )

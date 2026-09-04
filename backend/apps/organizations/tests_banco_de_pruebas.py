"""El banco de pruebas, y sobre todo quién no entra.

Esta pantalla borra carpetas de un botón, así que la mitad de estas pruebas son sobre el
portero: que una cuenta que no está en la lista no pueda tocar nada, ni siquiera mirar.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.archivos.models import Carpeta
from apps.workspaces.models import ROLE_ADMIN

from .models import CompanyDocument, Organization

User = get_user_model()

URL = '/api/v1/organizations/banco-de-pruebas/'
FUNDADOR = 'fundador@afable.test'


@override_settings(CUENTAS_DE_PRUEBA=[FUNDADOR])
class BancoDePruebasTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.fundador = User.objects.create_user(
            username=FUNDADOR, email=FUNDADOR, password='x',
        )
        self.org = Organization.objects.create(owner=self.fundador, name='Cocinas SpA')
        self.org.agregar_miembro(self.fundador, ROLE_ADMIN)
        self.client.force_authenticate(self.fundador)

    def hacer(self, accion, **extra):
        return self.client.post(
            URL, {'workspace': self.org.slug, 'accion': accion, **extra}, format='json',
        )

    # ── el portero ───────────────────────────────────────────────────────────

    def test_una_cuenta_fuera_de_la_lista_no_entra(self):
        otro = User.objects.create_user(username='o@x.test', email='o@x.test', password='x')
        self.org.agregar_miembro(otro, ROLE_ADMIN)
        self.client.force_authenticate(otro)

        r = self.client.get(URL, {'workspace': self.org.slug})
        self.assertEqual(r.status_code, 403)

    def test_ni_siquiera_siendo_administrador_de_la_empresa(self):
        """Ser dueño de la empresa no alcanza: la lista es aparte y es a mano."""
        otro = User.objects.create_user(username='o2@x.test', email='o2@x.test', password='x')
        suya = Organization.objects.create(owner=otro, name='Otra SpA')
        suya.agregar_miembro(otro, ROLE_ADMIN)
        self.client.force_authenticate(otro)

        r = self.client.post(
            URL, {'workspace': suya.slug, 'accion': 'vaciar_estructura'}, format='json',
        )
        self.assertEqual(r.status_code, 403)

    @override_settings(CUENTAS_DE_PRUEBA=[])
    def test_con_la_lista_vacia_no_entra_nadie(self):
        """Es como viene en producción."""
        r = self.client.get(URL, {'workspace': self.org.slug})
        self.assertEqual(r.status_code, 403)

    def test_hay_que_estar_autenticado(self):
        self.client.force_authenticate(None)
        r = self.client.get(URL, {'workspace': self.org.slug})
        self.assertIn(r.status_code, (401, 403))

    # ── mirar ────────────────────────────────────────────────────────────────

    def test_el_estado_dice_que_hay(self):
        r = self.client.get(URL, {'workspace': self.org.slug})

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['estado']['empresa'], 'Cocinas SpA')
        self.assertEqual(r.data['estado']['documentos'], 0)
        self.assertTrue(r.data['acciones'])

    def test_el_estado_incluye_lo_que_veria_en_el_chat(self):
        """Comprobar que las recomendaciones reaccionan sin abrir la otra pantalla."""
        r = self.client.get(URL, {'workspace': self.org.slug})
        self.assertIn('recomendaciones', r.data['estado'])

    # ── las acciones ─────────────────────────────────────────────────────────

    def test_cargar_y_quitar_una_demo(self):
        r = self.hacer('cargar_demo', tipo='constructora')
        self.assertEqual(r.status_code, 200)
        self.assertGreater(r.data['estado']['documentos_de_ejemplo'], 0)

        r = self.hacer('quitar_demo')
        self.assertEqual(r.data['estado']['documentos_de_ejemplo'], 0)

    def test_armar_y_vaciar_la_estructura(self):
        r = self.hacer('armar_estructura', rubro='construccion')
        self.assertGreater(r.data['estado']['carpetas'], 0)
        self.assertTrue(Carpeta.objects.filter(organization=self.org, name='Obras').exists())

        r = self.hacer('vaciar_estructura')
        self.assertEqual(r.data['estado']['carpetas'], 0)

    def test_vaciar_no_toca_las_carpetas_personales(self):
        """Lo de cada uno es de cada uno, incluso en una pantalla de pruebas."""
        from services.estructura_inicial import carpeta_personal

        self.hacer('armar_estructura')
        mia = carpeta_personal(self.org, self.fundador)
        CompanyDocument.objects.create(
            organization=self.org, title='Lo mío', file='m.pdf', carpeta=mia,
        )

        r = self.hacer('vaciar_estructura')

        self.assertEqual(r.data['estado']['carpetas'], 0)
        self.assertEqual(r.data['estado']['carpetas_personales'], 1)
        self.assertTrue(Carpeta.objects.filter(pk=mia.pk).exists())

    def test_reiniciar_el_onboarding(self):
        self.org.onboarding_oculto = True
        self.org.save(update_fields=['onboarding_oculto'])

        self.hacer('reiniciar_onboarding')

        self.org.refresh_from_db()
        self.assertFalse(self.org.onboarding_oculto)

    def test_una_accion_que_no_existe_se_rechaza(self):
        r = self.hacer('borrar_todo')
        self.assertEqual(r.status_code, 400)

    def test_cada_accion_usa_el_camino_real(self):
        """Cargar la demo por acá deja documentos indexables, igual que el camino normal."""
        self.hacer('cargar_demo', tipo='consultora')

        docs = CompanyDocument.objects.filter(organization=self.org, source='ejemplo')
        self.assertTrue(all(d.extracted_text.strip() for d in docs))
        self.assertTrue(all(d.carpeta_id for d in docs))

"""La estructura inicial de carpetas y el circuito de publicación.

Lo que se prueba acá no es que se creen carpetas —eso es trivial— sino que los permisos
que salen de ellas sean los que se prometieron: que `root` la lea todo el equipo pero solo
la editen los administradores, que Remuneraciones no la vea un miembro cualquiera, y que
la carpeta de una persona no la vea otra. Todo eso se consigue con el motor de permisos que
ya existía, sin tocarlo, y estas pruebas son las que sostienen esa afirmación.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.archivos.models import (
    NIVEL_EDICION,
    NIVEL_LECTURA,
    PUBLICACION_APROBADA,
    PUBLICACION_PENDIENTE,
    PUBLICACION_RECHAZADA,
    Carpeta,
    SolicitudDePublicacion,
)
from apps.archivos.permisos import nivel_sobre_carpeta
from apps.organizations.models import CompanyDocument, Organization
from apps.workspaces.models import ROLE_ADMIN, ROLE_MEMBER, Membership
from services.estructura_inicial import (
    BASE,
    POR_RUBRO,
    carpeta_personal,
    crear_estructura,
)

User = get_user_model()


class EstructuraInicialTests(TestCase):
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

    # ── root ──────────────────────────────────────────────────────────────────

    def test_root_se_llama_como_la_empresa(self):
        """«root» es vocabulario de sistemas: en pantalla va el nombre de la empresa."""
        root = crear_estructura(self.org, 'servicios', self.duena)
        self.assertEqual(root.name, 'Cocinas SpA')
        self.assertIsNone(root.parent)

    def test_todo_el_equipo_lee_root_pero_solo_el_admin_edita(self):
        root = crear_estructura(self.org, 'general', self.duena)

        self.assertEqual(nivel_sobre_carpeta(self.empleado, root, self.m_empleado), NIVEL_LECTURA)
        self.assertEqual(nivel_sobre_carpeta(self.duena, root, self.m_duena), NIVEL_EDICION)

    def test_lo_de_dirección_no_lo_ve_un_miembro(self):
        """Remuneraciones está dentro de root, pero sin el permiso de brocha gorda."""
        crear_estructura(self.org, 'general', self.duena)
        remuneraciones = Carpeta.objects.get(organization=self.org, name='Remuneraciones')

        self.assertIsNone(nivel_sobre_carpeta(self.empleado, remuneraciones, self.m_empleado))
        self.assertEqual(
            nivel_sobre_carpeta(self.duena, remuneraciones, self.m_duena), NIVEL_EDICION,
        )

    def test_las_subcarpetas_heredan_la_lectura_de_root(self):
        """La restricción más cercana manda, y la más cercana es la de root."""
        crear_estructura(self.org, 'general', self.duena)
        conciliacion = Carpeta.objects.get(organization=self.org, name='Conciliación')

        self.assertEqual(
            nivel_sobre_carpeta(self.empleado, conciliacion, self.m_empleado), NIVEL_LECTURA,
        )

    # ── el rubro ──────────────────────────────────────────────────────────────

    def test_el_rubro_cambia_el_arbol(self):
        """Es la diferencia entre criterio y plantilla: una constructora no es una consultora."""
        crear_estructura(self.org, 'construccion', self.duena)
        nombres = set(Carpeta.objects.filter(organization=self.org).values_list('name', flat=True))

        self.assertIn('Obras', nombres)
        self.assertIn('Estados de pago', nombres)
        self.assertNotIn('Propuestas', nombres)   # eso es de servicios

    def test_un_rubro_desconocido_no_deja_a_la_empresa_sin_carpetas(self):
        crear_estructura(self.org, 'lo-que-sea', self.duena)
        nombres = set(Carpeta.objects.filter(organization=self.org).values_list('name', flat=True))

        for nombre, _hijas in BASE:
            self.assertIn(nombre, nombres)
        for nombre, _hijas in POR_RUBRO['general']:
            self.assertIn(nombre, nombres)

    def test_correrlo_dos_veces_no_duplica_nada(self):
        """El onboarding se puede reintentar: media estructura repetida sería peor que nada."""
        crear_estructura(self.org, 'comercio', self.duena)
        cuantas = Carpeta.objects.filter(organization=self.org).count()

        crear_estructura(self.org, 'comercio', self.duena)
        self.assertEqual(Carpeta.objects.filter(organization=self.org).count(), cuantas)

    # ── la carpeta de cada persona ────────────────────────────────────────────

    def test_la_carpeta_personal_no_la_ve_nadie_mas(self):
        mia = carpeta_personal(self.org, self.empleado)

        self.assertEqual(nivel_sobre_carpeta(self.empleado, mia, self.m_empleado), NIVEL_EDICION)
        # Un compañero no la ve: `None` es "ni sabe que existe".
        otra = User.objects.create_user(username='otra@x.test', email='otra@x.test', password='x')
        self.org.agregar_miembro(otra, ROLE_MEMBER)
        m_otra = Membership.objects.get(organization=self.org, user=otra)
        self.assertIsNone(nivel_sobre_carpeta(otra, mia, m_otra))

    def test_el_administrador_si_la_ve(self):
        """No puede administrar lo que no ve. Es la regla del motor, y se conserva."""
        mia = carpeta_personal(self.org, self.empleado)
        self.assertEqual(nivel_sobre_carpeta(self.duena, mia, self.m_duena), NIVEL_EDICION)

    def test_dos_personas_del_mismo_nombre_no_chocan(self):
        """`una_carpeta_por_nombre_y_lugar` dejaría a la segunda sin carpeta."""
        a = User.objects.create_user(username='a@x.test', email='a@x.test',
                                     password='x', first_name='Ana', last_name='Pérez')
        b = User.objects.create_user(username='b@x.test', email='b@x.test',
                                     password='x', first_name='Ana', last_name='Pérez')
        self.org.agregar_miembro(a, ROLE_MEMBER)
        self.org.agregar_miembro(b, ROLE_MEMBER)

        ca, cb = carpeta_personal(self.org, a), carpeta_personal(self.org, b)
        self.assertNotEqual(ca.pk, cb.pk)
        self.assertNotEqual(ca.name, cb.name)

    def test_pedirla_dos_veces_devuelve_la_misma(self):
        primera = carpeta_personal(self.org, self.empleado)
        self.assertEqual(carpeta_personal(self.org, self.empleado).pk, primera.pk)

    def test_se_encuentra_aunque_la_persona_se_cambie_el_nombre(self):
        """Por eso `personal` es un flag y no una convención de nombre."""
        primera = carpeta_personal(self.org, self.empleado)
        self.empleado.first_name = 'Otro'
        self.empleado.save(update_fields=['first_name'])

        self.assertEqual(carpeta_personal(self.org, self.empleado).pk, primera.pk)


class SolicitudDePublicacionTests(TestCase):
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

        self.root = crear_estructura(self.org, 'general', self.duena)
        self.mia = carpeta_personal(self.org, self.empleado)
        self.contabilidad = Carpeta.objects.get(organization=self.org, name='Contabilidad')
        self.facturacion = Carpeta.objects.get(organization=self.org, name='Facturación')

        self.doc = CompanyDocument.objects.create(
            organization=self.org, title='Cuadro de gastos', file='g.xlsx',
            uploaded_by=self.empleado, carpeta=self.mia,
        )

    def _pedir(self, destino=None):
        return SolicitudDePublicacion.objects.create(
            document=self.doc, solicitada_por=self.empleado,
            destino=destino or self.contabilidad, nota='Los gastos del trimestre.',
        )

    def test_aprobar_mueve_el_documento(self):
        solicitud = self._pedir()
        solicitud.aprobar(self.duena)

        self.doc.refresh_from_db()
        self.assertEqual(self.doc.carpeta_id, self.contabilidad.pk)
        self.assertEqual(solicitud.estado, PUBLICACION_APROBADA)
        self.assertEqual(solicitud.resuelta_por, self.duena)
        self.assertIsNotNone(solicitud.resolved_at)

    def test_quien_aprueba_puede_corregir_el_destino(self):
        """El que sabe dónde va cada cosa lo arregla al aprobar, no dos meses después."""
        solicitud = self._pedir(destino=self.contabilidad)
        solicitud.aprobar(self.duena, destino=self.facturacion)

        self.doc.refresh_from_db()
        self.assertEqual(self.doc.carpeta_id, self.facturacion.pk)
        # Queda el rastro de la corrección: sirve para ver qué carpeta no se encuentra.
        self.assertEqual(solicitud.destino.pk, self.contabilidad.pk)
        self.assertEqual(solicitud.destino_final.pk, self.facturacion.pk)

    def test_publicar_es_mover_no_repartir_permisos(self):
        """Al salir de la carpeta personal deja de aplicarle su restricción."""
        m_otro = Membership.objects.get(organization=self.org, user=self.duena)
        self._pedir().aprobar(self.duena)
        self.doc.refresh_from_db()

        # Ahora cuelga de root, que todo el equipo lee.
        self.assertEqual(
            nivel_sobre_carpeta(self.empleado, self.doc.carpeta,
                                Membership.objects.get(organization=self.org, user=self.empleado)),
            NIVEL_LECTURA,
        )
        self.assertEqual(
            nivel_sobre_carpeta(self.duena, self.doc.carpeta, m_otro), NIVEL_EDICION,
        )

    def test_rechazar_no_mueve_nada(self):
        solicitud = self._pedir()
        solicitud.rechazar(self.duena, respuesta='Ya está en Contabilidad/2026.')

        self.doc.refresh_from_db()
        self.assertEqual(self.doc.carpeta_id, self.mia.pk)
        self.assertEqual(solicitud.estado, PUBLICACION_RECHAZADA)
        self.assertEqual(solicitud.respuesta, 'Ya está en Contabilidad/2026.')

    def test_no_puede_haber_dos_solicitudes_abiertas_del_mismo_documento(self):
        """Quien aprueba vería el mismo archivo dos veces sin saber cuál es la buena."""
        from django.db import IntegrityError, transaction

        self._pedir()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._pedir(destino=self.facturacion)

    def test_despues_de_resolver_se_puede_volver_a_pedir(self):
        """Rechazada una vez, corregida y propuesta de nuevo: el circuito no se cierra."""
        primera = self._pedir()
        primera.rechazar(self.duena, respuesta='Va en Facturación.')

        segunda = self._pedir(destino=self.facturacion)
        self.assertEqual(segunda.estado, PUBLICACION_PENDIENTE)

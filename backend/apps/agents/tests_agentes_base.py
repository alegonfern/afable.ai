"""Que una empresa nueva NUNCA nazca sin agentes.

Los cuatro agentes base vivían en un `manage.py seed_agentes_base` que había que acordarse
de correr, y las empresas creadas después de la última corrida nacían vacías: quien se
registraba abría la galería y no tenía con quién hablar. Es la peor primera pantalla
posible para un producto que se vende como "IA para equipos".
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.agents.agentes_base import AGENTES_BASE
from apps.organizations.models import Organization

User = get_user_model()


class UnaEmpresaNuevaNaceConAgentesTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='rosa@afable.test', email='rosa@afable.test', password='afable123',
            first_name='Rosa',
        )

    def test_al_crear_la_empresa_quedan_los_cuatro(self):
        empresa = Organization.crear_para_dueno(self.user)
        self.assertEqual(empresa.agents.count(), len(AGENTES_BASE))
        self.assertEqual(
            set(empresa.agents.values_list('handle', flat=True)),
            {a['handle'] for a in AGENTES_BASE},
        )

    def test_se_respeta_el_nombre_que_escribio_la_persona(self):
        """Sin esto toda empresa nacía «Empresa de Rosa»: el nombre del equipo, mal puesto."""
        empresa = Organization.crear_para_dueno(self.user, name='Panadería del Sur')
        self.assertEqual(empresa.name, 'Panadería del Sur')

    def test_sin_nombre_se_arma_uno_pero_no_se_bloquea_el_registro(self):
        empresa = Organization.crear_para_dueno(self.user)
        self.assertEqual(empresa.name, 'Empresa de Rosa')

    def test_sembrar_es_idempotente_y_no_pisa_lo_editado(self):
        """Un seed que revienta el trabajo ajeno es peor que no correr."""
        from apps.agents.agentes_base import sembrar_en

        empresa = Organization.crear_para_dueno(self.user)
        agente = empresa.agents.get(handle='afable')
        agente.instructions = 'Lo que escribió el cliente.'
        agente.save()

        self.assertEqual(sembrar_en(empresa), 0)
        agente.refresh_from_db()
        self.assertEqual(agente.instructions, 'Lo que escribió el cliente.')

    def test_si_falla_sembrar_igual_queda_la_empresa(self):
        """⚠️ Sin agentes es molesto y reparable; sin cuenta, la persona no puede ni volver."""
        import unittest.mock as mock

        with mock.patch(
            'apps.agents.models.Agent.objects.get_or_create',
            side_effect=Exception('base caída'),
        ):
            empresa = Organization.crear_para_dueno(self.user)
        self.assertIsNotNone(empresa.pk)
        self.assertEqual(empresa.agents.count(), 0)

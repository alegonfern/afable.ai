"""Conciliar desde el chat (25-10-2026): la herramienta `conciliar_banco` y su tarjeta.

Usa las cartolas de prueba de septiembre y las de octubre con pendientes
(`pruebas/finanzas/cartola_*_octubre_pendientes.csv`): un abono de $4.998.000 que calza con
cuatro facturas, un abono de la Municipalidad con $4.000 de diferencia, un cargo de seguro sin
documento y un traspaso de Santander a BCI.
"""
from apps.workspaces.models import ROLE_MEMBER

from . import conciliacion, herramienta_conciliar as h
from .models import MovimientoBancario
from .tests import _ConCartolas, ejemplo, usuario


class ConciliarDesdeElChatTests(_ConCartolas):

    def setUp(self):
        super().setUp()
        self._cargar()
        conciliacion.cargar_cartola(self.sant, ejemplo('cartola_santander_octubre_pendientes.csv'), 'sant-oct.csv')
        conciliacion.cargar_cartola(self.bci, ejemplo('cartola_bci_octubre_pendientes.csv'), 'bci-oct.csv')

    def _pendiente(self, monto):
        return MovimientoBancario.objects.get(organization=self.org, monto=monto, fecha__month=10)

    def test_pendientes_trae_los_de_octubre_con_sus_candidatos(self):
        r = h.ejecutar(self.org, {'accion': 'pendientes', 'anio': 2026, 'mes': 10}, self.admin)
        por_monto = {m['monto']: m for m in r['pendientes']}
        self.assertIn(4998000, por_monto)
        self.assertGreaterEqual(len(por_monto[4998000]['candidatos']), 2)
        self.assertIn('posible_traspaso_con', por_monto[-2000000])
        self.assertEqual(por_monto[-89990].get('candidatos'), [])

    def test_conciliar_pide_confirmacion_y_despues_deja_la_factura_pagada(self):
        mov = self._pendiente(4998000)
        doc = conciliacion.candidatos(mov)[0][0]
        args = {'accion': 'conciliar', 'movimiento': mov.id, 'documentos': [doc.id]}
        r = h.ejecutar(self.org, args, self.admin)
        self.assertTrue(r['requiere_confirmacion'])
        mov.refresh_from_db()
        self.assertEqual(mov.estado, MovimientoBancario.PENDIENTE)
        r = h.ejecutar(self.org, {**args, 'confirmado': True}, self.admin)
        mov.refresh_from_db()
        doc.refresh_from_db()
        self.assertEqual(mov.estado, MovimientoBancario.CONCILIADO)
        self.assertTrue(doc.pagado)
        self.assertIn('folio', r['hecho'])

    def test_la_diferencia_de_monto_se_avisa_antes_de_conciliar(self):
        mov = self._pendiente(1900000)
        muni = [d for d, _, nombre in conciliacion.candidatos(mov) if nombre][0]
        r = h.ejecutar(self.org, {'accion': 'conciliar', 'movimiento': mov.id, 'documentos': [muni.id]}, self.admin)
        self.assertIn('diferencia de $4.000', r['se_hara'])

    def test_identificar_un_cargo_sin_documento(self):
        mov = self._pendiente(-89990)
        h.ejecutar(self.org, {'accion': 'identificar', 'movimiento': mov.id, 'tipo': 'otro',
                              'nota': 'Seguro del vehículo', 'confirmado': True}, self.admin)
        mov.refresh_from_db()
        self.assertEqual((mov.estado, mov.tipo_sin_documento), (MovimientoBancario.IDENTIFICADO, 'otro'))

    def test_confirmar_el_traspaso_marca_las_dos_puntas(self):
        mov = self._pendiente(-2000000)
        h.ejecutar(self.org, {'accion': 'traspaso', 'movimiento': mov.id, 'confirmado': True}, self.admin)
        self.assertEqual(self._pendiente(2000000).estado, MovimientoBancario.TRASPASO)

    def test_un_miembro_puede_ver_pero_no_conciliar(self):
        miembro = usuario('miembro@afable.test')
        self.org.agregar_miembro(miembro, ROLE_MEMBER)
        self.assertIn('pendientes', h.ejecutar(self.org, {'accion': 'pendientes'}, miembro))
        r = h.ejecutar(self.org, {'accion': 'deshacer', 'movimiento': self._pendiente(-89990).id,
                                  'confirmado': True}, miembro)
        self.assertIn('editor', r['error'])

    def test_desde_el_chat_queda_la_tarjeta(self):
        from services import agent_tools
        artifacts = {}
        agent_tools.execute_tool('conciliar_banco', {'accion': 'pendientes', 'anio': 2026, 'mes': 10},
                                 self.org, [], None, artifacts, usuario=self.admin)
        t = artifacts['acciones'][0]
        self.assertEqual((t['tipo'], t['titulo']), ('lista', 'Por conciliar en octubre'))
        estados = {f['estado'] for f in t['filas']}
        self.assertTrue({'Posible traspaso', 'Sin documento', 'Mismo monto'} <= estados)

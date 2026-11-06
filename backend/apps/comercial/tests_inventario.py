"""El inventario completo (26-10-2026): lo comprometido y lo que viene, entradas y salidas sin
orden, kardex, valorización, rotación, tomas de inventario y carga inicial."""
import io
from datetime import timedelta
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from openpyxl import load_workbook

from . import inventario as inv, operaciones as op
from .models import COMPRA, VENTA, ConfiguracionComercial, ConteoInventario, MovimientoStock, Pedido
from .tests import _Base


class _BaseInventario(_Base):
    def setUp(self):
        super().setUp()
        ConfiguracionComercial.objects.filter(pk=ConfiguracionComercial.de(self.org).pk).update(nivel_inventario='basico')
        self.inv = f'{self.base}/inventario'
        self.client.force_authenticate(self.editor)

    def _entrada(self, cantidad, costo=None, motivo='inicial', producto=None, **extra):
        r = self.client.post(f'{self.inv}/entrada/', {'producto': (producto or self.cemento).id, 'cantidad': cantidad,
                                                      'costo_unitario': costo, 'motivo': motivo, **extra}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        return r

    def _orden(self, tipo, cantidad):
        p = self._cotizacion(tipo=tipo, lineas=[{'producto': self.cemento.id, 'cantidad': cantidad}])
        self.assertEqual(self._accion(p['id'], 'confirmar').status_code, 200)
        return Pedido.objects.get(pk=p['id'])

    def _fila(self, data, producto=None):
        return next(x for x in data['productos'] if x['id'] == (producto or self.cemento).id)


class StockTests(_BaseInventario):
    def test_reservado_por_recibir_disponible_y_proyectado(self):
        self._entrada(20, 4000)
        venta = self._orden(VENTA, 8)
        self._orden(COMPRA, 30)
        op.registrar_entrega(venta, {venta.lineas.first().id: Decimal('3')}, self.editor)
        f = self._fila(self.client.get(f'{self.inv}/stock/').data)
        # 20 en bodega − 3 entregados = 17; faltan entregar 5; vienen 30.
        self.assertEqual((f['fisico'], f['reservado'], f['disponible'], f['por_recibir'], f['proyectado']),
                         ('17', '5', '12', '30', '42'))
        self.assertEqual(f['valor'], 68000)
        self.assertEqual(f['estado'], 'ok')

    def test_estados_y_alertas_del_resumen(self):
        self.cemento.stock_minimo = Decimal('10')
        self.cemento.save()
        self._entrada(4, 4000)
        self._orden(VENTA, 6)  # vendido más de lo que hay
        r = self.client.get(f'{self.inv}/resumen/').data
        self.assertEqual(r['kpis']['comprometido_sin_stock'], 1)
        self.assertEqual(r['alertas'][0]['tipo'], 'comprometido')
        f = self._fila(self.client.get(f'{self.inv}/stock/?estado=bajo_minimo').data)
        self.assertEqual(f['estado'], 'bajo_minimo')
        self.assertEqual(r['por_familia'][0]['familia'], 'Sin familia')

    def test_apagado_responde_vacio_y_no_deja_registrar(self):
        ConfiguracionComercial.objects.filter(organization=self.org).update(nivel_inventario='ninguno')
        self.assertEqual(self.client.get(f'{self.inv}/stock/').data['productos'], [])
        self.assertEqual(self.client.get(f'{self.inv}/resumen/').data['nivel'], 'ninguno')
        r = self.client.post(f'{self.inv}/entrada/', {'producto': self.cemento.id, 'cantidad': 1, 'motivo': 'inicial'},
                             format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('configuración de Inventario', r.data['detail'])

    def test_un_miembro_solo_mira(self):
        self.client.force_authenticate(self.miembro)
        self.assertEqual(self.client.get(f'{self.inv}/stock/').status_code, 200)
        r = self.client.post(f'{self.inv}/entrada/', {'producto': self.cemento.id, 'cantidad': 1, 'motivo': 'inicial'},
                             format='json')
        self.assertEqual(r.status_code, 403)


class EntradasSalidasTests(_BaseInventario):
    def test_entrada_con_costo_entra_al_costo_promedio(self):
        self._entrada(10, 4000)
        self._entrada(10, 6000, motivo='produccion')
        self.assertEqual(op.costo_promedio(self.org, self.cemento), Decimal('5000'))
        m = MovimientoStock.objects.filter(organization=self.org).order_by('id')
        self.assertEqual([x.tipo for x in m], [MovimientoStock.INICIAL, MovimientoStock.ENTRADA])
        self.assertEqual(m.last().motivo, 'produccion')

    def test_salida_con_motivo_y_sin_dejar_negativo(self):
        self._entrada(5, 4000)
        r = self.client.post(f'{self.inv}/salida/', {'producto': self.cemento.id, 'cantidad': 2, 'motivo': 'merma'},
                             format='json')
        self.assertEqual(r.status_code, 201)
        r = self.client.post(f'{self.inv}/salida/', {'producto': self.cemento.id, 'cantidad': 9, 'motivo': 'merma'},
                             format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('hay 3', r.data['detail'])
        r = self.client.post(f'{self.inv}/salida/', {'producto': self.cemento.id, 'cantidad': 1, 'motivo': 'inventado'},
                             format='json')
        self.assertIn('motivo', r.data['detail'])

    def test_servicio_no_lleva_stock(self):
        r = self.client.post(f'{self.inv}/entrada/', {'producto': self.flete.id, 'cantidad': 1, 'motivo': 'inicial'},
                             format='json')
        self.assertIn('almacenables', r.data['detail'])


class KardexTests(_BaseInventario):
    def test_saldos_costo_promedio_movil_y_documento(self):
        hoy = timezone.localdate()
        self._entrada(10, 4000, fecha=(hoy - timedelta(days=5)).isoformat())
        self._entrada(10, 6000, motivo='hallazgo', fecha=(hoy - timedelta(days=3)).isoformat())
        venta = self._orden(VENTA, 4)
        op.registrar_entrega(venta, {}, self.editor)
        k = self.client.get(f'{self.inv}/kardex/{self.cemento.id}/').data
        self.assertEqual([m['saldo'] for m in k['movimientos']], ['10', '20', '16'])
        self.assertEqual(k['movimientos'][1]['valor_saldo'], 100000)  # 20 × 5.000
        self.assertEqual(k['saldo_final'], {'cantidad': '16', 'valor': 80000})
        doc = k['movimientos'][2]['documento']
        self.assertIn(venta.numero, doc['numero'])
        self.assertEqual(doc['enlace'], f'/app/ventas/ordenes/{venta.id}')
        # Desde una fecha: el saldo anterior queda como saldo inicial.
        k = self.client.get(f'{self.inv}/kardex/{self.cemento.id}/?desde={(hoy - timedelta(days=4)).isoformat()}').data
        self.assertEqual(k['saldo_inicial'], {'cantidad': '10', 'valor': 40000})
        self.assertEqual(len(k['movimientos']), 2)
        self.assertTrue(k['serie'])
        movs = self.client.get(f'{self.inv}/movimientos/?motivo=hallazgo').data
        self.assertEqual(len(movs), 1)
        self.assertEqual(movs[0]['motivo_nombre'], 'Sobrante encontrado')

    def test_exportar_kardex_stock_y_valorizacion(self):
        self._entrada(3, 4000)
        for url in (f'{self.inv}/exportar/kardex/{self.cemento.id}/', f'{self.inv}/exportar/stock/',
                    f'{self.inv}/exportar/valorizacion/'):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, url)
            self.assertTrue(r.content.startswith(b'PK'))


class ValorizacionRotacionTests(_BaseInventario):
    def test_valorizacion_a_una_fecha_pasada(self):
        hoy = timezone.localdate()
        self._entrada(10, 4000, fecha=(hoy - timedelta(days=10)).isoformat())
        self._entrada(10, 8000, motivo='produccion', fecha=(hoy - timedelta(days=2)).isoformat())
        antes = self.client.get(f'{self.inv}/valorizacion/?fecha={(hoy - timedelta(days=5)).isoformat()}').data
        self.assertEqual((antes['total'], antes['productos'][0]['cantidad']), (40000, '10'))
        ahora = self.client.get(f'{self.inv}/valorizacion/').data
        self.assertEqual(ahora['total'], 120000)

    def test_rotacion_e_inmovilizados(self):
        self._entrada(30, 4000)
        hace_40 = (timezone.localdate() - timedelta(days=40)).isoformat()
        self._entrada(5, 1000, producto=self._ladrillo(), fecha=hace_40)
        # Lo recién llegado no está inmovilizado aunque todavía no se venda.
        from .models import Producto
        self._entrada(7, 2000, producto=Producto.objects.create(organization=self.org, nombre='Teja', precio_venta=Decimal('900')))
        venta = self._orden(VENTA, 9)
        op.registrar_entrega(venta, {}, self.editor)
        r = self.client.get(f'{self.inv}/rotacion/?dias=30').data
        cemento = next(x for x in r['productos'] if x['id'] == self.cemento.id)
        self.assertEqual((cemento['salidas'], cemento['salidas_diarias'], cemento['dias_inventario']), ('9', '0.3', 70))
        self.assertEqual([x['nombre'] for x in r['inmovilizados']], ['Ladrillo'])

    def _ladrillo(self):
        from .models import Producto
        return Producto.objects.create(organization=self.org, nombre='Ladrillo', precio_venta=Decimal('500'))


class ConteoTests(_BaseInventario):
    def test_toma_de_inventario_completa(self):
        self._entrada(20, 4000)
        r = self.client.post(f'{self.inv}/conteos/', {}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        c = r.data
        self.assertEqual((c['numero'], c['estado']), ('CI-0001', 'contando'))
        linea = next(l for l in c['lineas'] if l['producto_id'] == self.cemento.id)
        self.assertEqual(linea['sistema'], '20')
        # Se cuentan 17; mientras tanto se entregan 2 (el stock actual pasa a 18).
        r = self.client.patch(f'{self.inv}/conteos/{c["id"]}/lineas/', {'lineas': [{'id': linea['id'], 'contada': '17'}]},
                              format='json')
        fila = next(l for l in r.data['lineas'] if l['id'] == linea['id'])
        self.assertEqual((fila['diferencia'], fila['valor_diferencia']), ('-3', -12000))
        self.assertEqual(r.data['con_diferencia'], 1)
        venta = self._orden(VENTA, 2)
        op.registrar_entrega(venta, {}, self.editor)
        r = self.client.post(f'{self.inv}/conteos/{c["id"]}/aplicar/')
        self.assertEqual(r.data['estado'], 'aplicado')
        f = self._fila(self.client.get(f'{self.inv}/stock/').data)
        self.assertEqual(f['fisico'], '17')  # lo contado manda
        m = MovimientoStock.objects.get(organization=self.org, tipo=MovimientoStock.CONTEO)
        self.assertEqual((m.cantidad, m.conteo_id), (Decimal('-1'), c['id']))
        # Ya aplicada, no se edita.
        r = self.client.patch(f'{self.inv}/conteos/{c["id"]}/lineas/', {'lineas': [{'id': linea['id'], 'contada': 1}]},
                              format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(len(self.client.get(f'{self.inv}/conteos/').data), 1)

    def test_planilla_de_conteo_ida_y_vuelta(self):
        self._entrada(20, 4000)
        c = self.client.post(f'{self.inv}/conteos/', {'solo_con_stock': True}, format='json').data
        r = self.client.get(f'{self.inv}/conteos/{c["id"]}/planilla/')
        ws = load_workbook(io.BytesIO(r.content)).active
        self.assertEqual([x.value for x in ws[1]], inv.COLUMNAS_CONTEO)
        ws['G2'] = 19
        salida = io.BytesIO()
        ws.parent.save(salida)
        r = self.client.post(f'{self.inv}/conteos/{c["id"]}/planilla/',
                             {'archivo': SimpleUploadedFile('conteo.xlsx', salida.getvalue())})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['lineas'][0]['contada'], '19')
        self.assertEqual(r.data['errores'], [])

    def test_cancelar(self):
        self._entrada(1, 4000)
        c = self.client.post(f'{self.inv}/conteos/', {}, format='json').data
        r = self.client.post(f'{self.inv}/conteos/{c["id"]}/cancelar/')
        self.assertEqual(r.data['estado'], 'cancelado')
        self.assertEqual(ConteoInventario.objects.get(pk=c['id']).estado, 'cancelado')


class CargaInicialTests(_BaseInventario):
    def test_importar_stock_inicial_con_errores_por_fila(self):
        r = self.client.get(f'{self.inv}/plantilla-inicial/')
        self.assertTrue(r.content.startswith(b'PK'))
        csv = ('Código;Nombre;Cantidad;Costo unitario;Bodega\n'
               'CEM;;25;4200;\n'
               ';Producto que no existe;3;100;\n'
               ';Flete;1;10;\n'
               'CEM;;5;;Bodega fantasma\n').encode('utf-8')
        r = self.client.post(f'{self.inv}/importar-inicial/', {'archivo': SimpleUploadedFile('inicial.csv', csv)})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['creados'], 1)
        self.assertEqual([e['fila'] for e in r.data['errores']], [3, 4, 5])
        self.assertIn('no es almacenable', r.data['errores'][1]['error'])
        f = self._fila(self.client.get(f'{self.inv}/stock/').data)
        self.assertEqual((f['fisico'], f['costo_promedio']), ('25', '4200'))

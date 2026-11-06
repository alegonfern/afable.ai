from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.finanzas.models import Contacto, Contraparte, DocumentoTributario
from apps.organizations.models import Organization
from apps.workspaces.models import ROLE_ADMIN, ROLE_EDITOR, ROLE_MEMBER

from . import facturacion, operaciones as op
from .models import (COMPRA, VENTA, Bodega, ConfiguracionComercial, MovimientoStock, Pedido, PedidoFactura,
                     PrecioContacto, Producto, stock)

User = get_user_model()


def usuario(email):
    return User.objects.create_user(username=email, email=email, password='afable123')


class _Base(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = usuario('admin@afable.test')
        self.editor = usuario('editor@afable.test')
        self.miembro = usuario('miembro@afable.test')
        self.ajeno = usuario('ajeno@afable.test')
        self.org = Organization.objects.create(owner=self.admin, name='Ferretería Ejemplo', rut='76.000.000-0')
        self.org.agregar_miembro(self.admin, ROLE_ADMIN)
        self.org.agregar_miembro(self.editor, ROLE_EDITOR)
        self.org.agregar_miembro(self.miembro, ROLE_MEMBER)
        otra = Organization.objects.create(owner=self.ajeno, name='Otra')
        otra.agregar_miembro(self.ajeno, ROLE_ADMIN)
        self.base = f'/api/v1/workspaces/{self.org.slug}/comercial'
        self.cliente = Contacto.objects.create(organization=self.org, rut='77111222-3', razon_social='Constructora Andes',
                                               es_cliente=True, email='compras@andes.test')
        self.proveedor = Contacto.objects.create(organization=self.org, rut='76555444-1', razon_social='Cementos Sur',
                                                 es_proveedor=True)
        self.cemento = Producto.objects.create(organization=self.org, codigo='CEM', nombre='Saco de cemento',
                                               precio_venta=Decimal('6000'), costo=Decimal('4000'))
        self.flete = Producto.objects.create(organization=self.org, nombre='Flete', tipo=Producto.SERVICIO,
                                             precio_venta=Decimal('20000'))
        self.client.force_authenticate(self.editor)

    def _cotizacion(self, tipo=VENTA, contacto=None, lineas=None):
        r = self.client.post(f'{self.base}/pedidos/', {
            'tipo': tipo, 'contacto': (contacto or (self.cliente if tipo == VENTA else self.proveedor)).id,
            'lineas': lineas or [{'producto': self.cemento.id, 'cantidad': 10}, {'producto': self.flete.id, 'cantidad': 1}],
        }, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        return r.data

    def _accion(self, pid, accion):
        return self.client.post(f'{self.base}/pedidos/{pid}/accion/', {'accion': accion}, format='json')

    def _factura(self, libro, contacto, neto, folio='100', tipo='33', fecha=None):
        iva = round(neto * 0.19)
        return DocumentoTributario.objects.create(
            organization=self.org, libro=libro, tipo_documento=tipo, folio=folio, rut=contacto.rut,
            razon_social=contacto.razon_social, fecha=fecha or timezone.localdate(), monto_neto=neto,
            monto_iva=iva, monto_total=neto + iva)


class ContactoUnicoTests(_Base):
    def test_la_contraparte_cuelga_de_la_ficha_unica_con_su_rol(self):
        a = Contraparte.objects.create(organization=self.org, libro='compras', rut='79999888-7', razon_social='Doble SpA')
        b = Contraparte.objects.create(organization=self.org, libro='ventas', rut='79999888-7', razon_social='Doble SpA')
        self.assertEqual(a.contacto_id, b.contacto_id)
        self.assertTrue(a.contacto.es_proveedor)
        b.contacto.refresh_from_db()
        self.assertTrue(b.contacto.es_cliente)

    def test_lista_por_rol_y_crear_valida_el_rut(self):
        r = self.client.get(f'{self.base}/contactos/?rol=cliente')
        self.assertEqual([c['razon_social'] for c in r.data], ['Constructora Andes'])
        r = self.client.post(f'{self.base}/contactos/', {'razon_social': 'Nueva', 'rut': '77.111.222-3'}, format='json')
        self.assertEqual(r.status_code, 400)                          # mismo RUT, con puntos
        r = self.client.post(f'{self.base}/contactos/', {'razon_social': 'Nueva', 'rut': '12.345.678-k',
                                                         'es_proveedor': True}, format='json')
        self.assertEqual(r.data['rut'], '12345678-K')

    def test_el_miembro_ve_pero_no_crea_y_el_ajeno_no_ve(self):
        self.client.force_authenticate(self.miembro)
        self.assertEqual(self.client.get(f'{self.base}/contactos/').status_code, 200)
        self.assertEqual(self.client.post(f'{self.base}/contactos/', {'razon_social': 'X'}, format='json').status_code, 403)
        self.client.force_authenticate(self.ajeno)
        self.assertEqual(self.client.get(f'{self.base}/pedidos/?tipo=venta').status_code, 404)


class PedidosTests(_Base):
    def test_cotizacion_con_iva_y_numeracion(self):
        p = self._cotizacion()
        self.assertEqual(p['numero'], 'OV-0001')
        self.assertEqual(p['etapa'], 'Cotización')
        self.assertEqual(Decimal(p['neto']), Decimal('80000'))           # 10 × 6.000 + 20.000
        self.assertEqual(Decimal(p['iva']), Decimal('15200'))
        self.assertEqual(Decimal(p['total']), Decimal('95200'))
        self.assertEqual(self._cotizacion(tipo=COMPRA)['numero'], 'OC-0001')
        self.assertEqual(self._cotizacion()['numero'], 'OV-0002')

    def test_exento_descuento_y_moneda(self):
        p = self._cotizacion(lineas=[{'descripcion': 'Asesoría', 'cantidad': 2, 'precio_unitario': '10,5',
                                      'descuento_pct': 10, 'exento': True}])
        r = self.client.patch(f'{self.base}/pedidos/{p["id"]}/', {'moneda': 'UF', 'tipo_cambio': '38000'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(Decimal(r.data['exento']), Decimal('18.9'))      # 2 × 10,5 − 10%
        self.assertEqual(Decimal(r.data['iva']), Decimal('0'))
        self.assertEqual(r.data['base_clp'], 718200)                     # 18,9 UF × 38.000

    def test_confirmada_no_cambia_lineas_y_cancelar_tiene_reglas(self):
        p = self._cotizacion()
        self.assertEqual(self._accion(p['id'], 'confirmar').data['etapa'], 'Orden de venta')
        r = self.client.patch(f'{self.base}/pedidos/{p["id"]}/', {'lineas': []}, format='json')
        self.assertEqual(r.status_code, 400)
        self.client.post(f'{self.base}/pedidos/{p["id"]}/entregar/', {}, format='json')
        self.assertEqual(self._accion(p['id'], 'cancelar').status_code, 400)   # ya entregada
        self.assertEqual(self.client.delete(f'{self.base}/pedidos/{p["id"]}/').status_code, 400)

    def test_pdf_y_correo(self):
        p = self._cotizacion()
        r = self.client.get(f'{self.base}/pedidos/{p["id"]}/pdf/')
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertTrue(r.content.startswith(b'%PDF'))
        r = self.client.post(f'{self.base}/pedidos/{p["id"]}/correo/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['etapa'], 'Cotización enviada')
        self.assertEqual(mail.outbox[0].to, ['compras@andes.test'])
        self.assertEqual(mail.outbox[0].attachments[0][0], 'OV-0001.pdf')

    def test_emitir_desde_la_orden_factura_con_el_facturador_simulado(self):
        # Hasta el 25-10-2026 respondía que faltaba el proveedor; ahora emite el simulado
        # (emision.py) y la orden queda facturada.
        from .tests_facturar import configurar_emisor
        configurar_emisor(self.org)
        p = self._cotizacion()
        self._accion(p['id'], 'confirmar')
        r = self._accion(p['id'], 'emitir')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(PedidoFactura.objects.filter(pedido_id=p['id']).count(), 1)


class InventarioTests(_Base):
    def setUp(self):
        super().setUp()
        cfg = ConfiguracionComercial.de(self.org)
        cfg.nivel_inventario = 'completo'
        cfg.save()
        self.principal = Bodega.principal_de(self.org)
        self.sala = Bodega.objects.create(organization=self.org, nombre='Sala de ventas')

    def _hay(self, bodega):
        return stock(self.org, producto=self.cemento, bodega=bodega).get((self.cemento.id, bodega.id), Decimal('0'))

    def test_recibir_compra_y_entregar_venta_mueven_stock(self):
        oc = self._cotizacion(tipo=COMPRA, lineas=[{'producto': self.cemento.id, 'cantidad': 50}])
        self._accion(oc['id'], 'confirmar')
        linea = oc['lineas'][0]['id']
        r = self.client.post(f'{self.base}/pedidos/{oc["id"]}/entregar/', {'cantidades': {linea: 30}}, format='json')
        self.assertEqual(r.data['etapa'], 'Recepción parcial')
        self.assertEqual(self._hay(self.principal), 30)
        ov = self._cotizacion()
        self._accion(ov['id'], 'confirmar')
        r = self.client.post(f'{self.base}/pedidos/{ov["id"]}/entregar/', {}, format='json')   # todo lo pendiente
        self.assertEqual(r.data['etapa'], 'Entregada')
        self.assertEqual(self._hay(self.principal), 20)                   # el flete no lleva stock
        self.assertEqual(r.data['entregas'][0]['numero'], 'GD-0001')

    def test_no_entrega_mas_de_lo_pedido_y_anular_devuelve(self):
        ov = self._cotizacion()
        self._accion(ov['id'], 'confirmar')
        linea = ov['lineas'][0]['id']
        r = self.client.post(f'{self.base}/pedidos/{ov["id"]}/entregar/', {'cantidades': {linea: 11}}, format='json')
        self.assertEqual(r.status_code, 400)
        r = self.client.post(f'{self.base}/pedidos/{ov["id"]}/entregar/', {'cantidades': {linea: 4}}, format='json')
        self.assertEqual(self._hay(self.principal), -4)
        entrega = r.data['entregas'][0]['id']
        r = self.client.post(f'{self.base}/entregas/{entrega}/anular/', {}, format='json')
        self.assertEqual(self._hay(self.principal), 0)
        self.assertEqual(r.data['lineas'][0]['cantidad_entregada'], '0')

    def test_ajuste_y_traspaso(self):
        self.client.post(f'{self.base}/stock/ajuste/', {'producto': self.cemento.id, 'cantidad': 40}, format='json')
        self.assertEqual(self._hay(self.principal), 40)
        r = self.client.post(f'{self.base}/stock/traspaso/', {'producto': self.cemento.id, 'origen': self.principal.id,
                                                               'destino': self.sala.id, 'cantidad': 50}, format='json')
        self.assertEqual(r.status_code, 400)                              # no hay tanto
        self.client.post(f'{self.base}/stock/traspaso/', {'producto': self.cemento.id, 'origen': self.principal.id,
                                                           'destino': self.sala.id, 'cantidad': 15}, format='json')
        self.assertEqual((self._hay(self.principal), self._hay(self.sala)), (25, 15))
        r = self.client.get(f'{self.base}/stock/')
        fila = next(p for p in r.data['productos'] if p['id'] == self.cemento.id)
        self.assertEqual(fila['stock'], '40')

    def test_sin_inventario_no_mueve_stock(self):
        cfg = ConfiguracionComercial.de(self.org)
        cfg.nivel_inventario = 'ninguno'
        cfg.save()
        ov = self._cotizacion()
        self._accion(ov['id'], 'confirmar')
        self.client.post(f'{self.base}/pedidos/{ov["id"]}/entregar/', {}, format='json')
        self.assertFalse(MovimientoStock.objects.exists())


class FacturacionTests(_Base):
    def test_vincular_y_por_facturar(self):
        ov = self._cotizacion()
        self._accion(ov['id'], 'confirmar')
        r = self.client.get(f'{self.base}/por-facturar/?tipo=venta')
        self.assertEqual(r.data['pedidos'][0]['por_facturar_clp'], 80000)
        doc = self._factura('ventas', self.cliente, 50000)
        candidatos = self.client.get(f'{self.base}/pedidos/{ov["id"]}/facturas/').data
        self.assertEqual(candidatos[0]['documento'], doc.id)
        r = self.client.post(f'{self.base}/pedidos/{ov["id"]}/facturas/', {'documento': doc.id}, format='json')
        self.assertEqual((r.data['facturado_clp'], r.data['por_facturar_clp'], r.data['factura']), (50000, 30000, 'parcial'))
        doc2 = self._factura('ventas', self.cliente, 30000, folio='101')
        r = self.client.post(f'{self.base}/pedidos/{ov["id"]}/facturas/', {'documento': doc2.id}, format='json')
        self.assertEqual(r.data['factura'], 'completa')
        self.assertEqual(self.client.get(f'{self.base}/por-facturar/?tipo=venta').data['pedidos'], [])

    def test_politica_lo_entregado(self):
        cfg = ConfiguracionComercial.de(self.org)
        cfg.facturar_ventas = 'entregado'
        cfg.save()
        ov = self._cotizacion(lineas=[{'producto': self.cemento.id, 'cantidad': 10}])
        self._accion(ov['id'], 'confirmar')
        self.assertEqual(self.client.get(f'{self.base}/por-facturar/?tipo=venta').data['pedidos'], [])
        self.client.post(f'{self.base}/pedidos/{ov["id"]}/entregar/', {'cantidades': {ov['lineas'][0]['id']: 4}}, format='json')
        self.assertEqual(self.client.get(f'{self.base}/por-facturar/?tipo=venta').data['pedidos'][0]['por_facturar_clp'], 24000)

    def test_vinculo_automatico_al_importar(self):
        from apps.finanzas.models import Carga
        from apps.finanzas.senales import carga_importada
        ov = self._cotizacion()
        self._accion(ov['id'], 'confirmar')
        doc = self._factura('ventas', self.cliente, 80500)                 # dentro del 2% de tolerancia
        otro = self._factura('ventas', self.cliente, 999999, folio='102')  # no cuadra con nada
        carga_importada.send(sender=Carga, carga=mock.Mock(id=1), documentos=[doc, otro])
        self.assertEqual(list(PedidoFactura.objects.values_list('documento_id', 'origen')), [(doc.id, 'auto')])

    def test_compra_facturada_de_mas_se_avisa(self):
        oc = self._cotizacion(tipo=COMPRA, lineas=[{'producto': self.cemento.id, 'cantidad': 10}])   # 40.000
        self._accion(oc['id'], 'confirmar')
        self.client.post(f'{self.base}/pedidos/{oc["id"]}/entregar/', {'cantidades': {oc['lineas'][0]['id']: 5}}, format='json')
        doc = self._factura('compras', self.proveedor, 40000)
        r = self.client.post(f'{self.base}/pedidos/{oc["id"]}/facturas/', {'documento': doc.id, 'monto': 40000}, format='json')
        self.assertTrue(any('más que lo recibido' in d for d in r.data['diferencias']))

    def test_la_nota_de_credito_resta(self):
        ov = self._cotizacion()
        self._accion(ov['id'], 'confirmar')
        f = self._factura('ventas', self.cliente, 80000)
        nc = self._factura('ventas', self.cliente, 10000, folio='5', tipo='61')
        self.client.post(f'{self.base}/pedidos/{ov["id"]}/facturas/', {'documento': f.id}, format='json')
        r = self.client.post(f'{self.base}/pedidos/{ov["id"]}/facturas/', {'documento': nc.id}, format='json')
        self.assertEqual(r.data['facturado_clp'], 70000)


class AutomatizacionesComercialesTests(_Base):
    def test_estan_en_el_catalogo_de_su_modulo(self):
        from apps.finanzas import automatizaciones as a
        self.assertIn('cotizaciones_sin_respuesta', a.POR_CLAVE)
        r = self.client.get(f'/api/v1/workspaces/{self.org.slug}/finanzas/automatizaciones/?modulo=compras')
        self.assertEqual({x['clave'] for x in r.data}, {'oc_atrasadas', 'facturas_compra_con_diferencia'})
        # Las de stock son del módulo Inventario (26-10-2026).
        r = self.client.get(f'/api/v1/workspaces/{self.org.slug}/finanzas/automatizaciones/?modulo=inventario')
        self.assertEqual({x['clave'] for x in r.data}, {'stock_bajo', 'reponer_stock'})

    def test_cotizaciones_sin_respuesta(self):
        from . import automatizaciones as a
        p = Pedido.objects.get(pk=self._cotizacion()['id'])
        op.marcar_enviado(p)
        hoy = timezone.localdate()
        self.assertIsNone(a._cotizaciones_sin_respuesta(self.org, hoy, False))
        Pedido.objects.filter(pk=p.pk).update(fecha=hoy - timedelta(days=10))
        r = a._cotizaciones_sin_respuesta(self.org, hoy, False)
        self.assertIn('OV-0001', r[2])

    def test_stock_bajo_solo_con_inventario(self):
        from . import automatizaciones as a
        self.cemento.stock_minimo = Decimal('5')
        self.cemento.save()
        hoy = timezone.localdate()
        self.assertIsNone(a._stock_bajo(self.org, hoy, False))
        cfg = ConfiguracionComercial.de(self.org)
        cfg.nivel_inventario = 'basico'
        cfg.save()
        self.assertIn('Saco de cemento', a._stock_bajo(self.org, hoy, False)[2])

    def test_oc_atrasada(self):
        from . import automatizaciones as a
        oc = self._cotizacion(tipo=COMPRA)
        self._accion(oc['id'], 'confirmar')
        Pedido.objects.filter(pk=oc['id']).update(fecha_compromiso=timezone.localdate() - timedelta(days=2))
        self.assertIn('OC-0001', a._oc_atrasadas(self.org, timezone.localdate(), False)[2])


class HerramientaTests(_Base):
    def test_el_chat_crea_una_cotizacion_y_confirma_con_el_si(self):
        from . import herramienta
        r = herramienta.ejecutar(self.org, {'accion': 'crear_cotizacion', 'tipo': 'venta', 'contacto': 'andes',
                                            'lineas': [{'producto': 'cemento', 'cantidad': 3}]}, self.editor)
        self.assertEqual(r['creada'], 'OV-0001')
        self.assertEqual(Decimal(r['neto']), Decimal('18000'))
        r = herramienta.ejecutar(self.org, {'accion': 'confirmar', 'numero': 'ov-0001'}, self.editor)
        self.assertTrue(r['requiere_confirmacion'])
        self.assertEqual(Pedido.objects.get().estado, Pedido.BORRADOR)            # sin el sí, nada cambia
        r = herramienta.ejecutar(self.org, {'accion': 'confirmar', 'numero': 'OV-0001', 'confirmado': True}, self.editor)
        self.assertEqual(r['etapa'], 'Orden de venta')

    def test_el_miembro_no_escribe_desde_el_chat(self):
        from . import herramienta
        r = herramienta.ejecutar(self.org, {'accion': 'crear_contacto', 'contacto': 'X'}, self.miembro)
        self.assertIn('editor', r['error'])
        self.assertIn('cantidad', herramienta.ejecutar(self.org, {'accion': 'pedidos'}, self.miembro))

    def test_contacto_ambiguo_pregunta(self):
        from . import herramienta
        Contacto.objects.create(organization=self.org, rut='1-9', razon_social='Constructora Sur', es_cliente=True)
        r = herramienta.ejecutar(self.org, {'accion': 'crear_cotizacion', 'tipo': 'venta', 'contacto': 'constructora',
                                            'lineas': [{'descripcion': 'x', 'cantidad': 1, 'precio_unitario': 1}]}, self.editor)
        self.assertIn('varios', r['error'])


class TipoCambioTests(_Base):
    def test_trae_y_guarda_el_ultimo_habil(self):
        from . import cambio
        from .models import TipoCambio
        sabado = date(2026, 10, 24)
        respuestas = [mock.Mock(status_code=200, json=lambda: {'serie': []}),                   # sábado
                      mock.Mock(status_code=200, json=lambda: {'serie': [{'valor': 945.12}]})]   # viernes
        for x in respuestas:
            x.raise_for_status = lambda: None
        with mock.patch('apps.comercial.cambio.requests.get', side_effect=respuestas) as get:
            self.assertEqual(cambio.valor('USD', sabado), Decimal('945.12'))
        self.assertEqual(get.call_count, 2)
        self.assertTrue(TipoCambio.objects.filter(moneda='USD', fecha=date(2026, 10, 23)).exists())
        with mock.patch('apps.comercial.cambio.requests.get') as get:
            self.assertEqual(cambio.valor('USD', date(2026, 10, 23)), Decimal('945.12'))
        get.assert_not_called()


# ── 24-10-2026: lo que faltaba para que el módulo haga el trabajo completo ─────

class DuplicarYFiltrosTests(_Base):
    def test_duplicar_copia_lineas_y_queda_en_borrador(self):
        ov = self._cotizacion()
        self._accion(ov['id'], 'confirmar')
        r = self._accion(ov['id'], 'duplicar')
        self.assertEqual(r.status_code, 201)
        self.assertNotEqual(r.data['id'], ov['id'])
        self.assertEqual((r.data['estado'], r.data['numero']), ('borrador', 'OV-0002'))
        self.assertEqual([l['descripcion'] for l in r.data['lineas']], ['Saco de cemento', 'Flete'])
        self.assertEqual(r.data['total'], ov['total'])

    def test_filtrar_por_etapa_y_fecha(self):
        a = self._cotizacion()
        b = self._cotizacion()
        self._accion(b['id'], 'confirmar')
        Pedido.objects.filter(pk=a['id']).update(fecha=date(2026, 1, 15))
        r = self.client.get(f'{self.base}/pedidos/?tipo=venta&etapa=Orden de venta')
        self.assertEqual([x['id'] for x in r.data], [b['id']])
        r = self.client.get(f'{self.base}/pedidos/?tipo=venta&desde=2026-01-01&hasta=2026-01-31')
        self.assertEqual([x['id'] for x in r.data], [a['id']])


class PagosTests(_Base):
    def test_cobrar_marca_pagadas_las_facturas_y_borrar_las_desmarca(self):
        ov = self._cotizacion()                                       # 80.000 + IVA = 95.200
        self._accion(ov['id'], 'confirmar')
        # Un anticipo antes de la factura vale; la factura llega después.
        r = self.client.post(f'{self.base}/pedidos/{ov["id"]}/pagos/', {'monto': 50000, 'medio': 'transferencia'}, format='json')
        self.assertEqual((r.data['pagado_clp'], r.data['por_pagar_clp']), (50000, 45200))
        doc = self._factura('ventas', self.cliente, 80000)
        self.client.post(f'{self.base}/pedidos/{ov["id"]}/facturas/', {'documento': doc.id}, format='json')
        doc.refresh_from_db()
        self.assertFalse(doc.pagado)
        r = self.client.post(f'{self.base}/pedidos/{ov["id"]}/pagos/', {'monto': 50000}, format='json')
        self.assertEqual(r.status_code, 400)                          # más de lo que falta
        r = self.client.post(f'{self.base}/pedidos/{ov["id"]}/pagos/', {'monto': 45200}, format='json')
        doc.refresh_from_db()
        self.assertTrue(doc.pagado)
        pago = r.data['pagos'][-1]['id']
        r = self.client.delete(f'{self.base}/pedidos/{ov["id"]}/pagos/{pago}/')
        self.assertEqual(r.data['pagado_clp'], 50000)
        doc.refresh_from_db()
        self.assertFalse(doc.pagado)

    def test_la_cotizacion_no_se_cobra(self):
        ov = self._cotizacion()
        r = self.client.post(f'{self.base}/pedidos/{ov["id"]}/pagos/', {'monto': 1000}, format='json')
        self.assertEqual(r.status_code, 400)


class DevolucionesTests(_Base):
    def setUp(self):
        super().setUp()
        cfg = ConfiguracionComercial.de(self.org)
        cfg.nivel_inventario = 'basico'
        cfg.save()
        self.bodega = Bodega.principal_de(self.org)

    def _hay(self):
        return stock(self.org, producto=self.cemento).get((self.cemento.id, self.bodega.id), Decimal('0'))

    def test_devolucion_de_cliente_vuelve_a_bodega_y_se_puede_anular(self):
        ov = self._cotizacion()
        self._accion(ov['id'], 'confirmar')
        linea = ov['lineas'][0]['id']
        self.client.post(f'{self.base}/pedidos/{ov["id"]}/entregar/', {'cantidades': {linea: 6}}, format='json')
        self.assertEqual(self._hay(), -6)
        r = self.client.post(f'{self.base}/pedidos/{ov["id"]}/devolver/', {'cantidades': {linea: 7}}, format='json')
        self.assertEqual(r.status_code, 400)                          # no se devuelve más de lo entregado
        r = self.client.post(f'{self.base}/pedidos/{ov["id"]}/devolver/', {'cantidades': {linea: 2}}, format='json')
        self.assertEqual(self._hay(), -4)
        self.assertEqual(r.data['lineas'][0]['cantidad_entregada'], '4')
        dev = next(e for e in r.data['entregas'] if e['tipo'] == 'devolucion')
        self.assertEqual(dev['numero'], 'DV-0001')
        r = self.client.post(f'{self.base}/entregas/{dev["id"]}/anular/', {}, format='json')
        self.assertEqual(r.data['lineas'][0]['cantidad_entregada'], '6')
        self.assertEqual(self._hay(), -6)

    def test_devolucion_al_proveedor_saca_de_bodega(self):
        oc = self._cotizacion(tipo=COMPRA, lineas=[{'producto': self.cemento.id, 'cantidad': 20}])
        self._accion(oc['id'], 'confirmar')
        self.client.post(f'{self.base}/pedidos/{oc["id"]}/entregar/', {}, format='json')
        self.client.post(f'{self.base}/pedidos/{oc["id"]}/devolver/', {'cantidades': {oc['lineas'][0]['id']: 5}}, format='json')
        self.assertEqual(self._hay(), 15)


class PreciosYCostoTests(_Base):
    def test_precio_del_cliente_y_del_proveedor_se_proponen_solos(self):
        self.client.post(f'{self.base}/precios/', {'producto': self.cemento.id, 'contacto': self.cliente.id,
                                                   'tipo': 'venta', 'precio': 5500}, format='json')
        self.client.post(f'{self.base}/precios/', {'producto': self.cemento.id, 'contacto': self.proveedor.id,
                                                   'tipo': 'compra', 'precio': 3800, 'preferido': True}, format='json')
        ov = self._cotizacion(lineas=[{'producto': self.cemento.id, 'cantidad': 1}])
        oc = self._cotizacion(tipo=COMPRA, lineas=[{'producto': self.cemento.id, 'cantidad': 1}])
        self.assertEqual((ov['lineas'][0]['precio_unitario'], oc['lineas'][0]['precio_unitario']), ('5500', '3800'))

    def test_costo_promedio_y_valor_del_inventario(self):
        cfg = ConfiguracionComercial.de(self.org)
        cfg.nivel_inventario = 'basico'
        cfg.save()
        for cantidad, precio in ((10, 4000), (30, 5000)):
            oc = self._cotizacion(tipo=COMPRA, lineas=[{'producto': self.cemento.id, 'cantidad': cantidad, 'precio_unitario': precio}])
            self._accion(oc['id'], 'confirmar')
            self.client.post(f'{self.base}/pedidos/{oc["id"]}/entregar/', {}, format='json')
        self.assertEqual(op.costo_promedio(self.org, self.cemento), Decimal('4750'))      # (40.000 + 150.000) / 40
        r = self.client.get(f'{self.base}/stock/')
        fila = next(p for p in r.data['productos'] if p['id'] == self.cemento.id)
        self.assertEqual((fila['costo_promedio'], fila['valor'], r.data['valor_total']), ('4750', 190000, 190000))


class ReponerTests(_Base):
    def setUp(self):
        super().setUp()
        cfg = ConfiguracionComercial.de(self.org)
        cfg.nivel_inventario = 'basico'
        cfg.save()
        self.cemento.stock_minimo = Decimal('10')
        self.cemento.save()

    def test_arma_la_solicitud_al_proveedor_y_no_la_repite(self):
        from . import automatizaciones as a
        hoy = timezone.localdate()
        r = a._reponer_stock(self.org, hoy, True)                    # Probar ahora: no arma nada
        self.assertIn('Sin proveedor', r[2])
        self.assertFalse(Pedido.objects.filter(tipo=COMPRA).exists())
        PrecioContacto.objects.create(organization=self.org, producto=self.cemento, contacto=self.proveedor,
                                      tipo=COMPRA, precio=Decimal('3900'))
        r = a._reponer_stock(self.org, hoy, False)
        oc = Pedido.objects.get(tipo=COMPRA)
        self.assertEqual((oc.origen, oc.contacto, oc.estado), ('reposicion', self.proveedor, 'borrador'))
        linea = oc.lineas.get()
        self.assertEqual((linea.cantidad, linea.precio_unitario), (Decimal('20'), Decimal('3900')))
        self.assertIn(oc.numero, r[2])
        self.assertIsNone(a._reponer_stock(self.org, hoy, False))   # ya está pedido: no repite
        self.assertEqual(Pedido.objects.filter(tipo=COMPRA).count(), 1)


class RecordarCotizacionesTests(_Base):
    def test_le_escribe_una_vez_al_cliente_con_correo(self):
        from . import automatizaciones as a
        p = Pedido.objects.get(pk=self._cotizacion()['id'])
        op.marcar_enviado(p)
        Pedido.objects.filter(pk=p.pk).update(enviado_en=timezone.now() - timedelta(days=10))
        hoy = timezone.localdate()
        r = a._recordar_cotizaciones(self.org, hoy, True)            # Probar ahora: no escribe
        self.assertEqual(len(mail.outbox), 0)
        self.assertIn('Constructora Andes', r[2])
        a._recordar_cotizaciones(self.org, hoy, False)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['compras@andes.test'])
        self.assertTrue(mail.outbox[0].subject.startswith('Seguimiento'))
        self.assertIsNone(a._recordar_cotizaciones(self.org, hoy, False))   # una sola vez
        self.assertEqual(len(mail.outbox), 1)


class PlanillasYReportesTests(_Base):
    def test_exportar_pedidos_contactos_productos_y_reporte(self):
        self._accion(self._cotizacion()['id'], 'confirmar')
        for ruta in ('pedidos/?tipo=venta', 'contactos/?rol=cliente', 'productos/', 'reporte/?tipo=venta&por=producto'):
            r = self.client.get(f'{self.base}/exportar/{ruta}')
            self.assertEqual(r.status_code, 200, ruta)
            self.assertTrue(r.content[:2] == b'PK', ruta)            # es un .xlsx

    def test_importar_productos_crea_y_actualiza(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        csv = ('Código;Nombre;Tipo;Unidad;Precio de venta;Costo;Stock mínimo;Exento\n'
               'CEM;Saco de cemento;Almacenable;un;6500;4100;5;No\n'
               'ARE;Arena;Almacenable;m3;15000;9000;;No\n'
               ';;;;;;;\n'
               'X;Algo;Mineral;un;1;1;;\n').encode()
        r = self.client.post(f'{self.base}/importar/productos/', {'file': SimpleUploadedFile('p.csv', csv)}, format='multipart')
        self.assertEqual((r.data['creados'], r.data['actualizados']), (1, 1))
        self.assertEqual(r.data['errores'][0]['fila'], 5)
        self.cemento.refresh_from_db()
        self.assertEqual(self.cemento.precio_venta, Decimal('6500'))
        r = self.client.get(f'{self.base}/importar/productos/')
        self.assertEqual(r.content[:2], b'PK')                       # la plantilla

    def test_importar_contactos_y_archivar(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        csv = ('RUT;Razón social;Correo;Cliente;Proveedor\n77111222-3;Constructora Andes SpA;nuevo@andes.test;Sí;No\n'
               '11.111.111-1;Ferretería Norte;;No;Sí\n').encode()
        r = self.client.post(f'{self.base}/importar/contactos/', {'file': SimpleUploadedFile('c.csv', csv)}, format='multipart')
        self.assertEqual((r.data['creados'], r.data['actualizados']), (1, 1))
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.email, 'nuevo@andes.test')
        self.client.patch(f'{self.base}/contactos/{self.cliente.id}/', {'activo': False}, format='json')
        ids = [c['id'] for c in self.client.get(f'{self.base}/contactos/').data]
        self.assertNotIn(self.cliente.id, ids)
        ids = [c['id'] for c in self.client.get(f'{self.base}/contactos/?archivados=solo').data]
        self.assertEqual(ids, [self.cliente.id])

    def test_reporte_de_ventas_con_margen(self):
        ov = self._cotizacion()                                       # 10 cementos a 6.000 (costo 4.000) + flete
        self._accion(ov['id'], 'confirmar')
        r = self.client.get(f'{self.base}/reportes/?tipo=venta&por=producto')
        cemento = next(f for f in r.data['filas'] if f['nombre'] == 'Saco de cemento')
        self.assertEqual((cemento['monto'], cemento['costo'], cemento['margen'], cemento['margen_pct']),
                         (60000, 40000, 20000, 33.3))
        r = self.client.get(f'{self.base}/reportes/?tipo=venta&por=contacto')
        self.assertEqual((r.data['filas'][0]['nombre'], r.data['filas'][0]['pedidos']), ('Constructora Andes', 1))
        self.assertEqual(r.data['total']['monto'], 80000)


class ChatNuevasAccionesTests(_Base):
    def test_duplicar_cobrar_y_reporte_desde_el_chat(self):
        from . import herramienta
        ov = self._cotizacion()
        self._accion(ov['id'], 'confirmar')
        r = herramienta.ejecutar(self.org, {'accion': 'duplicar', 'numero': 'OV-0001'}, self.editor)
        self.assertEqual(r['creada'], 'OV-0002')
        r = herramienta.ejecutar(self.org, {'accion': 'registrar_pago', 'numero': 'OV-0001', 'monto': 50000}, self.editor)
        self.assertTrue(r['requiere_confirmacion'])
        herramienta.ejecutar(self.org, {'accion': 'registrar_pago', 'numero': 'OV-0001', 'monto': 50000,
                                        'confirmado': True}, self.editor)
        r = herramienta.ejecutar(self.org, {'accion': 'pedido', 'numero': 'OV-0001'}, self.editor)
        self.assertEqual((r['pagado_clp'], r['por_pagar_clp']), (50000, 45200))
        r = herramienta.ejecutar(self.org, {'accion': 'reporte', 'tipo': 'venta', 'por': 'contacto'}, self.miembro)
        self.assertEqual(r['total']['monto'], 80000)

    def test_enviar_correo_pide_confirmacion(self):
        from . import herramienta
        ov = self._cotizacion()
        r = herramienta.ejecutar(self.org, {'accion': 'enviar_correo', 'numero': 'OV-0001'}, self.editor)
        self.assertTrue(r['requiere_confirmacion'])
        self.assertEqual(len(mail.outbox), 0)
        herramienta.ejecutar(self.org, {'accion': 'enviar_correo', 'numero': 'OV-0001', 'confirmado': True}, self.editor)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(Pedido.objects.get(pk=ov['id']).estado, 'enviado')

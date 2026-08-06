"""Pruebas de la facturación: quién puede tocarla, y que el dinero no se descuadre.

Ninguna habla con Flow ni con PayPal de verdad: las dos pasarelas se simulan. Lo que se
fija acá es lo que rompería la confianza de un cliente que paga:

- **El que paga es la empresa**, y sólo su administrador puede contratar o dar de baja.
- **No hay dos planes vigentes a la vez**, porque serían dos cobros el mismo mes.
- **Una suscripción sin aprobar no da acceso**: crear la intención no es haber pagado.
- **Un webhook sin verificar no activa nada**, o sería un "actíveme el plan" abierto.
- **No se puede quitar el medio con el que se está pagando**, o el próximo cobro falla.
- **Si la pasarela no confirma la baja, no se marca cancelada**, o el cliente paga por
  algo que ya no tiene.
"""

import json
import unittest.mock as mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.organizations.models import Organization
from apps.workspaces.models import ROLE_ADMIN, ROLE_EDITOR, Workspace

from .models import (
    MONEDA_CLP, MONEDA_USD, PROVEEDOR_FLOW, PROVEEDOR_PAYPAL,
    ClientePasarela, MetodoPago, Payment, Plan, Subscription,
)

User = get_user_model()


def url(slug, resto=''):
    return f'/api/v1/workspaces/{slug}/facturacion/{resto}'


class BaseFacturacion(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username='admin@afable.test', email='admin@afable.test', password='afable123',
        )
        self.editor = User.objects.create_user(
            username='editor@afable.test', email='editor@afable.test', password='afable123',
        )
        self.ajeno = User.objects.create_user(
            username='ajeno@afable.test', email='ajeno@afable.test', password='afable123',
        )
        self.org = Organization.objects.create(owner=self.admin, name='Cocinas SpA')
        self.ws = Workspace.objects.create(name='Cocinas SpA', organization=self.org)
        self.ws.add_member(self.admin, ROLE_ADMIN)
        self.ws.add_member(self.editor, ROLE_EDITOR)

        self.starter = Plan.objects.create(
            id='starter', name='Starter', price_clp=99_000, price_usd=99,
        )
        self.growth = Plan.objects.create(
            id='growth', name='Growth', price_clp=299_000, price_usd=299,
        )
        self.medida = Plan.objects.create(
            id='medida', name='Enterprise', price_clp=0, price_usd=0, es_a_medida=True,
        )

    def como(self, usuario):
        self.client.force_authenticate(usuario)

    def _tarjeta(self, proveedor=PROVEEDOR_FLOW):
        return MetodoPago.objects.create(
            workspace=self.ws, proveedor=proveedor,
            etiqueta='Visa ···· 4242', token_pasarela='cus_1', principal=True,
        )


class QuienPuedeTocarLaFacturacion(BaseFacturacion):

    def test_el_administrador_ve_el_estado(self):
        self.como(self.admin)
        r = self.client.get(url(self.ws.slug))
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.data['suscripcion'])
        ids = [p['id'] for p in r.data['planes']]
        self.assertIn('starter', ids)
        self.assertIn('medida', ids)

    def test_un_editor_no_alcanza(self):
        """Editar archivos no es lo mismo que dar de baja el plan de la empresa."""
        self.como(self.editor)
        self.assertEqual(self.client.get(url(self.ws.slug)).status_code, 403)
        self.assertEqual(
            self.client.post(url(self.ws.slug, 'suscribir/'), {'plan_id': 'starter'}).status_code,
            403,
        )

    def test_para_alguien_de_afuera_el_workspace_no_existe(self):
        """404 y no 403: un 403 confirmaría que el slug es real."""
        self.como(self.ajeno)
        self.assertEqual(self.client.get(url(self.ws.slug)).status_code, 404)

    def test_sin_entrar_el_workspace_tampoco_existe(self):
        """404 también para el anónimo: no es miembro, así que no hay nada que ver."""
        self.assertEqual(self.client.get(url(self.ws.slug)).status_code, 404)


class AltaConFlow(BaseFacturacion):

    @mock.patch('apps.payments.facturacion.FlowClient')
    def test_sin_tarjeta_manda_a_registrarla_y_deja_el_plan_esperando(self, FakeFlow):
        """En Flow no se puede suscribir sin tarjeta: primero el medio, después el plan."""
        FakeFlow.return_value.create_customer.return_value = {'customerId': 'cus_9'}
        FakeFlow.return_value.register_card.return_value = {
            'url': 'https://flow.test/registro', 'token': 'tok_1',
        }

        self.como(self.admin)
        r = self.client.post(url(self.ws.slug, 'suscribir/'), {'plan_id': 'starter'})

        self.assertEqual(r.status_code, 202)
        self.assertTrue(r.data['requiere_tarjeta'])
        self.assertIn('tok_1', r.data['url'])

        sub = Subscription.objects.get(workspace=self.ws)
        self.assertFalse(sub.aprobada)
        self.assertFalse(sub.vigente, 'una intención de pago no puede dar acceso')
        self.assertEqual(sub.moneda, MONEDA_CLP)

    @mock.patch('apps.payments.facturacion.FlowClient')
    def test_con_tarjeta_suscribe_derecho(self, FakeFlow):
        FakeFlow.return_value.subscribe.return_value = {'subscriptionId': 'sub_flow_1'}
        ClientePasarela.objects.create(
            workspace=self.ws, proveedor=PROVEEDOR_FLOW, customer_id='cus_1',
        )
        self._tarjeta()

        self.como(self.admin)
        r = self.client.post(url(self.ws.slug, 'suscribir/'), {'plan_id': 'growth'})

        self.assertEqual(r.status_code, 201)
        sub = Subscription.objects.get(workspace=self.ws)
        self.assertTrue(sub.aprobada)
        self.assertTrue(sub.vigente)
        self.assertEqual(sub.id_externo, 'sub_flow_1')

    @mock.patch('apps.payments.facturacion.FlowClient')
    def test_si_flow_falla_al_cambiar_de_plan_sobrevive_el_que_ya_pagaba(self, FakeFlow):
        """Un problema de la pasarela no puede cortarle el servicio a quien está al día.

        Es el bug que tenía la primera versión: el plan anterior se cancelaba al elegir
        el nuevo, así que un 502 de Flow dejaba a la empresa sin ninguno.
        """
        FakeFlow.return_value.subscribe.side_effect = Exception('Flow caído')
        ClientePasarela.objects.create(
            workspace=self.ws, proveedor=PROVEEDOR_FLOW, customer_id='cus_1',
        )
        self._tarjeta()
        viejo = Subscription.objects.create(
            workspace=self.ws, plan=self.starter, proveedor=PROVEEDOR_FLOW,
            aprobada=True, status=Subscription.ESTADO_ACTIVA, id_externo='sub_viejo',
        )

        self.como(self.admin)
        r = self.client.post(url(self.ws.slug, 'suscribir/'), {'plan_id': 'growth'})

        self.assertEqual(r.status_code, 502)
        viejo.refresh_from_db()
        self.assertTrue(viejo.vigente, 'el plan que se estaba pagando tiene que seguir')

    @mock.patch('apps.payments.facturacion.FlowClient')
    def test_mientras_no_apruebe_sigue_mandando_el_plan_aprobado(self, FakeFlow):
        """Con un cambio a medio terminar, la pantalla debe mostrar el que paga hoy."""
        FakeFlow.return_value.create_customer.return_value = {'customerId': 'cus_9'}
        FakeFlow.return_value.register_card.return_value = {
            'url': 'https://flow.test/registro', 'token': 'tok_1',
        }
        Subscription.objects.create(
            workspace=self.ws, plan=self.starter, proveedor=PROVEEDOR_FLOW,
            aprobada=True, status=Subscription.ESTADO_ACTIVA,
        )

        self.como(self.admin)
        self.client.post(url(self.ws.slug, 'suscribir/'), {'plan_id': 'growth'})
        r = self.client.get(url(self.ws.slug))

        self.assertEqual(r.data['suscripcion']['plan']['id'], 'starter')
        self.assertTrue(r.data['suscripcion']['aprobada'])

    @mock.patch('apps.payments.facturacion.FlowClient')
    def test_cambiar_de_plan_no_deja_dos_vigentes(self, FakeFlow):
        """Dos suscripciones vigentes serían dos cobros el mismo mes."""
        FakeFlow.return_value.subscribe.return_value = {'subscriptionId': 'sub_2'}
        ClientePasarela.objects.create(
            workspace=self.ws, proveedor=PROVEEDOR_FLOW, customer_id='cus_1',
        )
        self._tarjeta()
        self.como(self.admin)

        self.client.post(url(self.ws.slug, 'suscribir/'), {'plan_id': 'starter'})
        self.client.post(url(self.ws.slug, 'suscribir/'), {'plan_id': 'growth'})

        vigentes = Subscription.objects.filter(
            workspace=self.ws, status__in=Subscription.ESTADOS_VIGENTES,
        )
        self.assertEqual(vigentes.count(), 1)
        self.assertEqual(vigentes.first().plan_id, 'growth')

    @mock.patch('apps.payments.facturacion.FlowClient')
    def test_si_flow_falla_no_queda_una_suscripcion_fantasma(self, FakeFlow):
        FakeFlow.return_value.subscribe.side_effect = Exception('Flow caído')
        ClientePasarela.objects.create(
            workspace=self.ws, proveedor=PROVEEDOR_FLOW, customer_id='cus_1',
        )
        self._tarjeta()

        self.como(self.admin)
        r = self.client.post(url(self.ws.slug, 'suscribir/'), {'plan_id': 'starter'})

        self.assertEqual(r.status_code, 502)
        self.assertEqual(Subscription.objects.count(), 0)


class AltaConPayPal(BaseFacturacion):

    @mock.patch('apps.payments.facturacion.PayPalClient')
    def test_devuelve_el_enlace_de_aprobacion_y_cobra_en_dolares(self, FakePayPal):
        cliente = FakePayPal.return_value
        cliente.configurado = True
        cliente.crear_suscripcion.return_value = ('I-SUB1', 'https://paypal.test/aprobar')

        self.como(self.admin)
        r = self.client.post(
            url(self.ws.slug, 'suscribir/'), {'plan_id': 'growth', 'proveedor': 'paypal'},
        )

        self.assertEqual(r.status_code, 202)
        self.assertTrue(r.data['requiere_aprobacion'])
        self.assertEqual(r.data['url'], 'https://paypal.test/aprobar')

        sub = Subscription.objects.get(workspace=self.ws)
        self.assertEqual(sub.moneda, MONEDA_USD)
        self.assertEqual(sub.id_externo, 'I-SUB1')
        self.assertFalse(sub.vigente, 'sin aprobar todavía no hay acceso')

    @mock.patch('apps.payments.facturacion.PayPalClient')
    def test_sin_credenciales_lo_dice_en_vez_de_reventar(self, FakePayPal):
        FakePayPal.return_value.configurado = False
        self.como(self.admin)
        r = self.client.post(
            url(self.ws.slug, 'suscribir/'), {'plan_id': 'growth', 'proveedor': 'paypal'},
        )
        self.assertEqual(r.status_code, 503)
        self.assertEqual(Subscription.objects.count(), 0)


class PlanesQueNoSeCobranSolos(BaseFacturacion):

    def test_enterprise_no_pasa_por_pasarela(self):
        """Cobrar $0 dejaría a la empresa 'suscrita' y sin servicio."""
        self.como(self.admin)
        r = self.client.post(url(self.ws.slug, 'suscribir/'), {'plan_id': 'medida'})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Subscription.objects.count(), 0)

    def test_un_plan_sin_precio_en_dolares_no_se_vende_por_paypal(self):
        sin_usd = Plan.objects.create(id='solo_clp', name='Solo Chile', price_clp=50_000, price_usd=0)
        self.como(self.admin)
        r = self.client.post(
            url(self.ws.slug, 'suscribir/'), {'plan_id': sin_usd.id, 'proveedor': 'paypal'},
        )
        self.assertEqual(r.status_code, 400)

    def test_pasarela_inventada(self):
        self.como(self.admin)
        r = self.client.post(
            url(self.ws.slug, 'suscribir/'), {'plan_id': 'starter', 'proveedor': 'bitcoin'},
        )
        self.assertEqual(r.status_code, 400)


class Baja(BaseFacturacion):

    def _sub(self, proveedor=PROVEEDOR_FLOW, id_externo='sub_1'):
        return Subscription.objects.create(
            workspace=self.ws, plan=self.starter, proveedor=proveedor,
            id_externo=id_externo, aprobada=True, status=Subscription.ESTADO_ACTIVA,
        )

    @mock.patch('apps.payments.facturacion.FlowClient')
    def test_dar_de_baja_avisa_a_flow(self, FakeFlow):
        sub = self._sub()
        self.como(self.admin)
        r = self.client.post(url(self.ws.slug, 'cancelar/'))

        self.assertEqual(r.status_code, 200)
        FakeFlow.return_value.cancel_subscription.assert_called_once_with('sub_1')
        sub.refresh_from_db()
        self.assertEqual(sub.status, Subscription.ESTADO_CANCELADA)

    @mock.patch('apps.payments.facturacion.FlowClient')
    def test_si_la_pasarela_no_confirma_no_se_marca_cancelada(self, FakeFlow):
        """Decir 'cancelada' mientras la pasarela sigue cobrando es cobrarle por nada."""
        FakeFlow.return_value.cancel_subscription.side_effect = Exception('timeout')
        sub = self._sub()

        self.como(self.admin)
        r = self.client.post(url(self.ws.slug, 'cancelar/'))

        self.assertEqual(r.status_code, 502)
        sub.refresh_from_db()
        self.assertEqual(sub.status, Subscription.ESTADO_ACTIVA)

    def test_sin_plan_no_hay_nada_que_dar_de_baja(self):
        self.como(self.admin)
        self.assertEqual(self.client.post(url(self.ws.slug, 'cancelar/')).status_code, 404)


class MediosDePago(BaseFacturacion):

    def test_el_token_de_la_pasarela_no_sale_del_servidor(self):
        self._tarjeta()
        self.como(self.admin)
        r = self.client.get(url(self.ws.slug, 'metodos/'))
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('token_pasarela', r.data[0])
        self.assertEqual(r.data[0]['etiqueta'], 'Visa ···· 4242')

    def test_marcar_principal_deja_uno_solo(self):
        """Con dos principales, contra cuál se cobra queda al azar de la consulta."""
        uno = self._tarjeta()
        otro = MetodoPago.objects.create(
            workspace=self.ws, proveedor=PROVEEDOR_FLOW, etiqueta='Visa ···· 1111',
        )
        self.como(self.admin)
        r = self.client.post(url(self.ws.slug, f'metodos/{otro.id}/principal/'))

        self.assertEqual(r.status_code, 200)
        uno.refresh_from_db(); otro.refresh_from_db()
        self.assertTrue(otro.principal)
        self.assertFalse(uno.principal)

    def test_no_se_puede_quitar_el_medio_con_el_que_se_paga(self):
        tarjeta = self._tarjeta()
        Subscription.objects.create(
            workspace=self.ws, plan=self.starter, proveedor=PROVEEDOR_FLOW,
            aprobada=True, status=Subscription.ESTADO_ACTIVA,
        )
        self.como(self.admin)
        r = self.client.delete(url(self.ws.slug, f'metodos/{tarjeta.id}/'))

        self.assertEqual(r.status_code, 409)
        self.assertTrue(MetodoPago.objects.filter(pk=tarjeta.pk).exists())

    @mock.patch('apps.payments.facturacion.FlowClient')
    def test_al_quitar_el_principal_otro_toma_su_lugar(self, FakeFlow):
        principal = self._tarjeta()
        suplente = MetodoPago.objects.create(
            workspace=self.ws, proveedor=PROVEEDOR_PAYPAL, etiqueta='PayPal · a@b.cl',
        )
        self.como(self.admin)
        r = self.client.delete(url(self.ws.slug, f'metodos/{principal.id}/'))

        self.assertEqual(r.status_code, 204)
        suplente.refresh_from_db()
        self.assertTrue(suplente.principal, 'la empresa no puede quedar sin medio principal')

    def test_un_medio_de_otra_empresa_no_se_toca(self):
        otra_org = Organization.objects.create(owner=self.ajeno, name='Otra')
        otro_ws = Workspace.objects.create(name='Otra', organization=otra_org)
        ajeno = MetodoPago.objects.create(
            workspace=otro_ws, proveedor=PROVEEDOR_FLOW, etiqueta='Visa ···· 9999',
        )
        self.como(self.admin)
        r = self.client.delete(url(self.ws.slug, f'metodos/{ajeno.id}/'))
        self.assertEqual(r.status_code, 404)
        self.assertTrue(MetodoPago.objects.filter(pk=ajeno.pk).exists())

    def test_en_paypal_no_se_agrega_un_medio_por_separado(self):
        self.como(self.admin)
        r = self.client.post(url(self.ws.slug, 'metodos/'), {'proveedor': 'paypal'})
        self.assertEqual(r.status_code, 400)


class RetornoDeFlowConLaTarjeta(BaseFacturacion):
    """Lo que pasa cuando la persona vuelve de escribir su tarjeta en Flow."""

    def setUp(self):
        super().setUp()
        self.cliente = ClientePasarela.objects.create(
            workspace=self.ws, proveedor=PROVEEDOR_FLOW, customer_id='cus_7',
        )

    @mock.patch('apps.payments.views.FlowClient')
    def test_guarda_la_tarjeta_y_completa_el_plan_que_esperaba(self, FakeFlow):
        FakeFlow.return_value.get_register_status.return_value = {
            'customerId': 'cus_7', 'creditCardType': 'Visa', 'last4CardDigits': '4242',
        }
        FakeFlow.return_value.subscribe.return_value = {'subscriptionId': 'sub_ok'}
        pendiente = Subscription.objects.create(
            workspace=self.ws, plan=self.growth, proveedor=PROVEEDOR_FLOW, aprobada=False,
        )

        r = self.client.get('/api/v1/payments/tarjeta/retorno/?token=tok_1')

        self.assertEqual(r.status_code, 302)
        self.assertIn('pago=listo', r.url)
        metodo = MetodoPago.objects.get(workspace=self.ws)
        self.assertEqual(metodo.etiqueta, 'Visa ···· 4242')
        self.assertTrue(metodo.principal)
        pendiente.refresh_from_db()
        self.assertTrue(pendiente.aprobada)
        self.assertEqual(pendiente.id_externo, 'sub_ok')

    @mock.patch('apps.payments.views.FlowClient')
    def test_registrar_de_nuevo_reemplaza_los_cuatro_digitos(self, FakeFlow):
        MetodoPago.objects.create(
            workspace=self.ws, proveedor=PROVEEDOR_FLOW,
            etiqueta='Visa ···· 1111', token_pasarela='cus_7',
        )
        FakeFlow.return_value.get_register_status.return_value = {
            'customerId': 'cus_7', 'creditCardType': 'Mastercard', 'last4CardDigits': '5555',
        }

        self.client.get('/api/v1/payments/tarjeta/retorno/?token=tok_2')

        self.assertEqual(MetodoPago.objects.filter(workspace=self.ws).count(), 1)
        self.assertEqual(
            MetodoPago.objects.get(workspace=self.ws).etiqueta, 'Mastercard ···· 5555',
        )

    @mock.patch('apps.payments.views.FlowClient')
    def test_un_cliente_que_no_es_nuestro_no_crea_nada(self, FakeFlow):
        FakeFlow.return_value.get_register_status.return_value = {'customerId': 'cus_ajeno'}
        r = self.client.get('/api/v1/payments/tarjeta/retorno/?token=tok_3')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(MetodoPago.objects.count(), 0)


class WebhookDePayPal(BaseFacturacion):

    def setUp(self):
        super().setUp()
        self.sub = Subscription.objects.create(
            workspace=self.ws, plan=self.growth, proveedor=PROVEEDOR_PAYPAL,
            moneda=MONEDA_USD, id_externo='I-SUB1', aprobada=False,
        )

    def _mandar(self, cuerpo):
        return self.client.post(
            '/api/v1/payments/webhook/paypal/',
            data=json.dumps(cuerpo), content_type='application/json',
        )

    @mock.patch('apps.payments.views.PayPalClient')
    def test_sin_firma_verificada_no_activa_nada(self, FakePayPal):
        """Si no, cualquiera activa su plan mandando un POST."""
        FakePayPal.return_value.verificar_webhook.return_value = False

        r = self._mandar({'event_type': 'BILLING.SUBSCRIPTION.ACTIVATED',
                          'resource': {'id': 'I-SUB1'}})

        self.assertEqual(r.status_code, 400)
        self.sub.refresh_from_db()
        self.assertFalse(self.sub.aprobada)

    @mock.patch('apps.payments.views.PayPalClient')
    def test_activada_deja_el_plan_vigente_y_guarda_la_cuenta(self, FakePayPal):
        FakePayPal.return_value.verificar_webhook.return_value = True

        r = self._mandar({
            'event_type': 'BILLING.SUBSCRIPTION.ACTIVATED',
            'resource': {'id': 'I-SUB1', 'subscriber': {'email_address': 'pago@empresa.cl'}},
        })

        self.assertEqual(r.status_code, 200)
        self.sub.refresh_from_db()
        self.assertTrue(self.sub.vigente)
        metodo = MetodoPago.objects.get(workspace=self.ws)
        self.assertEqual(metodo.etiqueta, 'PayPal · pago@empresa.cl')

    @mock.patch('apps.payments.views.PayPalClient')
    def test_un_cobro_queda_en_la_cartola_en_dolares(self, FakePayPal):
        FakePayPal.return_value.verificar_webhook.return_value = True

        self._mandar({
            'event_type': 'PAYMENT.SALE.COMPLETED',
            'resource': {'id': 'PAY-1', 'billing_agreement_id': 'I-SUB1',
                         'amount': {'total': '299.00'}},
        })

        pago = Payment.objects.get(workspace=self.ws)
        self.assertEqual(pago.amount, 299)
        self.assertEqual(pago.moneda, MONEDA_USD)
        self.assertEqual(pago.status, 'paid')

    @mock.patch('apps.payments.views.PayPalClient')
    def test_un_cobro_rechazado_suspende(self, FakePayPal):
        FakePayPal.return_value.verificar_webhook.return_value = True
        self.sub.aprobada = True
        self.sub.status = Subscription.ESTADO_ACTIVA
        self.sub.save()

        self._mandar({'event_type': 'BILLING.SUBSCRIPTION.SUSPENDED',
                      'resource': {'id': 'I-SUB1'}})

        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, Subscription.ESTADO_SUSPENDIDA)
        self.assertFalse(self.sub.vigente)

    @mock.patch('apps.payments.views.PayPalClient')
    def test_un_evento_que_no_nos_interesa_se_contesta_igual(self, FakePayPal):
        """Un 4xx hace que PayPal reintente durante días."""
        FakePayPal.return_value.verificar_webhook.return_value = True
        r = self._mandar({'event_type': 'CHECKOUT.ORDER.APPROVED', 'resource': {}})
        self.assertEqual(r.status_code, 200)


class WebhookDeFlow(BaseFacturacion):

    @mock.patch('apps.payments.views.FlowClient')
    def test_un_pago_confirmado_activa_el_plan(self, FakeFlow):
        sub = Subscription.objects.create(
            workspace=self.ws, plan=self.starter, proveedor=PROVEEDOR_FLOW, aprobada=False,
        )
        pago = Payment.objects.create(
            workspace=self.ws, proveedor=PROVEEDOR_FLOW, moneda=MONEDA_CLP,
            commerce_order='AFA-1', amount=99_000, subject='Afable Starter',
        )
        FakeFlow.return_value.get_payment_status.return_value = {
            'status': 2, 'commerceOrder': 'AFA-1',
        }

        r = self.client.post('/api/v1/payments/webhook/confirm/', {'token': 'tok'})

        self.assertEqual(r.status_code, 200)
        pago.refresh_from_db(); sub.refresh_from_db()
        self.assertEqual(pago.status, 'paid')
        self.assertTrue(sub.vigente)

    @mock.patch('apps.payments.views.FlowClient')
    def test_un_pago_de_un_pedido_que_no_existe(self, FakeFlow):
        FakeFlow.return_value.get_payment_status.return_value = {
            'status': 2, 'commerceOrder': 'AFA-INVENTADO',
        }
        r = self.client.post('/api/v1/payments/webhook/confirm/', {'token': 'tok'})
        self.assertEqual(r.status_code, 404)


class CartolaYEstado(BaseFacturacion):

    def test_los_cobros_de_otra_empresa_no_aparecen(self):
        otra_org = Organization.objects.create(owner=self.ajeno, name='Otra')
        otro_ws = Workspace.objects.create(name='Otra', organization=otra_org)
        Payment.objects.create(
            workspace=otro_ws, commerce_order='AFA-AJENO', amount=1, subject='ajeno',
        )
        Payment.objects.create(
            workspace=self.ws, commerce_order='AFA-MIO', amount=99_000, subject='mío',
        )

        self.como(self.admin)
        r = self.client.get(url(self.ws.slug))
        pedidos = [c['commerce_order'] for c in r.data['cobros']]
        self.assertEqual(pedidos, ['AFA-MIO'])

    def test_el_numero_de_pedido_no_dice_velery(self):
        """Ese número queda escrito en la cartola del cliente."""
        self.assertTrue(Payment.generate_commerce_order().startswith('AFA-'))

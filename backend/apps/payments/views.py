"""Lo que llaman las pasarelas, no la app: retornos del navegador y webhooks.

Todo acá es `AllowAny` porque quien golpea estas URLs es Flow, PayPal, o el navegador
de la persona volviendo de pagar — ninguno trae el token de Afable. Por eso **nada de
esto confía en lo que le llega**: el estado se le vuelve a preguntar a la pasarela
(Flow) o se verifica la firma (PayPal). Un webhook que se cree lo que dice el cuerpo es
un botón de "actíveme el plan" abierto a internet.

La facturación que sí usa la app está en `facturacion.py`, colgada del Workspace.
"""

import json
import logging

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from services.flow_client import FlowClient
from services.paypal_client import PayPalClient

from .facturacion import SuscribirView, activar, suscripcion_vigente
from .models import (
    MONEDA_USD, PROVEEDOR_FLOW, PROVEEDOR_PAYPAL,
    ClientePasarela, MetodoPago, Payment, Plan, Subscription,
)
from .serializers import PlanSerializer

logger = logging.getLogger(__name__)

# Flow dice "pagado" con un 2 y "rechazado" con 3 o 4.
FLOW_PAGADO = 2
FLOW_RECHAZADO = (3, 4)


def _pantalla_facturacion(resultado):
    """A dónde vuelve la persona después de pasar por una pasarela.

    Siempre a la pantalla de Facturación de la app, con el resultado en la URL: volver
    a una pantalla de "gracias" suelta deja a alguien mirando un cartel sin saber si su
    plan quedó activo.
    """
    return redirect(f'{settings.FRONTEND_URL}/app/admin/facturacion?pago={resultado}')


class PlansListView(APIView):
    """El catálogo de planes con sus dos precios. Público, para poder mostrarlo sin entrar."""

    permission_classes = [AllowAny]

    def get(self, request):
        planes = Plan.objects.filter(is_active=True)
        return Response(PlanSerializer(planes, many=True).data)


class FlowWebhookView(APIView):
    """Flow avisa que un cobro cambió de estado.

    Se le vuelve a preguntar a Flow por el token en vez de creerle al cuerpo del POST:
    el aviso no viene firmado, así que el cuerpo es apenas una notificación de "andá a
    mirar".
    """

    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get('token')
        if not token:
            return HttpResponse('falta el token', status=400)

        try:
            datos = FlowClient().get_payment_status(token)
        except Exception as e:
            logger.warning('Flow no contestó por el token %s: %s', token, e)
            return HttpResponse('flow no responde', status=502)

        pago = Payment.objects.filter(commerce_order=datos.get('commerceOrder')).first()
        if pago is None:
            return HttpResponse('no encontrado', status=404)

        estado = datos.get('status')
        if estado == FLOW_PAGADO:
            pago.status = 'paid'
            pago.save(update_fields=['status', 'updated_at'])
            sub = suscripcion_vigente(pago.workspace)
            if sub:
                activar(sub)
        elif estado in FLOW_RECHAZADO:
            pago.status = 'rejected'
            pago.save(update_fields=['status', 'updated_at'])

        return HttpResponse('OK')


class PaymentReturnView(APIView):
    """El navegador vuelve de pagar en Flow."""

    permission_classes = [AllowAny]

    def get(self, request):
        token = request.query_params.get('token')
        if not token:
            return _pantalla_facturacion('rechazado')
        try:
            datos = FlowClient().get_payment_status(token)
            if datos.get('status') == FLOW_PAGADO:
                return _pantalla_facturacion('listo')
        except Exception as e:
            logger.warning('Flow no contestó al volver del pago: %s', e)
        return _pantalla_facturacion('rechazado')


class RetornoTarjetaFlowView(APIView):
    """El navegador vuelve de registrar una tarjeta en Flow.

    Acá se completa el alta: se guarda el medio de pago con lo que Flow diga que quedó
    registrado, y si había un plan elegido esperando, se suscribe. La empresa se
    encuentra por el `customerId` que devuelve Flow — no hace falta pasar el Workspace
    por la URL, que además sería un dato que cualquiera podría cambiar a mano.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        token = request.query_params.get('token')
        if not token:
            return _pantalla_facturacion('sin-tarjeta')

        try:
            datos = FlowClient().get_register_status(token)
        except Exception as e:
            logger.warning('Flow no contestó por el registro de tarjeta: %s', e)
            return _pantalla_facturacion('sin-tarjeta')

        customer_id = datos.get('customerId', '')
        cliente = ClientePasarela.objects.filter(
            proveedor=PROVEEDOR_FLOW, customer_id=customer_id,
        ).select_related('workspace').first()
        if cliente is None:
            logger.warning('Flow registró la tarjeta de un cliente que no es nuestro: %s', customer_id)
            return _pantalla_facturacion('sin-tarjeta')

        marca = datos.get('creditCardType') or 'Tarjeta'
        ultimos = datos.get('last4CardDigits') or '????'
        metodo, creado = MetodoPago.objects.get_or_create(
            workspace=cliente.workspace,
            proveedor=PROVEEDOR_FLOW,
            defaults={
                'etiqueta': f'{marca} ···· {ultimos}',
                'token_pasarela': customer_id,
            },
        )
        if not creado:
            # Registrar de nuevo reemplaza la tarjeta anterior: en Flow un cliente
            # tiene una sola. Dejar la etiqueta vieja mostraría los cuatro dígitos
            # equivocados justo donde la persona los va a ir a mirar.
            metodo.etiqueta = f'{marca} ···· {ultimos}'
            metodo.token_pasarela = customer_id
            metodo.save(update_fields=['etiqueta', 'token_pasarela'])
        metodo.marcar_principal()

        # ¿Había un plan esperando esta tarjeta?
        pendiente = (
            Subscription.objects
            .select_related('plan')
            .filter(
                workspace=cliente.workspace, proveedor=PROVEEDOR_FLOW,
                aprobada=False, status__in=Subscription.ESTADOS_VIGENTES,
            )
            .first()
        )
        if pendiente is None:
            return _pantalla_facturacion('tarjeta-lista')

        try:
            SuscribirView._suscribir_en_flow(FlowClient(), cliente, pendiente.plan, pendiente)
        except Exception as e:
            logger.warning('La tarjeta quedó registrada pero Flow no suscribió: %s', e)
            return _pantalla_facturacion('tarjeta-sin-plan')

        return _pantalla_facturacion('listo')


class RetornoPayPalView(APIView):
    """El navegador vuelve de aprobar la suscripción en PayPal.

    PayPal manda `subscription_id` en la vuelta, pero **no se le cree**: se le pregunta
    a PayPal en qué estado quedó. El id viaja en una URL que la persona puede editar.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        subscription_id = request.query_params.get('subscription_id')
        if not subscription_id:
            return _pantalla_facturacion('rechazado')

        sub = Subscription.objects.filter(
            proveedor=PROVEEDOR_PAYPAL, id_externo=subscription_id,
        ).select_related('workspace', 'plan').first()
        if sub is None:
            return _pantalla_facturacion('rechazado')

        try:
            datos = PayPalClient().obtener_suscripcion(subscription_id)
        except Exception as e:
            logger.warning('PayPal no contestó por la suscripción %s: %s', subscription_id, e)
            return _pantalla_facturacion('rechazado')

        if datos.get('status') not in ('ACTIVE', 'APPROVED'):
            return _pantalla_facturacion('rechazado')

        _activar_paypal(sub, datos)
        return _pantalla_facturacion('listo')


class PayPalWebhookView(APIView):
    """PayPal avisa de cobros, suspensiones y bajas.

    Sin firma verificada no se procesa nada (ver `verificar_webhook`). Se contesta 200
    igual cuando el evento no interesa: un 4xx hace que PayPal reintente durante días.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        try:
            cuerpo = json.loads(request.body or b'{}')
        except json.JSONDecodeError:
            return HttpResponse('cuerpo ilegible', status=400)

        if not PayPalClient().verificar_webhook(request.headers, cuerpo):
            # 400 y no 403: es la respuesta que PayPal espera para un aviso que
            # rechazamos, y así queda en su panel como fallido.
            return HttpResponse('firma no verificada', status=400)

        evento = cuerpo.get('event_type', '')
        recurso = cuerpo.get('resource', {}) or {}
        logger.info('Webhook de PayPal: %s', evento)

        if evento == 'BILLING.SUBSCRIPTION.ACTIVATED':
            sub = _sub_de_paypal(recurso.get('id'))
            if sub:
                _activar_paypal(sub, recurso)

        elif evento == 'PAYMENT.SALE.COMPLETED':
            sub = _sub_de_paypal(recurso.get('billing_agreement_id'))
            if sub:
                monto = recurso.get('amount', {}).get('total') or '0'
                Payment.objects.create(
                    workspace=sub.workspace,
                    subscription=sub,
                    proveedor=PROVEEDOR_PAYPAL,
                    moneda=MONEDA_USD,
                    referencia_pasarela=recurso.get('id', ''),
                    commerce_order=Payment.generate_commerce_order(),
                    amount=int(float(monto)),
                    status='paid',
                    subject=f'Afable {sub.plan.name}',
                )

        elif evento in ('BILLING.SUBSCRIPTION.SUSPENDED', 'PAYMENT.SALE.DENIED'):
            sub = _sub_de_paypal(recurso.get('id') or recurso.get('billing_agreement_id'))
            if sub:
                sub.status = Subscription.ESTADO_SUSPENDIDA
                sub.save(update_fields=['status', 'updated_at'])

        elif evento in ('BILLING.SUBSCRIPTION.CANCELLED', 'BILLING.SUBSCRIPTION.EXPIRED'):
            sub = _sub_de_paypal(recurso.get('id'))
            if sub:
                sub.status = Subscription.ESTADO_CANCELADA
                sub.save(update_fields=['status', 'updated_at'])

        return HttpResponse('OK')


def _sub_de_paypal(id_externo):
    if not id_externo:
        return None
    return (
        Subscription.objects
        .select_related('workspace', 'plan')
        .filter(proveedor=PROVEEDOR_PAYPAL, id_externo=id_externo)
        .first()
    )


def _activar_paypal(sub, datos):
    """Deja la suscripción activa y guarda la cuenta de PayPal como medio de pago.

    En PayPal el medio de pago no es una tarjeta nuestra: es la cuenta con la que la
    persona aprobó. Se guarda su correo para que la pantalla pueda mostrar con qué se
    está pagando, que es la pregunta que uno le hace a esa lista.
    """
    activar(sub)

    correo = (datos.get('subscriber') or {}).get('email_address') or 'cuenta de PayPal'
    metodo, creado = MetodoPago.objects.get_or_create(
        workspace=sub.workspace,
        proveedor=PROVEEDOR_PAYPAL,
        defaults={'etiqueta': f'PayPal · {correo}', 'token_pasarela': sub.id_externo},
    )
    if not creado:
        metodo.etiqueta = f'PayPal · {correo}'
        metodo.token_pasarela = sub.id_externo
        metodo.save(update_fields=['etiqueta', 'token_pasarela'])
    metodo.marcar_principal()

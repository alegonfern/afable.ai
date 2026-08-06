"""La facturación de un Workspace: plan, medios de pago y cartola.

Todo lo de acá exige ser **administrador** del Workspace (`IsAdmin`), que es el mismo
embudo que usa el resto de la app. Un editor puede subir archivos y correr agentes; darle
de baja el plan a la empresa es otra cosa.

El orden de los pasos NO es el mismo en las dos pasarelas, y eso explica la forma de
`SuscribirView`:

- **PayPal** aprueba y cobra en el mismo paso: se crea la suscripción, la persona la
  aprueba en PayPal, y al volver ya hay medio de pago.
- **Flow** necesita la tarjeta registrada ANTES de poder suscribir. Si todavía no hay,
  la suscripción queda anotada sin aprobar y se completa cuando la persona vuelve de
  registrar su tarjeta (`RetornoTarjetaFlowView`).

Es a propósito que la intención quede guardada como una `Subscription` sin aprobar en vez
de en una tabla aparte o en la sesión: si la persona abandona a mitad de camino, el
administrador ve en la pantalla que hay algo a medias, y no un plan que se perdió.
"""

import logging

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.workspaces.permissions import IsAdmin
from services.flow_client import FlowClient
from services.paypal_client import PayPalClient, PayPalError

from .models import (
    DIAS_DE_PRUEBA, MONEDA_DE_PROVEEDOR, PROVEEDOR_CHOICES, PROVEEDOR_FLOW,
    PROVEEDOR_PAYPAL, ClientePasarela, MetodoPago, Payment, Plan, Subscription,
)
from .serializers import (
    MetodoPagoSerializer, PaymentSerializer, PlanSerializer, SubscriptionSerializer,
)

logger = logging.getLogger(__name__)

PROVEEDORES = [p[0] for p in PROVEEDOR_CHOICES]

# El producto de PayPal es uno solo para todo Afable; los planes cuelgan de él.
PAYPAL_PRODUCT_ID = 'AFABLE-SUSCRIPCION'


def email_de_facturacion(workspace, usuario=None):
    """A qué correo van los comprobantes.

    El de la empresa si lo cargó; si no, el del administrador que está contratando.
    Un solo lugar para que la pasarela, el comprobante y el aviso de cobro rechazado
    no terminen mandándose a tres direcciones distintas.
    """
    if workspace.billing_email:
        return workspace.billing_email
    return usuario.email if usuario else ''


def suscripcion_vigente(workspace):
    """La suscripción que manda hoy en esa empresa, o None.

    Es la consulta que hacen todas las vistas, y está acá para que ninguna se olvide de
    incluir el estado de prueba: quien está probando tiene plan.

    Ordena la **aprobada primero**, no la más nueva. Mientras alguien está a mitad de un
    cambio de plan conviven dos: la que paga hoy y la que todavía no aprobó. Devolver la
    nueva mostraría "falta terminar el pago" a una empresa que está al día.
    """
    return (
        Subscription.objects
        .select_related('plan')
        .filter(workspace=workspace, status__in=Subscription.ESTADOS_VIGENTES)
        .order_by('-aprobada', '-created_at')
        .first()
    )


def activar(sub):
    """Deja esta suscripción como la que paga, y da de baja las demás.

    ⭐ Las anteriores se cancelan **acá y no al elegir el plan**. Cancelarlas antes
    parecía más ordenado, pero si después la pasarela fallaba, la empresa se quedaba sin
    el plan que SÍ tenía: un problema de Flow le cortaba el servicio a alguien que estaba
    pagando. Ahora conviven hasta que la nueva quede confirmada.
    """
    sub.status = Subscription.ESTADO_ACTIVA
    sub.aprobada = True
    sub.save(update_fields=['status', 'aprobada', 'updated_at'])

    Subscription.objects.filter(
        workspace=sub.workspace, status__in=Subscription.ESTADOS_VIGENTES,
    ).exclude(pk=sub.pk).update(status=Subscription.ESTADO_CANCELADA)
    return sub


def _cliente_pasarela(workspace, proveedor, crear_en_flow=None, email=''):
    """El id de cliente de esa empresa en esa pasarela, creándolo si es la primera vez.

    `crear_en_flow` recibe el `FlowClient` ya armado. Se pasa desde afuera para que la
    prueba pueda simular la pasarela sin que esta función sepa de mocks.
    """
    fila = ClientePasarela.objects.filter(workspace=workspace, proveedor=proveedor).first()
    if fila:
        return fila

    if proveedor == PROVEEDOR_FLOW:
        datos = crear_en_flow.create_customer(
            name=workspace.name,
            email=email,
            external_id=f'ws-{workspace.id}',
        )
        customer_id = datos.get('customerId', '')
    else:
        # PayPal no tiene "customer": el pagador se identifica con su cuenta al
        # aprobar. Se guarda igual la fila para que la pantalla pueda decir "ya está
        # conectado con PayPal" sin preguntarle a PayPal.
        customer_id = f'ws-{workspace.id}'

    return ClientePasarela.objects.create(
        workspace=workspace, proveedor=proveedor, customer_id=customer_id,
    )


def _asegurar_plan_en_flow(client, plan):
    """El plan tiene que existir en Flow antes de poder suscribir a alguien.

    Flow contesta con error si el plan ya está creado, y ese error es el caso normal a
    partir del segundo cliente: se traga a propósito. No hay forma barata de
    distinguir "ya existe" de otro problema, y si el plan de verdad no se pudo crear,
    la suscripción que viene enseguida falla y ahí sí se le avisa a la persona.
    """
    try:
        client.create_plan(
            plan_id=plan.id,
            name=plan.name,
            amount=plan.price_clp,
            interval=3,  # 3 = mensual en Flow
            trial_period_days=DIAS_DE_PRUEBA,
        )
    except Exception:
        logger.info('El plan %s ya estaba en Flow (o no se pudo crear).', plan.id)


class EstadoFacturacionView(APIView):
    """Todo lo que la pantalla necesita, en una sola llamada.

    Va junto porque se dibuja junto: el plan actual, con qué se paga, qué se cobró y
    qué otros planes hay. Cuatro llamadas para una sola pantalla harían que se pinte
    en cuatro tiempos.
    """

    permission_classes = [IsAdmin]

    def get(self, request, slug):
        workspace = request.workspace
        sub = suscripcion_vigente(workspace)
        paypal_disponible = PayPalClient().configurado

        return Response({
            'suscripcion': SubscriptionSerializer(sub).data if sub else None,
            'metodos_pago': MetodoPagoSerializer(
                MetodoPago.objects.filter(workspace=workspace), many=True,
            ).data,
            'cobros': PaymentSerializer(
                Payment.objects.filter(workspace=workspace)[:24], many=True,
            ).data,
            'planes': PlanSerializer(Plan.objects.filter(is_active=True), many=True).data,
            # Cuáles se pueden ofrecer HOY. Sin esto la pantalla mostraría un botón de
            # PayPal que revienta al apretarlo porque faltan las credenciales.
            'proveedores': {
                PROVEEDOR_FLOW: bool(settings.FLOW_API_KEY),
                PROVEEDOR_PAYPAL: paypal_disponible,
            },
            'dias_de_prueba': DIAS_DE_PRUEBA,
        })


class SuscribirView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, slug):
        workspace = request.workspace
        plan_id = request.data.get('plan_id')
        proveedor = request.data.get('proveedor', PROVEEDOR_FLOW)

        if proveedor not in PROVEEDORES:
            return Response({'detail': 'Pasarela desconocida.'}, status=status.HTTP_400_BAD_REQUEST)

        plan = Plan.objects.filter(id=plan_id, is_active=True).first()
        if plan is None:
            return Response({'detail': 'Ese plan no existe.'}, status=status.HTTP_404_NOT_FOUND)

        if plan.es_a_medida:
            # Enterprise no pasa por pasarela: es una conversación. Cobrarlo
            # automáticamente en $0 dejaría a la empresa "suscrita" y sin servicio.
            return Response(
                {'detail': 'Ese plan se acuerda con nosotros. Escríbanos y lo armamos.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        moneda = MONEDA_DE_PROVEEDOR[proveedor]
        if not plan.precio_en(moneda):
            return Response(
                {'detail': f'El plan {plan.name} no tiene precio en {moneda}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if proveedor == PROVEEDOR_PAYPAL:
            return self._con_paypal(request, workspace, plan)
        return self._con_flow(request, workspace, plan)

    # ── Flow ────────────────────────────────────────────────────────────────────

    def _con_flow(self, request, workspace, plan):
        client = FlowClient()
        try:
            cliente = _cliente_pasarela(
                workspace, PROVEEDOR_FLOW, crear_en_flow=client,
                email=email_de_facturacion(workspace, request.user),
            )
        except Exception as e:
            return Response({'detail': f'Flow no respondió: {e}'}, status=status.HTTP_502_BAD_GATEWAY)

        tarjeta = MetodoPago.objects.filter(
            workspace=workspace, proveedor=PROVEEDOR_FLOW,
        ).exclude(token_pasarela='').first()

        sub = self._anotar_intencion(workspace, plan, PROVEEDOR_FLOW)

        if tarjeta is None:
            # Sin tarjeta registrada no se puede suscribir en Flow. Se manda a
            # registrarla y la suscripción se completa al volver.
            try:
                datos = client.register_card(
                    customer_id=cliente.customer_id,
                    url_return=settings.FLOW_REGISTER_RETURN_URL,
                )
            except Exception as e:
                sub.delete()
                return Response(
                    {'detail': f'Flow no pudo abrir el registro de tarjeta: {e}'},
                    status=status.HTTP_502_BAD_GATEWAY,
                )
            url = datos.get('url', '')
            token = datos.get('token', '')
            return Response({
                'requiere_tarjeta': True,
                'url': f'{url}?token={token}' if token else url,
                'suscripcion': SubscriptionSerializer(sub).data,
            }, status=status.HTTP_202_ACCEPTED)

        try:
            self._suscribir_en_flow(client, cliente, plan, sub)
        except Exception as e:
            sub.delete()
            return Response({'detail': f'Flow rechazó la suscripción: {e}'},
                            status=status.HTTP_502_BAD_GATEWAY)

        return Response(SubscriptionSerializer(sub).data, status=status.HTTP_201_CREATED)

    @staticmethod
    def _suscribir_en_flow(client, cliente, plan, sub):
        """Crea la suscripción en Flow y la deja aprobada. Reusado por el retorno."""
        _asegurar_plan_en_flow(client, plan)
        datos = client.subscribe(
            customer_id=cliente.customer_id,
            plan_id=plan.id,
            trial_period_days=DIAS_DE_PRUEBA,
        )
        sub.id_externo = datos.get('subscriptionId', '')
        sub.save(update_fields=['id_externo', 'updated_at'])
        return activar(sub)

    # ── PayPal ──────────────────────────────────────────────────────────────────

    def _con_paypal(self, request, workspace, plan):
        client = PayPalClient()
        if not client.configurado:
            return Response(
                {'detail': 'PayPal todavía no está configurado.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        _cliente_pasarela(workspace, PROVEEDOR_PAYPAL)
        sub = self._anotar_intencion(workspace, plan, PROVEEDOR_PAYPAL)

        frente = settings.FRONTEND_URL
        try:
            client.asegurar_producto(PAYPAL_PRODUCT_ID, 'Afable', 'IA para equipos')
            client.asegurar_plan(
                plan_id=plan.id,
                product_id=PAYPAL_PRODUCT_ID,
                nombre=f'Afable {plan.name}',
                precio_usd=plan.price_usd,
                dias_de_prueba=DIAS_DE_PRUEBA,
            )
            id_externo, aprobacion = client.crear_suscripcion(
                plan_id=plan.id,
                email=email_de_facturacion(workspace, request.user),
                url_retorno=f'{settings.BACKEND_URL}/api/v1/payments/paypal/retorno/',
                url_cancelacion=f'{frente}/app/admin/facturacion?paypal=cancelado',
                nombre_empresa=workspace.name,
            )
        except PayPalError as e:
            sub.delete()
            return Response({'detail': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        sub.id_externo = id_externo
        sub.save(update_fields=['id_externo', 'updated_at'])

        return Response({
            'requiere_aprobacion': True,
            'url': aprobacion,
            'suscripcion': SubscriptionSerializer(sub).data,
        }, status=status.HTTP_202_ACCEPTED)

    # ── Común ───────────────────────────────────────────────────────────────────

    @staticmethod
    def _anotar_intencion(workspace, plan, proveedor):
        """Deja anotado el plan que se eligió, todavía sin aprobar.

        No toca el plan anterior: eso lo hace `activar` cuando la pasarela confirma.
        Una intención de pago no puede dar de baja un plan que se está pagando.
        """
        return Subscription.objects.create(
            workspace=workspace,
            plan=plan,
            proveedor=proveedor,
            moneda=MONEDA_DE_PROVEEDOR[proveedor],
            status=Subscription.ESTADO_PRUEBA,
            aprobada=False,
        )


class CancelarSuscripcionView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, slug):
        sub = suscripcion_vigente(request.workspace)
        if sub is None:
            return Response({'detail': 'No hay ningún plan activo.'},
                            status=status.HTTP_404_NOT_FOUND)

        if sub.id_externo:
            try:
                if sub.proveedor == PROVEEDOR_PAYPAL:
                    PayPalClient().cancelar_suscripcion(sub.id_externo)
                else:
                    FlowClient().cancel_subscription(sub.id_externo)
            except Exception as e:
                # No se marca cancelada acá: si la pasarela sigue cobrando y nosotros
                # ya dijimos "cancelada", el cliente paga por algo que no tiene.
                return Response({'detail': f'La pasarela no confirmó la baja: {e}'},
                                status=status.HTTP_502_BAD_GATEWAY)

        sub.status = Subscription.ESTADO_CANCELADA
        sub.save(update_fields=['status', 'updated_at'])
        return Response(SubscriptionSerializer(sub).data)


class MetodosPagoView(APIView):
    """Los medios de pago guardados de la empresa."""

    permission_classes = [IsAdmin]

    def get(self, request, slug):
        return Response(MetodoPagoSerializer(
            MetodoPago.objects.filter(workspace=request.workspace), many=True,
        ).data)

    def post(self, request, slug):
        """Empieza el alta de un medio de pago nuevo.

        Sólo tiene sentido en Flow: es lo que abre el formulario de tarjeta. En PayPal
        el medio de pago ES la cuenta con la que se aprueba la suscripción, así que no
        hay nada que agregar por separado — decirlo es más honesto que mostrar un
        botón que no lleva a ninguna parte.
        """
        proveedor = request.data.get('proveedor', PROVEEDOR_FLOW)
        if proveedor == PROVEEDOR_PAYPAL:
            return Response(
                {'detail': 'En PayPal el medio de pago se elige al aprobar la suscripción.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if proveedor != PROVEEDOR_FLOW:
            return Response({'detail': 'Pasarela desconocida.'}, status=status.HTTP_400_BAD_REQUEST)

        client = FlowClient()
        try:
            cliente = _cliente_pasarela(
                request.workspace, PROVEEDOR_FLOW, crear_en_flow=client,
                email=email_de_facturacion(request.workspace, request.user),
            )
            datos = client.register_card(
                customer_id=cliente.customer_id,
                url_return=settings.FLOW_REGISTER_RETURN_URL,
            )
        except Exception as e:
            return Response({'detail': f'Flow no respondió: {e}'}, status=status.HTTP_502_BAD_GATEWAY)

        url = datos.get('url', '')
        token = datos.get('token', '')
        return Response({'url': f'{url}?token={token}' if token else url})


class MetodoPagoDetalleView(APIView):
    permission_classes = [IsAdmin]

    def _fila(self, request, pk):
        return MetodoPago.objects.filter(workspace=request.workspace, pk=pk).first()

    def delete(self, request, slug, pk):
        metodo = self._fila(request, pk)
        if metodo is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        sub = suscripcion_vigente(request.workspace)
        if sub and sub.proveedor == metodo.proveedor:
            # Quitar el medio con el que se está pagando dejaría una suscripción que
            # no se puede cobrar: la próxima factura se rechaza y la empresa se
            # enteraría cuando le corten el servicio.
            return Response(
                {'detail': 'Con este medio se está pagando el plan. Cambie el plan de '
                           'medio o cancélelo antes de quitarlo.'},
                status=status.HTTP_409_CONFLICT,
            )

        if metodo.proveedor == PROVEEDOR_FLOW:
            cliente = ClientePasarela.objects.filter(
                workspace=request.workspace, proveedor=PROVEEDOR_FLOW,
            ).first()
            if cliente:
                try:
                    FlowClient().unregister_card(cliente.customer_id)
                except Exception as e:
                    return Response({'detail': f'Flow no pudo borrar la tarjeta: {e}'},
                                    status=status.HTTP_502_BAD_GATEWAY)

        era_principal = metodo.principal
        metodo.delete()

        # La empresa no puede quedar sin principal habiendo medios: el próximo cobro
        # tiene que saber contra qué va.
        if era_principal:
            otro = MetodoPago.objects.filter(workspace=request.workspace).first()
            if otro:
                otro.marcar_principal()

        return Response(status=status.HTTP_204_NO_CONTENT)


class MetodoPagoPrincipalView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, slug, pk):
        metodo = MetodoPago.objects.filter(workspace=request.workspace, pk=pk).first()
        if metodo is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        metodo.marcar_principal()
        return Response(MetodoPagoSerializer(metodo).data)

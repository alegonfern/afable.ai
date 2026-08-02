from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from services.flow_client import FlowClient
from .models import FlowCustomer, Payment, Plan, Subscription
from .serializers import PlanSerializer, SubscriptionSerializer


class PlansListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        plans = Plan.objects.filter(is_active=True)
        return Response(PlanSerializer(plans, many=True).data)


class CheckoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        plan_id = request.data.get('plan_id')
        if not plan_id:
            return Response({'error': 'plan_id requerido'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            plan = Plan.objects.get(id=plan_id, is_active=True)
        except Plan.DoesNotExist:
            return Response({'error': 'Plan no encontrado'}, status=status.HTTP_404_NOT_FOUND)

        commerce_order = Payment.generate_commerce_order()
        payment = Payment.objects.create(
            user=request.user,
            commerce_order=commerce_order,
            amount=plan.price_clp,
            subject=f'Afable {plan.name}',
        )

        try:
            client = FlowClient()
            result = client.create_payment(
                commerce_order=commerce_order,
                subject=f'Afable {plan.name}',
                amount=plan.price_clp,
                email=request.user.email,
                url_confirmation=settings.FLOW_WEBHOOK_URL,
                url_return=settings.FLOW_RETURN_URL,
            )
        except Exception as e:
            payment.status = 'cancelled'
            payment.save()
            return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        token = result.get('token')
        payment.flow_token = token
        payment.save()

        return Response({
            'url': f'{result.get("url")}?token={token}',
            'token': token,
            'commerce_order': commerce_order,
        })


class FlowWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get('token')
        if not token:
            return HttpResponse('missing token', status=400)

        try:
            client = FlowClient()
            data = client.get_payment_status(token)
        except Exception:
            return HttpResponse('flow error', status=500)

        flow_status = data.get('status')
        commerce_order = data.get('commerceOrder')

        try:
            payment = Payment.objects.get(commerce_order=commerce_order)
        except Payment.DoesNotExist:
            return HttpResponse('not found', status=404)

        if flow_status == 2:
            payment.status = 'paid'
            payment.save()

            active_sub = Subscription.objects.filter(
                user=payment.user, status__in=['trial', 'active']
            ).first()
            if active_sub:
                active_sub.status = 'active'
                active_sub.save()

        elif flow_status in (3, 4):
            payment.status = 'rejected'
            payment.save()

        return HttpResponse('OK')


class PaymentReturnView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        token = request.query_params.get('token')
        frontend = settings.FRONTEND_URL

        if not token:
            return redirect(f'{frontend}/app/pago/resultado?status=failed')

        try:
            client = FlowClient()
            data = client.get_payment_status(token)
            if data.get('status') == 2:
                return redirect(f'{frontend}/app/pago/resultado?status=success')
        except Exception:
            pass

        return redirect(f'{frontend}/app/pago/resultado?status=failed')


class SubscribeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        plan_id = request.data.get('plan_id')
        if not plan_id:
            return Response({'error': 'plan_id requerido'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            plan = Plan.objects.get(id=plan_id, is_active=True)
        except Plan.DoesNotExist:
            return Response({'error': 'Plan no encontrado'}, status=status.HTTP_404_NOT_FOUND)

        # Get or create Flow customer
        flow_customer_obj = FlowCustomer.objects.filter(user=request.user).first()
        client = FlowClient()

        if not flow_customer_obj:
            try:
                customer_data = client.create_customer(
                    name=request.user.get_full_name() or request.user.email,
                    email=request.user.email,
                    external_id=request.user.id,
                )
                flow_customer_obj = FlowCustomer.objects.create(
                    user=request.user,
                    flow_customer_id=customer_data['customerId'],
                )
            except Exception as e:
                return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        try:
            sub_data = client.subscribe(
                customer_id=flow_customer_obj.flow_customer_id,
                plan_id=plan_id,
                trial_period_days=14,
            )
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        Subscription.objects.filter(
            user=request.user, status__in=['trial', 'active']
        ).update(status='cancelled')

        sub = Subscription.objects.create(
            user=request.user,
            plan=plan,
            flow_subscription_id=sub_data.get('subscriptionId', ''),
            status='trial',
        )

        return Response(SubscriptionSerializer(sub).data, status=status.HTTP_201_CREATED)


class SubscriptionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sub = Subscription.objects.filter(
            user=request.user, status__in=['trial', 'active']
        ).first()
        if not sub:
            return Response(None)
        return Response(SubscriptionSerializer(sub).data)


class CancelSubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        sub = Subscription.objects.filter(
            user=request.user, status__in=['trial', 'active']
        ).first()
        if not sub:
            return Response({'error': 'No hay suscripción activa'}, status=status.HTTP_404_NOT_FOUND)

        if sub.flow_subscription_id:
            try:
                client = FlowClient()
                client.cancel_subscription(sub.flow_subscription_id)
            except Exception as e:
                return Response({'error': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        sub.status = 'cancelled'
        sub.save()
        return Response({'status': 'cancelled'})

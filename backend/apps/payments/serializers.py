from rest_framework import serializers

from .models import MetodoPago, Payment, Plan, Subscription


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = [
            'id', 'name', 'price_clp', 'price_usd', 'es_a_medida',
            'max_agents', 'max_integrations', 'queries_per_month', 'is_active',
        ]


class SubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)
    vigente = serializers.BooleanField(read_only=True)

    class Meta:
        model = Subscription
        fields = [
            'id', 'plan', 'proveedor', 'moneda', 'status', 'aprobada', 'vigente',
            'trial_end', 'current_period_end', 'created_at',
        ]


class MetodoPagoSerializer(serializers.ModelSerializer):
    """Lo que la pantalla necesita para dibujar la lista, y nada más.

    `token_pasarela` queda AFUERA a propósito: es con qué se le cobra a esa empresa y
    no tiene por qué salir del servidor.
    """

    class Meta:
        model = MetodoPago
        fields = ['id', 'proveedor', 'etiqueta', 'principal', 'creado_at']


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            'commerce_order', 'proveedor', 'moneda', 'amount', 'status',
            'subject', 'created_at',
        ]

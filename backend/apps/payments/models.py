from uuid import uuid4
from django.conf import settings
from django.db import models


class Plan(models.Model):
    id = models.CharField(max_length=100, primary_key=True)
    name = models.CharField(max_length=100)
    price_clp = models.IntegerField()
    max_agents = models.IntegerField(default=0)
    max_integrations = models.IntegerField(default=0)
    queries_per_month = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'payment_plans'
        verbose_name = 'Plan'

    def __str__(self):
        return self.name


class FlowCustomer(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='flow_customer'
    )
    flow_customer_id = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'flow_customers'
        verbose_name = 'Cliente Flow'

    def __str__(self):
        return f'{self.user.email} → {self.flow_customer_id}'


class Subscription(models.Model):
    STATUS_CHOICES = [
        ('trial', 'Trial'),
        ('active', 'Activa'),
        ('suspended', 'Suspendida'),
        ('cancelled', 'Cancelada'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscriptions'
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='subscriptions')
    flow_subscription_id = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='trial')
    trial_end = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'subscriptions'
        verbose_name = 'Suscripción'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.email} — {self.plan.name} ({self.status})'


class Payment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('paid', 'Pagado'),
        ('rejected', 'Rechazado'),
        ('cancelled', 'Cancelado'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payments'
    )
    subscription = models.ForeignKey(
        Subscription, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments'
    )
    flow_token = models.CharField(max_length=200, blank=True)
    commerce_order = models.CharField(max_length=50, unique=True)
    amount = models.IntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    subject = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payments'
        verbose_name = 'Pago'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.commerce_order} — {self.status}'

    @classmethod
    def generate_commerce_order(cls):
        return f'VEL-{uuid4().hex[:12].upper()}'

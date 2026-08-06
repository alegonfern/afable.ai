from django.contrib import admin

from .models import ClientePasarela, MetodoPago, Payment, Plan, Subscription


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'price_clp', 'price_usd', 'es_a_medida', 'is_active']


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['workspace', 'plan', 'proveedor', 'status', 'aprobada', 'current_period_end']
    list_filter = ['proveedor', 'status', 'aprobada']


@admin.register(MetodoPago)
class MetodoPagoAdmin(admin.ModelAdmin):
    list_display = ['workspace', 'proveedor', 'etiqueta', 'principal']
    list_filter = ['proveedor', 'principal']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['commerce_order', 'workspace', 'proveedor', 'amount', 'moneda', 'status']
    list_filter = ['proveedor', 'status']


admin.site.register(ClientePasarela)

"""Lo que llaman las pasarelas y la página de precios pública.

La facturación de una empresa NO está acá: vive en `facturacion_urls.py`, colgada de
`/api/v1/workspaces/<slug>/`, porque el que paga es el Workspace.

⚠️ `webhook/confirm/` y `return/` conservan su nombre a propósito: esas direcciones
están cargadas en el panel de Flow y renombrarlas dejaría los cobros sin confirmar.
"""

from django.urls import path

from . import views

urlpatterns = [
    path('plans/', views.PlansListView.as_view(), name='planes'),

    # Flow
    path('webhook/confirm/', views.FlowWebhookView.as_view(), name='flow-webhook'),
    path('return/', views.PaymentReturnView.as_view(), name='flow-retorno'),
    path('tarjeta/retorno/', views.RetornoTarjetaFlowView.as_view(), name='flow-tarjeta-retorno'),

    # PayPal
    path('paypal/retorno/', views.RetornoPayPalView.as_view(), name='paypal-retorno'),
    path('webhook/paypal/', views.PayPalWebhookView.as_view(), name='paypal-webhook'),
]

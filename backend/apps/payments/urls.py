from django.urls import path
from . import views

urlpatterns = [
    path('plans/', views.PlansListView.as_view()),
    path('checkout/', views.CheckoutView.as_view()),
    path('webhook/confirm/', views.FlowWebhookView.as_view()),
    path('return/', views.PaymentReturnView.as_view()),
    path('subscribe/', views.SubscribeView.as_view()),
    path('subscription/', views.SubscriptionDetailView.as_view()),
    path('subscription/cancel/', views.CancelSubscriptionView.as_view()),
]

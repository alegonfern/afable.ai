"""Rutas de la campana."""
from django.urls import path

from .views import NotificacionesView, NotificacionView

urlpatterns = [
    path('', NotificacionesView.as_view(), name='notificaciones'),
    path('<int:pk>/leida/', NotificacionView.as_view(), name='notificacion-leida'),
]

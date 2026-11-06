"""Conectores colgados de la Empresa: `/api/v1/workspaces/<slug>/conectores/...`."""

from django.urls import path

from . import views

P = '<slug:slug>/conectores/'

urlpatterns = [
    path(P, views.ConectoresView.as_view(), name='conectores'),
    path(P + '<str:tipo>/', views.ConectorView.as_view(), name='conector'),
    path(P + '<str:tipo>/conectar/', views.ConectarView.as_view(), name='conector-conectar'),
    path(P + '<str:tipo>/sincronizar/', views.SincronizarView.as_view(), name='conector-sincronizar'),
    path(P + '<str:tipo>/desconectar/', views.DesconectarView.as_view(), name='conector-desconectar'),
    path(P + '<str:tipo>/historial/', views.HistorialView.as_view(), name='conector-historial'),
]

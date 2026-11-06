"""Rutas del PDF de los DTE (pdf.py): `/api/v1/workspaces/<slug>/dte/...`."""

from django.urls import path

from . import views_pdf

P = '<slug:slug>/dte/'

urlpatterns = [
    path(P + 'documentos/<int:pk>/pdf/', views_pdf.DocumentoPdfView.as_view(), name='dte-documento-pdf'),
]

"""Facturación electrónica colgada de la Empresa: `/api/v1/workspaces/<slug>/dte/...`."""

from django.urls import path

from . import views

P = '<slug:slug>/dte/'

urlpatterns = [
    path(P + 'estado/', views.EstadoView.as_view(), name='dte-estado'),
    path(P + 'configuracion/', views.ConfiguracionView.as_view(), name='dte-configuracion'),
    path(P + 'certificado/', views.CertificadoView.as_view(), name='dte-certificado'),
    path(P + 'cafs/', views.CafsView.as_view(), name='dte-cafs'),
    path(P + 'probar-conexion/', views.ProbarConexionView.as_view(), name='dte-probar'),
    path(P + 'activar/', views.ActivarView.as_view(), name='dte-activar'),
    path(P + 'desactivar/', views.DesactivarView.as_view(), name='dte-desactivar'),
    path(P + 'documentos/', views.DocumentosView.as_view(), name='dte-documentos'),
    path(P + 'documentos/<int:pk>/xml/', views.DocumentoXmlView.as_view(), name='dte-documento-xml'),
    path(P + 'documentos/<int:pk>/nota/', views.NotaView.as_view(), name='dte-nota'),
    path(P + 'envios/<int:pk>/', views.EnvioView.as_view(), name='dte-envio'),
    path(P + 'envios/<int:pk>/reintentar/', views.ReintentarView.as_view(), name='dte-reintentar'),
]

# Cada pieza del facturador tiene sus rutas en su propio archivo.
from . import urls_certificacion, urls_intercambio, urls_pdf  # noqa: E402

urlpatterns += urls_pdf.urlpatterns + urls_intercambio.urlpatterns + urls_certificacion.urlpatterns

"""Rutas del asistente de certificación ante el SII (certificacion.py): `/api/v1/workspaces/<slug>/dte/...`."""

from django.urls import path

from . import views_certificacion as v

P = '<slug:slug>/dte/certificacion/'

urlpatterns = [
    path(P, v.CertificacionView.as_view(), name='dte-certificacion'),
    path(P + 'set/', v.SetView.as_view(), name='dte-certificacion-set'),
    path(P + 'generar/', v.GenerarView.as_view(), name='dte-certificacion-generar'),
    path(P + 'subir/', v.SubirView.as_view(), name='dte-certificacion-subir'),
    path(P + 'consultar/', v.ConsultarView.as_view(), name='dte-certificacion-consultar'),
    path(P + 'paso/', v.PasoView.as_view(), name='dte-certificacion-paso'),
    path(P + 'envios/<int:pk>/xml/', v.EnvioXmlView.as_view(), name='dte-certificacion-envio-xml'),
    path(P + 'intercambio/', v.IntercambioView.as_view(), name='dte-certificacion-intercambio'),
    path(P + 'muestras/', v.MuestrasView.as_view(), name='dte-certificacion-muestras'),
]

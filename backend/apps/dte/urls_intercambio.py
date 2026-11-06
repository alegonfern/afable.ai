"""Rutas del intercambio con clientes y proveedores (intercambio.py): `/api/v1/workspaces/<slug>/dte/...`."""

from django.urls import path

from . import views_intercambio as v

P = '<slug:slug>/dte/'

urlpatterns = [
    path(P + 'recibidos/', v.RecibidosView.as_view(), name='dte-recibidos'),
    path(P + 'recibidos/subir/', v.SubirRecibidoView.as_view(), name='dte-recibidos-subir'),
    path(P + 'recibidos/<int:pk>/', v.RecibidoView.as_view(), name='dte-recibido'),
    path(P + 'recibidos/<int:pk>/aceptar/', v.AceptarRecibidoView.as_view(), name='dte-recibido-aceptar'),
    path(P + 'recibidos/<int:pk>/reclamar/', v.ReclamarRecibidoView.as_view(), name='dte-recibido-reclamar'),
    path(P + 'recibidos/<int:pk>/xml/', v.RecibidoXmlView.as_view(), name='dte-recibido-xml'),
    path(P + 'casilla/', v.CasillaView.as_view(), name='dte-casilla'),
    path(P + 'casilla/probar/', v.ProbarCasillaView.as_view(), name='dte-casilla-probar'),
    path(P + 'casilla/revisar/', v.RevisarCasillaView.as_view(), name='dte-casilla-revisar'),
    path(P + 'documentos/<int:pk>/enviar-a-cliente/', v.EnviarAClienteView.as_view(), name='dte-enviar-a-cliente'),
]

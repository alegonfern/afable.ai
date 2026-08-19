"""Facturación colgada del Workspace: `/api/v1/workspaces/<slug>/facturacion/...`.

Va en un archivo aparte de `urls.py` porque las dos mitades de esta app se montan en
lugares distintos: esto bajo `workspaces/` (necesita el slug y el permiso), y lo de
`urls.py` en la raíz de `payments/` porque lo llaman las pasarelas, que no saben de
Workspaces.
"""

from django.urls import path

from . import facturacion

urlpatterns = [
    path(
        '<slug:slug>/facturacion/',
        facturacion.EstadoFacturacionView.as_view(), name='facturacion-estado',
    ),
    path(
        '<slug:slug>/facturacion/suscribir/',
        facturacion.SuscribirView.as_view(), name='facturacion-suscribir',
    ),
    path(
        '<slug:slug>/facturacion/cancelar/',
        facturacion.CancelarSuscripcionView.as_view(), name='facturacion-cancelar',
    ),
    path(
        '<slug:slug>/facturacion/metodos/',
        facturacion.MetodosPagoView.as_view(), name='facturacion-metodos',
    ),
    path(
        '<slug:slug>/facturacion/metodos/<int:pk>/',
        facturacion.MetodoPagoDetalleView.as_view(), name='facturacion-metodo-detalle',
    ),
    path(
        '<slug:slug>/facturacion/metodos/<int:pk>/principal/',
        facturacion.MetodoPagoPrincipalView.as_view(), name='facturacion-metodo-principal',
    ),
]

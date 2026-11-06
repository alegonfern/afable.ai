"""Finanzas colgada de la Empresa: `/api/v1/workspaces/<slug>/finanzas/...`, igual que
Facturación, para que los permisos por rol funcionen sin código propio."""

from django.urls import path

from . import views

P = '<slug:slug>/finanzas/'

urlpatterns = [
    path(P + 'configuracion/', views.ConfiguracionView.as_view(), name='finanzas-configuracion'),
    path(P + 'categorias/', views.CategoriasView.as_view(), name='finanzas-categorias'),
    path(P + 'categorias/<int:pk>/', views.CategoriaView.as_view(), name='finanzas-categoria'),
    path(P + 'proyectos/', views.ProyectosView.as_view(), name='finanzas-proyectos'),
    path(P + 'cargas/', views.CargasView.as_view(), name='finanzas-cargas'),
    path(P + 'cargas/<int:pk>/', views.CargaView.as_view(), name='finanzas-carga'),
    path(P + 'cargas/<int:pk>/sugerir/', views.SugerirCargaView.as_view(), name='finanzas-carga-sugerir'),
    path(P + 'cargas/<int:pk>/confirmar/', views.ConfirmarCargaView.as_view(), name='finanzas-carga-confirmar'),
    path(P + 'documentos/', views.DocumentosView.as_view(), name='finanzas-documentos'),
    path(P + 'documentos/lote/', views.LoteView.as_view(), name='finanzas-lote'),
    path(P + 'documentos/sugerir/', views.SugerirView.as_view(), name='finanzas-sugerir'),
    path(P + 'documentos/<int:pk>/', views.DocumentoView.as_view(), name='finanzas-documento'),
    path(P + 'contrapartes/', views.ContrapartesView.as_view(), name='finanzas-contrapartes'),
    path(P + 'contrapartes/<int:pk>/', views.ContraparteView.as_view(), name='finanzas-contraparte'),
    path(P + 'resumen/', views.ResumenView.as_view(), name='finanzas-resumen'),
    path(P + 'impuestos/', views.ImpuestosView.as_view(), name='finanzas-impuestos'),
    path(P + 'impuestos/<int:anio>/<int:mes>/', views.DeclaracionView.as_view(), name='finanzas-declaracion'),
    path(P + 'por-categoria/', views.PorCategoriaView.as_view(), name='finanzas-por-categoria'),
    path(P + 'proyectos/margen/', views.MargenProyectosView.as_view(), name='finanzas-margen-proyectos'),
    path(P + 'cuentas/', views.CuentasView.as_view(), name='finanzas-cuentas'),
    path(P + 'cartolas/', views.CartolasView.as_view(), name='finanzas-cartolas'),
    path(P + 'cuadre/', views.CuadreView.as_view(), name='finanzas-cuadre'),
    path(P + 'cuadre/cierres/', views.CierreView.as_view(), name='finanzas-cierres'),
    path(P + 'movimientos/', views.MovimientosView.as_view(), name='finanzas-movimientos'),
    path(P + 'movimientos/<int:pk>/<slug:accion>/', views.MovimientoView.as_view(), name='finanzas-movimiento'),
    path(P + 'cuentas-por/<slug:tipo>/', views.CuentasPorView.as_view(), name='finanzas-cuentas-por'),
    path(P + 'caja/', views.CajaView.as_view(), name='finanzas-caja'),
    path(P + 'cuenta-dueno/', views.CuentaDuenoView.as_view(), name='finanzas-cuenta-dueno'),
    path(P + 'automatizaciones/', views.AutomatizacionesView.as_view(), name='finanzas-automatizaciones'),
    path(P + 'agentes/<slug:modulo>/hoy/', views.ActividadAgenteView.as_view(), name='finanzas-agente-hoy'),
    path(P + 'automatizaciones/<slug:clave>/', views.AutomatizacionView.as_view(), name='finanzas-automatizacion'),
    path(P + 'ventas/', views.VentasView.as_view(), name='finanzas-ventas'),
]

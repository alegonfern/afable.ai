"""Rutas del explorador de archivos."""
from django.urls import path

from .views import (
    CambiosDeVersionView,
    EnviarPorCorreoView,
    ExportarPdfView,
    VistaView,
    CarpetaDetailView, CarpetaListCreateView, ContenidoView, DocumentoDetailView,
    CompartirView, ExploradorView, SubirView, VersionDetailView, VersionesView,
)

urlpatterns = [
    path('', ExploradorView.as_view(), name='explorador'),
    path('subir/', SubirView.as_view(), name='subir'),
    path('compartir/', CompartirView.as_view(), name='compartir'),
    path('carpetas/', CarpetaListCreateView.as_view(), name='carpetas'),
    path('carpetas/<int:pk>/', CarpetaDetailView.as_view(), name='carpeta'),
    path('documentos/<int:pk>/', DocumentoDetailView.as_view(), name='documento'),
    path('documentos/<int:pk>/contenido/', ContenidoView.as_view(), name='contenido'),
    path('documentos/<int:pk>/vista/', VistaView.as_view(), name='vista'),
    path('documentos/<int:pk>/pdf/', ExportarPdfView.as_view(), name='exportar-pdf'),
    path('documentos/<int:pk>/enviar/', EnviarPorCorreoView.as_view(), name='enviar-documento'),
    path('documentos/<int:pk>/versiones/', VersionesView.as_view(), name='versiones'),
    path(
        'documentos/<int:pk>/versiones/<int:numero>/',
        VersionDetailView.as_view(), name='version',
    ),
    path(
        'documentos/<int:pk>/versiones/<int:numero>/cambios/',
        CambiosDeVersionView.as_view(), name='cambios-version',
    ),
]

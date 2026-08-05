"""Rutas del explorador de archivos."""
from django.urls import path

from .views import (
    CarpetaDetailView, CarpetaListCreateView, ContenidoView, DocumentoDetailView,
    ExploradorView, VersionDetailView, VersionesView,
)

urlpatterns = [
    path('', ExploradorView.as_view(), name='explorador'),
    path('carpetas/', CarpetaListCreateView.as_view(), name='carpetas'),
    path('carpetas/<int:pk>/', CarpetaDetailView.as_view(), name='carpeta'),
    path('documentos/<int:pk>/', DocumentoDetailView.as_view(), name='documento'),
    path('documentos/<int:pk>/contenido/', ContenidoView.as_view(), name='contenido'),
    path('documentos/<int:pk>/versiones/', VersionesView.as_view(), name='versiones'),
    path(
        'documentos/<int:pk>/versiones/<int:numero>/',
        VersionDetailView.as_view(), name='version',
    ),
]

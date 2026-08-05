"""Rutas de las Sesiones.

El Workspace viaja como `?workspace=<slug>` y no en la ruta, a diferencia de los
Espacios: una Sesión se identifica por su slug dentro del Workspace, y anidarla también
en la URL haría direcciones largas sin ganar nada. El permiso se resuelve igual, en dos
niveles (ver `permissions.py`).
"""
from django.urls import path

from .archivos import ArchivoDetailView, ArchivoListCreateView
from .tareas import TareaDetailView, TareaEjecutarView, TareaListCreateView
from .views import (
    SesionDetailView, SesionDisponiblesView, SesionListCreateView, SesionMiembrosView,
)

urlpatterns = [
    path('', SesionListCreateView.as_view(), name='sesion-list'),
    # Lo específico va ANTES de `<slug:sesion_slug>/`, que si no se lo traga.
    path('<slug:sesion_slug>/tareas/', TareaListCreateView.as_view(), name='sesion-tareas'),
    path('<slug:sesion_slug>/tareas/<int:pk>/', TareaDetailView.as_view(), name='sesion-tarea'),
    path(
        '<slug:sesion_slug>/tareas/<int:pk>/ejecutar/',
        TareaEjecutarView.as_view(), name='sesion-tarea-ejecutar',
    ),
    path('<slug:sesion_slug>/archivos/', ArchivoListCreateView.as_view(), name='sesion-archivos'),
    path(
        '<slug:sesion_slug>/archivos/<int:pk>/',
        ArchivoDetailView.as_view(), name='sesion-archivo',
    ),
    path('<slug:sesion_slug>/miembros/', SesionMiembrosView.as_view(), name='sesion-miembros'),
    path(
        '<slug:sesion_slug>/disponibles/',
        SesionDisponiblesView.as_view(), name='sesion-disponibles',
    ),
    path('<slug:sesion_slug>/', SesionDetailView.as_view(), name='sesion-detail'),
]

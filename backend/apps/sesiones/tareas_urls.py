"""La ruta de las tareas que cruzan Sesiones.

Aparte de `sesiones/urls.py` a propósito: la pregunta que contesta esta vista no es sobre
una Sesión, es "qué tengo pendiente". Colgarla de `sesiones/<slug>/` habría exigido un slug
que acá no existe.
"""
from django.urls import path

from .tareas import TareasDelWorkspaceView

urlpatterns = [
    path('', TareasDelWorkspaceView.as_view(), name='tareas-del-workspace'),
]

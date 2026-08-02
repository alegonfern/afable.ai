from django.urls import path

from .views import InvitationAcceptView, InvitationPreviewView

# Endpoints por token, montados fuera de /workspaces/ a propósito: quien abre el
# link todavía no es miembro de nada, así que no puede pasar por un slug de
# Workspace. Ver es público; aceptar exige sesión y que el correo coincida.
urlpatterns = [
    path('<str:token>/', InvitationPreviewView.as_view(), name='invitation-preview'),
    path('<str:token>/accept/', InvitationAcceptView.as_view(), name='invitation-accept'),
]

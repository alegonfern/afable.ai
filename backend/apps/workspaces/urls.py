from django.urls import path

from .primeros_pasos import PrimerosPasosView
from .views import (
    InvitationDetailView, InvitationListCreateView, InvitationResendView,
    MemberDetailView, MemberListView, SectorListView,
    SpaceAvailableView, SpaceContentView, SpaceConversationsView,
    SpaceDetailView, SpaceListCreateView,
    WorkspaceDetailView, WorkspaceListCreateView,
)

# El Workspace viaja en la URL: /api/v1/workspaces/<slug>/... Así el permiso lo
# resuelve directo desde la ruta, queda visible en los registros del servidor y no
# hay estado escondido en el usuario ni en un encabezado.
urlpatterns = [
    path('', WorkspaceListCreateView.as_view(), name='workspace-list'),
    path('sectores/', SectorListView.as_view(), name='workspace-sectores'),
    path('<slug:slug>/', WorkspaceDetailView.as_view(), name='workspace-detail'),
    # La primera hora: que le falta a esta empresa. Solo el administrador.
    path(
        '<slug:slug>/primeros-pasos/',
        PrimerosPasosView.as_view(), name='workspace-primeros-pasos',
    ),
    path('<slug:slug>/members/', MemberListView.as_view(), name='workspace-members'),
    path('<slug:slug>/members/<int:pk>/', MemberDetailView.as_view(), name='workspace-member-detail'),
    path('<slug:slug>/invitations/', InvitationListCreateView.as_view(), name='workspace-invitations'),
    path('<slug:slug>/invitations/<int:pk>/', InvitationDetailView.as_view(), name='workspace-invitation-detail'),
    path('<slug:slug>/espacios/', SpaceListCreateView.as_view(), name='space-list'),
    path(
        '<slug:slug>/espacios/<slug:space_slug>/',
        SpaceDetailView.as_view(), name='space-detail',
    ),
    path(
        '<slug:slug>/espacios/<slug:space_slug>/disponibles/',
        SpaceAvailableView.as_view(), name='space-available',
    ),
    path(
        '<slug:slug>/espacios/<slug:space_slug>/conversaciones/',
        SpaceConversationsView.as_view(), name='space-conversations',
    ),
    path(
        '<slug:slug>/espacios/<slug:space_slug>/<slug:coleccion>/',
        SpaceContentView.as_view(), name='space-content',
    ),
    path(
        '<slug:slug>/invitations/<int:pk>/resend/',
        InvitationResendView.as_view(), name='workspace-invitation-resend',
    ),
]

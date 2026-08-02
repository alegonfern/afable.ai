from django.urls import path

from .views import (
    InvitationDetailView, InvitationListCreateView, InvitationResendView,
    MemberDetailView, MemberListView, SectorListView,
    WorkspaceDetailView, WorkspaceListCreateView,
)

# El Workspace viaja en la URL: /api/v1/workspaces/<slug>/... Así el permiso lo
# resuelve directo desde la ruta, queda visible en los registros del servidor y no
# hay estado escondido en el usuario ni en un encabezado.
urlpatterns = [
    path('', WorkspaceListCreateView.as_view(), name='workspace-list'),
    path('sectores/', SectorListView.as_view(), name='workspace-sectores'),
    path('<slug:slug>/', WorkspaceDetailView.as_view(), name='workspace-detail'),
    path('<slug:slug>/members/', MemberListView.as_view(), name='workspace-members'),
    path('<slug:slug>/members/<int:pk>/', MemberDetailView.as_view(), name='workspace-member-detail'),
    path('<slug:slug>/invitations/', InvitationListCreateView.as_view(), name='workspace-invitations'),
    path('<slug:slug>/invitations/<int:pk>/', InvitationDetailView.as_view(), name='workspace-invitation-detail'),
    path(
        '<slug:slug>/invitations/<int:pk>/resend/',
        InvitationResendView.as_view(), name='workspace-invitation-resend',
    ),
]

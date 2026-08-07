"""Las direcciones de la Empresa y de sus Workspaces.

⚠️ **El `<slug>` de la raíz es el de la EMPRESA**, no el de un Workspace. El prefijo sigue
diciendo `workspaces/` porque es el que el frontend ya usa en todas sus pantallas;
renombrarlo a `empresas/` es un cambio de superficie que no le cambia nada a nadie —queda
anotado como deuda, no como urgencia.

Por lo mismo, los Workspaces de adentro cuelgan de `espacios/`: era el nombre que tenían
cuando se escribió esta ruta. La dirección miente, el código no.
"""

from django.urls import path

from .primeros_pasos import PrimerosPasosView
from .views import (
    EmpresaDetailView, EmpresaListCreateView,
    InvitationDetailView, InvitationListCreateView, InvitationResendView,
    MemberDetailView, MemberListView, SectorListView,
    WorkspaceAvailableView, WorkspaceContentView, WorkspaceConversationsView,
    WorkspaceDetailView, WorkspaceListCreateView,
)

urlpatterns = [
    # ── La Empresa ───────────────────────────────────────────────────────────
    path('', EmpresaListCreateView.as_view(), name='empresa-list'),
    path('sectores/', SectorListView.as_view(), name='empresa-sectores'),
    path('<slug:slug>/', EmpresaDetailView.as_view(), name='empresa-detail'),
    path(
        '<slug:slug>/primeros-pasos/',
        PrimerosPasosView.as_view(), name='empresa-primeros-pasos',
    ),
    path('<slug:slug>/members/', MemberListView.as_view(), name='empresa-members'),
    path('<slug:slug>/members/<int:pk>/', MemberDetailView.as_view(), name='empresa-member-detail'),
    path('<slug:slug>/invitations/', InvitationListCreateView.as_view(), name='empresa-invitations'),
    path(
        '<slug:slug>/invitations/<int:pk>/',
        InvitationDetailView.as_view(), name='empresa-invitation-detail',
    ),
    path(
        '<slug:slug>/invitations/<int:pk>/resend/',
        InvitationResendView.as_view(), name='empresa-invitation-resend',
    ),

    # ── Sus Workspaces ───────────────────────────────────────────────────────
    path('<slug:slug>/espacios/', WorkspaceListCreateView.as_view(), name='workspace-list'),
    path(
        '<slug:slug>/espacios/<slug:space_slug>/',
        WorkspaceDetailView.as_view(), name='workspace-detail',
    ),
    path(
        '<slug:slug>/espacios/<slug:space_slug>/disponibles/',
        WorkspaceAvailableView.as_view(), name='workspace-available',
    ),
    path(
        '<slug:slug>/espacios/<slug:space_slug>/conversaciones/',
        WorkspaceConversationsView.as_view(), name='workspace-conversations',
    ),
    path(
        '<slug:slug>/espacios/<slug:space_slug>/<slug:coleccion>/',
        WorkspaceContentView.as_view(), name='workspace-content',
    ),
]

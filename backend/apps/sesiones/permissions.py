"""Quién entra a una Sesión.

Dos niveles encadenados, y el orden importa:

1. **El Workspace**: si no es miembro, ni sabe que la Sesión existe (404, no 403 —
   misma regla que `apps.workspaces.permissions`).
2. **La Sesión**: abierta la ve cualquier miembro del Workspace; restringida, solo
   quien esté agregado. El administrador del Workspace entra siempre como editor,
   porque no puede administrar lo que no ve.

Se resuelve acá y no en cada vista, por lo mismo que los permisos del Workspace viven
en un solo archivo: una regla repetida en seis vistas es una regla que en la séptima
se olvida.
"""
from django.db.models import Q
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.workspaces.models import ROLE_ADMIN
from apps.workspaces.permissions import require_membership

from .models import ROL_EDITOR, VISIBILIDAD_ABIERTA, Sesion


def sesiones_visibles(membership, incluir_archivadas=False, workspace_slug=None):
    """Las Sesiones que este miembro puede ver dentro de su empresa.

    `workspace_slug` acota a un Workspace: es lo que hace que el conmutador de arriba
    signifique algo fuera del chat. Sin él se ven todas las que la persona alcanza, que
    es lo que corresponde cuando eligió "Todos".
    """
    qs = Sesion.objects.filter(workspace__organization=membership.organization)
    if workspace_slug:
        qs = qs.filter(workspace__slug=workspace_slug)
    if not incluir_archivadas:
        qs = qs.filter(archivada=False)
    if membership.role == ROLE_ADMIN:
        return qs.distinct()
    return qs.filter(
        Q(visibility=VISIBILIDAD_ABIERTA) | Q(miembros__user=membership.user)
    ).distinct()


def require_sesion(membership, slug, minimo=None):
    """La Sesión, o 404. Con `minimo=ROL_EDITOR`, 403 si la ve pero no la administra.

    La distinción es la que importa: no verla y no poder administrarla son cosas
    distintas, y mezclarlas le diría a alguien que existe algo que no debería saber
    que existe.
    """
    sesion = (
        Sesion.objects.filter(workspace__organization=membership.organization, slug=slug)
        .select_related('workspace').first()
    )
    if sesion is None or sesion.rol_de(membership.user, membership) is None:
        raise NotFound('Sesión no encontrada.')
    if minimo == ROL_EDITOR and not sesion.alcanza(membership.user, membership, ROL_EDITOR):
        raise PermissionDenied(
            'Solo un editor de esta Sesión puede cambiar su configuración.'
        )
    return sesion


def membership_y_sesion(user, workspace_slug, sesion_slug, minimo=None):
    """Los dos niveles de una vez, que es como los usan todas las vistas."""
    membership = require_membership(user, workspace_slug)
    return membership, require_sesion(membership, sesion_slug, minimo)

"""El punto único de resolución de permisos de Afable.

Regla de diseño de la reconstrucción v1: **toda** consulta a datos de un Workspace
pasa por acá. Los permisos nunca se le piden al modelo dentro del prompt, como
hacía `_get_permissions_context` en el enfoque anterior — si el usuario no tiene
acceso, el dato simplemente no llega a la consulta.

La Etapa 3 agrega en este mismo archivo la resolución de Fuentes visibles
(`Source` con acceso privado/compartido/público más `SourceAccess`), y la Etapa 8
la de Salas, que heredan sus permisos de las Fuentes a las que apuntan. Es a
propósito que vivan juntas: un solo archivo que leer para saber quién ve qué.
"""

from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import BasePermission

from .models import ROLE_ADMIN, ROLE_EDITOR, ROLE_MEMBER, Membership


def resolve_membership(user, workspace_slug):
    """Devuelve la `Membership` del usuario en ese Workspace, o `None`.

    `None` cubre los tres casos sin distinguirlos: usuario anónimo, Workspace que
    no existe, y Workspace que existe pero del que no es miembro. Quien decide qué
    hacer con eso es `require_membership`.
    """
    if not user or not user.is_authenticated:
        return None
    return (
        Membership.objects
        .select_related('workspace', 'user')
        .filter(workspace__slug=workspace_slug, user=user)
        .first()
    )


def require_membership(user, workspace_slug, minimum_role=ROLE_MEMBER):
    """Igual que `resolve_membership`, pero corta la request si no alcanza.

    No ser miembro devuelve 404, no 403: para quien está afuera, el Workspace no
    existe. Un 403 confirmaría que el slug es real y filtraría los nombres de los
    Workspace de otras empresas.
    """
    membership = resolve_membership(user, workspace_slug)
    if membership is None:
        raise NotFound('Workspace no encontrado.')
    if not membership.has_at_least(minimum_role):
        raise PermissionDenied('No tiene permisos suficientes en este Workspace.')
    return membership


def workspaces_of(user):
    """Los Workspace de los que el usuario es miembro, para el conmutador."""
    if not user or not user.is_authenticated:
        return Membership.objects.none()
    return (
        Membership.objects
        .select_related('workspace')
        .filter(user=user)
        .order_by('workspace__name')
    )


def is_admin_anywhere(user):
    """Puente para el código anterior a la Etapa 1, que preguntaba por `User.org_admin`.

    Ese campo era un booleano global de plataforma. Acá se traduce a "es administrador
    de al menos un Workspace". Es una equivalencia floja **a propósito temporal**: cada
    pantalla que se rehace pasa a resolver el permiso contra SU Workspace con
    `require_membership`, y cuando no quede ningún llamador esta función se borra.
    """
    if not user or not user.is_authenticated:
        return False
    return Membership.objects.filter(user=user, role=ROLE_ADMIN).exists()


class WorkspaceRolePermission(BasePermission):
    """Base de los permisos DRF. Espera `slug` en los kwargs de la vista.

    Deja `request.membership` y `request.workspace` puestos para que la vista no
    tenga que volver a consultar, y para que sea evidente en el código de la vista
    que el acceso ya está resuelto.
    """

    minimum_role = ROLE_MEMBER

    def has_permission(self, request, view):
        slug = view.kwargs.get('slug')
        if not slug:
            return False
        membership = require_membership(request.user, slug, self.minimum_role)
        request.membership = membership
        request.workspace = membership.workspace
        return True


class IsMember(WorkspaceRolePermission):
    minimum_role = ROLE_MEMBER


class IsEditor(WorkspaceRolePermission):
    minimum_role = ROLE_EDITOR


class IsAdmin(WorkspaceRolePermission):
    minimum_role = ROLE_ADMIN

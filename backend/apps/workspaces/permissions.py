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

from .models import (
    ROLE_ADMIN, ROLE_EDITOR, ROLE_MEMBER,
    VISIBILITY_OPEN, Membership, Space,
)


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


def spaces_visible_to(membership):
    """Los Espacios que ese miembro puede ver dentro de su Workspace.

    Abiertos, más los restringidos donde está agregado. El administrador los ve
    todos: no puede administrar lo que no aparece en la lista.
    """
    if membership is None:
        return Space.objects.none()
    todos = Space.objects.filter(workspace=membership.workspace)
    if membership.role == ROLE_ADMIN:
        return todos.distinct()
    from django.db.models import Q
    return todos.filter(
        Q(visibility=VISIBILITY_OPEN) | Q(members=membership.user)
    ).distinct()


def require_space(membership, space_slug):
    """El Espacio, o 404. Mismo criterio que el Workspace: si no lo ve, no existe."""
    espacio = spaces_visible_to(membership).filter(slug=space_slug).first()
    if espacio is None:
        raise NotFound('Espacio no encontrado.')
    return espacio


def sources_visible_to(membership):
    """Las fuentes (conexiones y documentos) que alcanza ese miembro, vía Espacios.

    Devuelve `(conexiones, documentos)`. Es la consulta que tiene que usar el
    agente antes de armar el contexto: lo que no sale de acá no entra al prompt.
    """
    from apps.organizations.models import CompanyDocument, SystemConnection

    espacios = spaces_visible_to(membership)
    if membership is None:
        return SystemConnection.objects.none(), CompanyDocument.objects.none()
    return (
        SystemConnection.objects.filter(spaces__in=espacios).distinct(),
        CompanyDocument.objects.filter(spaces__in=espacios).distinct(),
    )


def alcance_de_agente(agent):
    """Qué fuentes alcanza este agente, según los Espacios a los que pertenece.

    Devuelve `(ids_de_conexiones, ids_de_documentos)`. **`None` en cualquiera de
    los dos significa "sin restricción"**, y es a propósito: un agente que no está
    en ningún Espacio sigue viendo todo lo de su empresa, como antes de que los
    Espacios existieran. Si los Espacios restringieran también a los agentes que
    nadie asignó, instalar esta función dejaría a toda la instalación existente
    con agentes que de golpe no saben nada.

    Un agente que SÍ está en Espacios queda encerrado en la unión de sus fuentes,
    aunque esa unión sea vacía: ahí el silencio es la respuesta correcta.
    """
    if agent is None or not agent.pk:
        return None, None

    espacios = list(agent.spaces.all())
    if not espacios:
        return None, None

    conexiones = set()
    documentos = set()
    for espacio in espacios:
        conexiones.update(espacio.connections.values_list('id', flat=True))
        documentos.update(espacio.documents.values_list('id', flat=True))
    return list(conexiones), list(documentos)


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

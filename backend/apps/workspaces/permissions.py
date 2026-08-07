"""El punto único de resolución de permisos de Afable.

Regla de diseño de la reconstrucción v1: **toda** consulta a datos de una empresa pasa por
acá. Los permisos nunca se le piden al modelo dentro del prompt — si la persona no tiene
acceso, el dato simplemente no llega a la consulta.

⭐ **Dos preguntas, no una** (desde el 2026-08-06, con los tres niveles):

1. **¿Pertenece a la empresa, y con qué rol?** → `Membership`, que cuelga de la Empresa.
   El rol (miembro / editor / administrador) es de la empresa entera.
2. **¿Entra a este Workspace?** → si es abierto, entra cualquiera de la empresa; si es
   restringido, sólo quien esté agregado. El administrador entra a todos: no puede
   administrar lo que no ve.

Partirlo así evita el permiso que nadie sabe explicar ("editor en Ventas, miembro en
Finanzas, ¿puede borrar este archivo?"). El rol dice qué **puede hacer**; el Workspace dice
sobre **qué**.
"""

from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import BasePermission

from .models import (
    ROLE_ADMIN, ROLE_EDITOR, ROLE_MEMBER,
    VISIBILITY_OPEN, Membership, Workspace,
)


def resolve_membership(user, empresa_slug):
    """Devuelve la `Membership` del usuario en esa Empresa, o `None`.

    `None` cubre los tres casos sin distinguirlos: usuario anónimo, empresa que no existe,
    y empresa que existe pero de la que no es miembro. Quién decide qué hacer con eso es
    `require_membership`.
    """
    if not user or not user.is_authenticated:
        return None
    return (
        Membership.objects
        .select_related('organization', 'user')
        .filter(organization__slug=empresa_slug, user=user)
        .first()
    )


def membership_por_organizacion(user, org):
    """La `Membership` de esta persona en esa empresa, o `None`.

    Existe porque hay código que sólo tiene la `Organization` a mano —el armado del prompt
    del agente, por ejemplo— y necesita saber el rol para resolver permisos.
    """
    if not user or not user.is_authenticated or org is None:
        return None
    return (
        Membership.objects
        .select_related('organization', 'user')
        .filter(organization=org, user=user)
        .first()
    )


def require_membership(user, empresa_slug, minimum_role=ROLE_MEMBER):
    """Igual que `resolve_membership`, pero corta la request si no alcanza.

    No ser miembro devuelve 404, no 403: para quien está afuera, la empresa no existe. Un
    403 confirmaría que el slug es real y filtraría los nombres de las empresas ajenas.
    """
    membership = resolve_membership(user, empresa_slug)
    if membership is None:
        raise NotFound('Empresa no encontrada.')
    if not membership.has_at_least(minimum_role):
        raise PermissionDenied('No tiene permisos suficientes en esta empresa.')
    return membership


def empresas_of(user):
    """Las empresas de las que la persona es miembro, para el conmutador."""
    if not user or not user.is_authenticated:
        return Membership.objects.none()
    return (
        Membership.objects
        .select_related('organization')
        .filter(user=user)
        .order_by('organization__name')
    )


# Nombre anterior, mientras quede código llamándolo.
workspaces_of = empresas_of


def is_admin_anywhere(user):
    """Puente para el código anterior a la Etapa 1, que preguntaba por `User.org_admin`.

    Ese campo era un booleano global de plataforma. Acá se traduce a "es administrador de
    al menos una empresa".
    """
    if not user or not user.is_authenticated:
        return False
    return Membership.objects.filter(user=user, role=ROLE_ADMIN).exists()


def workspaces_visible_to(membership):
    """Los Workspaces que esa persona puede ver dentro de su empresa.

    Los abiertos, más los restringidos donde está agregada. El administrador los ve todos:
    no puede administrar lo que no aparece en la lista.
    """
    if membership is None:
        return Workspace.objects.none()
    todos = Workspace.objects.filter(organization=membership.organization)
    if membership.role == ROLE_ADMIN:
        return todos.distinct()
    from django.db.models import Q
    return todos.filter(
        Q(visibility=VISIBILITY_OPEN) | Q(members=membership.user)
    ).distinct()


def require_workspace(membership, workspace_slug):
    """El Workspace, o 404. Mismo criterio que la empresa: si no lo ve, no existe."""
    workspace = workspaces_visible_to(membership).filter(slug=workspace_slug).first()
    if workspace is None:
        raise NotFound('Workspace no encontrado.')
    return workspace


def sources_visible_to(membership):
    """Las fuentes (conexiones y documentos) que alcanza esa persona, vía sus Workspaces.

    Devuelve `(conexiones, documentos)`. Es la consulta que tiene que usar el agente antes
    de armar el contexto: lo que no sale de acá no entra al prompt.
    """
    from apps.organizations.models import CompanyDocument, SystemConnection

    if membership is None:
        return SystemConnection.objects.none(), CompanyDocument.objects.none()
    visibles = workspaces_visible_to(membership)
    return (
        SystemConnection.objects.filter(workspaces__in=visibles).distinct(),
        CompanyDocument.objects.filter(workspaces__in=visibles).distinct(),
    )


def alcance_de_agente(agent):
    """Qué fuentes alcanza este agente, según los Workspaces a los que pertenece.

    Devuelve `(ids_de_conexiones, ids_de_documentos)`. **`None` en cualquiera de los dos
    significa "sin restricción"**, y es a propósito: un agente que no está en ningún
    Workspace sigue viendo todo lo de su empresa. Si los Workspaces restringieran también a
    los agentes que nadie asignó, instalar esta función dejaría a toda la instalación
    existente con agentes que de golpe no saben nada.

    Un agente que SÍ está en Workspaces queda encerrado en la unión de sus fuentes, aunque
    esa unión sea vacía: ahí el silencio es la respuesta correcta.
    """
    if agent is None or not agent.pk:
        return None, None

    workspaces = list(agent.workspaces.all())
    if not workspaces:
        return None, None

    conexiones = set()
    documentos = set()
    for ws in workspaces:
        conexiones.update(ws.connections.values_list('id', flat=True))
        documentos.update(ws.documents.values_list('id', flat=True))
    return list(conexiones), list(documentos)


class EmpresaRolePermission(BasePermission):
    """Base de los permisos DRF. Espera `slug` (el de la Empresa) en los kwargs.

    Deja `request.membership` y `request.empresa` puestos para que la vista no tenga que
    volver a consultar, y para que sea evidente en el código que el acceso ya está resuelto.
    """

    minimum_role = ROLE_MEMBER

    def has_permission(self, request, view):
        slug = view.kwargs.get('slug')
        if not slug:
            return False
        membership = require_membership(request.user, slug, self.minimum_role)
        request.membership = membership
        request.empresa = membership.organization
        # Alias mientras quede código escrito cuando el Workspace era la empresa.
        request.workspace = membership.organization
        return True


class IsMember(EmpresaRolePermission):
    minimum_role = ROLE_MEMBER


class IsEditor(EmpresaRolePermission):
    minimum_role = ROLE_EDITOR


class IsAdmin(EmpresaRolePermission):
    minimum_role = ROLE_ADMIN


# Nombre anterior de la clase base.
WorkspaceRolePermission = EmpresaRolePermission

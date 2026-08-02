"""La galería de Agentes de la vista Trabajo.

Es lo que alimenta "Chatear con…": las pestañas **Favoritos · Todos · Editables por
mí**, el buscador, el orden y el scroll infinito. Vive en su propio archivo porque
`views.py` de esta app ya carga con el chat, los documentos y los disparadores.

Alcance: los agentes de la Organization enlazada al Workspace activo. Mientras dure
el puente hacia la app anterior (ver `Workspace.organization`), el Workspace llega
por slug y de ahí se resuelve la Organization; así el permiso se sigue evaluando en
`apps/workspaces/permissions.py` y no acá.
"""

from django.db.models import Count, Exists, OuterRef, Q
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.workspaces.models import ROLE_ADMIN, ROLE_EDITOR
from apps.workspaces.permissions import require_membership, require_space

from .models import Agent, AgentFavorite

TAMANO_PAGINA = 12

ORDENES = {
    'popularidad': ('-popularidad', 'name'),
    'nombre': ('name',),
    'reciente': ('-created_at',),
}


def puede_editar_agentes(membership):
    """Si esta persona puede crear y editar agentes en su Workspace.

    Lo decide `Workspace.agent_creation_policy` cruzado con su rol. Un
    administrador siempre puede.
    """
    politica = membership.workspace.agent_creation_policy
    if membership.role == ROLE_ADMIN:
        return True
    if politica == 'todos':
        return True
    if politica == 'editores':
        return membership.role == ROLE_EDITOR
    return False


def serializar(agent, editable):
    autor = agent.created_by
    return {
        'id': agent.id,
        'name': agent.name,
        'description': agent.description,
        'area': agent.area,
        'author': (autor.get_full_name() or autor.email) if autor else 'Afable',
        'is_favorite': agent.es_favorito,
        'editable': editable,
        'conversations': agent.popularidad,
        'recommended_frequency': agent.recommended_frequency,
        'tools_summary': agent.tools_summary,
    }


class AgentGalleryView(APIView):
    """GET /api/v1/agents/gallery/?workspace=<slug>&espacio=&tab=&q=&orden=&page=

    `espacio` acota a los agentes de ese Espacio. Es lo que permite decir "estoy
    trabajando en Finanzas" y ver solo los agentes de Finanzas, en vez del catálogo
    entero de la empresa.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        slug = request.query_params.get('workspace')
        if not slug:
            return Response({'detail': 'Falta el Workspace.'}, status=status.HTTP_400_BAD_REQUEST)

        membership = require_membership(request.user, slug)
        organization_id = membership.workspace.organization_id
        editable = puede_editar_agentes(membership)

        favoritos = AgentFavorite.objects.filter(user=request.user, agent=OuterRef('pk'))
        agentes = (
            Agent.objects
            .filter(organization_id=organization_id, is_active=True)
            .select_related('created_by')
            .annotate(
                popularidad=Count('conversations', distinct=True),
                es_favorito=Exists(favoritos),
            )
        )

        espacio_slug = (request.query_params.get('espacio') or '').strip()
        if espacio_slug:
            # `require_space` corta con 404 si no lo ve: pedir los agentes de un
            # Espacio restringido ajeno no puede devolver la lista.
            espacio = require_space(membership, espacio_slug)
            agentes = agentes.filter(spaces=espacio)

        tab = request.query_params.get('tab', 'todos')
        if tab == 'favoritos':
            agentes = agentes.filter(es_favorito=True)
        elif tab == 'editables':
            # Sin permiso para editar, la pestaña queda vacía en vez de mentir.
            agentes = agentes.filter(created_by=request.user) if editable else agentes.none()

        q = (request.query_params.get('q') or '').strip()
        if q:
            agentes = agentes.filter(Q(name__icontains=q) | Q(description__icontains=q))

        agentes = agentes.order_by(*ORDENES.get(request.query_params.get('orden'), ORDENES['popularidad']))

        try:
            page = max(1, int(request.query_params.get('page', 1)))
        except ValueError:
            page = 1
        desde = (page - 1) * TAMANO_PAGINA
        total = agentes.count()
        pagina = list(agentes[desde:desde + TAMANO_PAGINA])

        return Response({
            'count': total,
            'page': page,
            'has_next': desde + len(pagina) < total,
            'can_create': editable,
            'results': [serializar(a, editable and (a.created_by_id == request.user.id)) for a in pagina],
        })


class AgentFavoriteView(APIView):
    """Marcar y desmarcar favorito. POST agrega, DELETE quita."""

    permission_classes = [IsAuthenticated]

    def _agente_visible(self, request, pk):
        slug = request.query_params.get('workspace') or request.data.get('workspace')
        if not slug:
            return None, Response({'detail': 'Falta el Workspace.'}, status=status.HTTP_400_BAD_REQUEST)
        membership = require_membership(request.user, slug)
        agent = Agent.objects.filter(pk=pk, organization_id=membership.workspace.organization_id).first()
        if agent is None:
            return None, Response({'detail': 'Agente no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        return agent, None

    def post(self, request, pk):
        agent, error = self._agente_visible(request, pk)
        if error:
            return error
        AgentFavorite.objects.get_or_create(user=request.user, agent=agent)
        return Response({'is_favorite': True})

    def delete(self, request, pk):
        agent, error = self._agente_visible(request, pk)
        if error:
            return error
        AgentFavorite.objects.filter(user=request.user, agent=agent).delete()
        return Response({'is_favorite': False})

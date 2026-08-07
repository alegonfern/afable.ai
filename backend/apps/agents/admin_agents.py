"""Admin › Agentes: configurar lo que la empresa le entrega a cada agente.

El agente llega sabiendo su oficio; lo que no sabe es nada de ESTA empresa. Acá se
le entrega: a qué datos puede mirar, con qué reglas responde y qué le conviene
saber. Es una decisión de la empresa, así que **solo un administrador** entra.

Se separa de `gallery.py` a propósito: esa es la vitrina de la vista Trabajo, esta
es la mesa de configuración de Admin.
"""

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.workspaces.permissions import require_membership
from apps.workspaces.models import ROLE_ADMIN

from .models import Agent, AgentConfig


def _config_de(agent):
    """La configuración del agente, creándola vacía la primera vez.

    Es lo que hace que un agente recién cargado al Workspace **aparezca solo** como
    pendiente en Admin, sin que nadie tenga que crear nada a mano.
    """
    config, _ = AgentConfig.objects.get_or_create(agent=agent)
    return config


def serializar(agent, config, detalle=False):
    datos = {
        'id': agent.id,
        'name': agent.name,
        'description': agent.description,
        'area': agent.area,
        'configurado': config.esta_configurado,
        'updated_at': config.updated_at,
    }
    if detalle:
        datos.update({
            'datos': config.datos,
            'reglas': config.reglas,
            'info_util': config.info_util,
            'instructions': agent.instructions,
            'tools_summary': agent.tools_summary,
        })
    return datos


class AgentesAdminListView(APIView):
    """GET /api/v1/agents/admin/?workspace=<slug> — todos los agentes y su estado."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        slug = request.query_params.get('workspace')
        if not slug:
            return Response({'detail': 'Falta el Workspace.'}, status=status.HTTP_400_BAD_REQUEST)

        membership = require_membership(request.user, slug, minimum_role=ROLE_ADMIN)
        agentes = (
            Agent.objects
            .filter(organization_id=membership.organization_id, is_active=True)
            .order_by('name')
        )

        resultados = [serializar(a, _config_de(a)) for a in agentes]
        return Response({
            'count': len(resultados),
            'pendientes': sum(1 for r in resultados if not r['configurado']),
            'results': resultados,
        })


class AgenteAdminDetailView(APIView):
    """GET y PATCH de la configuración de un agente."""

    permission_classes = [IsAuthenticated]

    def _agente(self, request, pk):
        slug = request.query_params.get('workspace') or request.data.get('workspace')
        if not slug:
            return None, None, Response(
                {'detail': 'Falta el Workspace.'}, status=status.HTTP_400_BAD_REQUEST,
            )
        membership = require_membership(request.user, slug, minimum_role=ROLE_ADMIN)
        agent = Agent.objects.filter(
            pk=pk, organization_id=membership.organization_id,
        ).first()
        if agent is None:
            return None, None, Response(
                {'detail': 'Agente no encontrado.'}, status=status.HTTP_404_NOT_FOUND,
            )
        return agent, _config_de(agent), None

    def get(self, request, pk):
        agent, config, error = self._agente(request, pk)
        if error:
            return error
        return Response(serializar(agent, config, detalle=True))

    def patch(self, request, pk):
        agent, config, error = self._agente(request, pk)
        if error:
            return error

        for campo in ('datos', 'reglas', 'info_util'):
            if campo in request.data:
                setattr(config, campo, (request.data.get(campo) or '').strip())

        # Queda "configurado" en cuanto se le entregó algo. Vaciarlo todo lo devuelve
        # a pendiente: es información de la empresa, no una casilla que se marca.
        tiene_algo = any([config.datos, config.reglas, config.info_util])
        if tiene_algo and not config.completed_at:
            config.completed_at = timezone.now()
        elif not tiene_algo:
            config.completed_at = None

        config.updated_by = request.user
        config.save()
        return Response(serializar(agent, config, detalle=True))

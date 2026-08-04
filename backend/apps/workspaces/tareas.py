"""Tareas del Espacio: el pendiente que una persona o un agente puede tomar.

El Espacio ya tenia fuentes, agentes, personas y las conversaciones del equipo. Lo
que no tenia era donde anotar el trabajo que todavia no se hizo, asi que cada
pendiente vivia fuera de Afable, en la cabeza de alguien o en otra herramienta.

Lo que separa esto de un tablero de tareas cualquiera: **un agente puede tomar una
tarea y ejecutarla**. La descripcion es su instruccion, el resultado queda guardado
en la tarea, y el equipo lo lee sin abrir ninguna conversacion.

Permisos: los del Espacio y nada mas. Cualquier miembro del Espacio crea, edita y
completa tareas — son items de trabajo livianos, no configuracion de la empresa. Lo
unico que se comprueba aparte es que el agente asignado sea uno que el Espacio
alcanza (si no, ejecutar una tarea seria la forma de hacer trabajar a un agente que
no me corresponde).
"""

import logging

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import TAREA_ESTADOS, TAREA_LISTA, TAREA_PENDIENTE, Task
from .permissions import IsMember, require_space

logger = logging.getLogger(__name__)

# Pendientes primero, listas al final: la lista se lee para saber que falta.
PRIORIDAD_DE_ESTADO = {'pendiente': 0, 'en_curso': 1, 'lista': 2}

MAX_RESULTADO = 8000


def serializar(tarea):
    return {
        'id': tarea.id,
        'title': tarea.title,
        'description': tarea.description,
        'state': tarea.state,
        'assignee': tarea.assignee_id,
        'assignee_name': (
            (tarea.assignee.get_full_name() or tarea.assignee.email) if tarea.assignee else None
        ),
        'agent': tarea.agent_id,
        'agent_name': tarea.agent.name if tarea.agent else None,
        'resultado': tarea.resultado,
        'resultado_error': tarea.resultado_error,
        'ejecutada_at': tarea.ejecutada_at,
        'author': (
            (tarea.created_by.get_full_name() or tarea.created_by.email)
            if tarea.created_by else None
        ),
        'created_at': tarea.created_at,
    }


def _ordenadas(qs):
    """Por estado (pendiente → en curso → lista) y dentro de cada uno, lo mas nuevo.

    El orden se arma aca y no en el `Meta` del modelo porque ahi `state` se ordenaria
    por su texto, o sea 'en_curso' < 'lista' < 'pendiente': las tareas ya hechas antes
    que las que faltan.
    """
    from django.db.models import Case, IntegerField, Value, When

    return qs.annotate(
        prioridad=Case(
            *[When(state=e, then=Value(p)) for e, p in PRIORIDAD_DE_ESTADO.items()],
            default=Value(9), output_field=IntegerField(),
        )
    ).order_by('prioridad', '-created_at')


def _agente_del_espacio(espacio, agent_id):
    """El agente que se le puede asignar a una tarea de este Espacio.

    Devuelve (agente, error). Un agente que el Espacio no alcanza no se asigna: si
    no, asignar y ejecutar seria la manera de poner a trabajar a un agente ajeno con
    su propio acceso a datos.

    Un Espacio sin agentes propios acepta cualquier agente de la empresa, por la misma
    razon que `alcance_de_agente` no restringe a un agente sin Espacios: si no, los
    Espacios que ya existen se quedan sin poder asignar nada.
    """
    from apps.agents.models import Agent

    if agent_id in (None, '', 0):
        return None, None
    de_la_empresa = Agent.objects.filter(
        organization_id=espacio.workspace.organization_id, pk=agent_id, is_active=True,
    )
    propios = espacio.agents.all()
    agente = (
        de_la_empresa.filter(pk__in=propios.values('pk')).first()
        if propios.exists()
        else de_la_empresa.first()
    )
    if agente is None:
        return None, 'Ese agente no está disponible en este Espacio.'
    return agente, None


def _persona_del_espacio(espacio, user_id):
    """La persona a la que se le puede asignar: cualquier miembro del Workspace.

    No se exige que este en `space.members` porque en un Espacio abierto esa lista
    esta vacia y entran todos: exigirla dejaria sin poder asignar a nadie justo en el
    caso mas comun.
    """
    from .models import Membership

    if user_id in (None, '', 0):
        return None, None
    membership = Membership.objects.filter(
        workspace=espacio.workspace, user_id=user_id,
    ).select_related('user').first()
    if membership is None:
        return None, 'Esa persona no es parte de este Workspace.'
    return membership.user, None


class TareaListCreateView(APIView):
    """GET y POST /api/v1/workspaces/<slug>/espacios/<space_slug>/tareas/"""

    permission_classes = [IsAuthenticated, IsMember]

    def get(self, request, slug, space_slug):
        espacio = require_space(request.membership, space_slug)
        tareas = _ordenadas(
            Task.objects.filter(space=espacio).select_related('assignee', 'agent', 'created_by')
        )
        pendientes = sum(1 for t in tareas if t.state != TAREA_LISTA)
        return Response({
            'count': len(tareas),
            'pendientes': pendientes,
            'results': [serializar(t) for t in tareas],
        })

    def post(self, request, slug, space_slug):
        espacio = require_space(request.membership, space_slug)

        title = (request.data.get('title') or '').strip()[:255]
        if not title:
            return Response(
                {'detail': 'La tarea necesita un título.'}, status=status.HTTP_400_BAD_REQUEST,
            )

        agente, error = _agente_del_espacio(espacio, request.data.get('agent'))
        if error:
            return Response({'detail': error}, status=status.HTTP_400_BAD_REQUEST)
        persona, error = _persona_del_espacio(espacio, request.data.get('assignee'))
        if error:
            return Response({'detail': error}, status=status.HTTP_400_BAD_REQUEST)

        tarea = Task.objects.create(
            space=espacio,
            title=title,
            description=(request.data.get('description') or '').strip(),
            agent=agente,
            assignee=persona,
            created_by=request.user,
        )
        return Response(serializar(tarea), status=status.HTTP_201_CREATED)


class TareaDetailView(APIView):
    """PATCH y DELETE de una tarea."""

    permission_classes = [IsAuthenticated, IsMember]

    def _tarea(self, request, space_slug, pk):
        espacio = require_space(request.membership, space_slug)
        tarea = Task.objects.filter(space=espacio, pk=pk).first()
        if tarea is None:
            return None, None, Response(
                {'detail': 'Tarea no encontrada.'}, status=status.HTTP_404_NOT_FOUND,
            )
        return tarea, espacio, None

    def patch(self, request, slug, space_slug, pk):
        tarea, espacio, error = self._tarea(request, space_slug, pk)
        if error:
            return error

        if 'title' in request.data:
            title = (request.data.get('title') or '').strip()[:255]
            if not title:
                return Response(
                    {'detail': 'La tarea necesita un título.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            tarea.title = title
        if 'description' in request.data:
            tarea.description = (request.data.get('description') or '').strip()
        if 'state' in request.data:
            estado = request.data.get('state')
            if estado not in dict(TAREA_ESTADOS):
                return Response(
                    {'detail': f'Estado desconocido: {estado}.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            tarea.state = estado
        if 'agent' in request.data:
            agente, err = _agente_del_espacio(espacio, request.data.get('agent'))
            if err:
                return Response({'detail': err}, status=status.HTTP_400_BAD_REQUEST)
            tarea.agent = agente
        if 'assignee' in request.data:
            persona, err = _persona_del_espacio(espacio, request.data.get('assignee'))
            if err:
                return Response({'detail': err}, status=status.HTTP_400_BAD_REQUEST)
            tarea.assignee = persona

        tarea.save()
        return Response(serializar(tarea))

    def delete(self, request, slug, space_slug, pk):
        tarea, _, error = self._tarea(request, space_slug, pk)
        if error:
            return error
        tarea.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TareaEjecutarView(APIView):
    """POST .../tareas/<pk>/ejecutar/ — el agente asignado hace la tarea.

    Corre el MISMO agente del chat, con el mismo contexto: el resultado es igual al
    que daria preguntarselo a mano. Se reusa `automation_runner._run_prompt` a
    proposito — un segundo camino de ejecucion daria respuestas distintas segun por
    donde se pidio, que es exactamente el problema que ese modulo evita.

    Sincronico, como el "ejecutar ahora" de las Automatizaciones: la llamada al modelo
    puede tardar, y quien apreta el boton esta esperando el resultado.
    """

    permission_classes = [IsAuthenticated, IsMember]

    def post(self, request, slug, space_slug, pk):
        espacio = require_space(request.membership, space_slug)
        tarea = Task.objects.filter(space=espacio, pk=pk).select_related('agent').first()
        if tarea is None:
            return Response(
                {'detail': 'Tarea no encontrada.'}, status=status.HTTP_404_NOT_FOUND,
            )
        if tarea.agent is None:
            return Response(
                {'detail': 'Asígnale un agente antes de pedirle que la haga.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        instruccion = (tarea.description or '').strip() or tarea.title
        organization = espacio.workspace.organization
        if organization is None:
            return Response(
                {'detail': 'Este Workspace todavía no está enlazado a una empresa.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Se marca en curso ANTES de llamar al modelo: la llamada tarda, y sin esto la
        # tarea se ve pendiente mientras alguien mas podria apretar ejecutar de nuevo.
        Task.objects.filter(pk=tarea.pk).update(state='en_curso')

        from services.automation_runner import _run_prompt

        try:
            # El agente corre con el contexto de SU dueño de empresa, igual que en las
            # Automatizaciones: es quien tiene la Organization enlazada.
            salida = _run_prompt(organization.owner, organization, instruccion, tarea.agent)
        except Exception as e:
            logger.exception('Fallo la ejecucion de la tarea %s', tarea.pk)
            tarea.refresh_from_db()
            tarea.state = TAREA_PENDIENTE
            tarea.resultado_error = str(e)[:500]
            tarea.save(update_fields=['state', 'resultado_error', 'updated_at'])
            return Response(
                {'detail': 'El agente no pudo completar la tarea.', **serializar(tarea)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        tarea.refresh_from_db()
        tarea.resultado = (salida or '')[:MAX_RESULTADO]
        tarea.resultado_error = ''
        tarea.ejecutada_at = timezone.now()
        # Queda LISTA, no pendiente: el agente ya la hizo. Si el resultado no sirve,
        # se vuelve a pendiente a mano — es una decision de la persona, no del agente.
        tarea.state = TAREA_LISTA
        tarea.save(update_fields=[
            'resultado', 'resultado_error', 'ejecutada_at', 'state', 'updated_at',
        ])
        return Response(serializar(tarea))

"""Tareas de la Sesión: el pendiente que toma una persona o un agente.

Nacieron colgadas del Espacio y se mudaron acá, que es su lugar: el pendiente es del
trabajo (la Sesión), no del contenedor de permisos (el Espacio).

Lo que separa esto de un tablero de tareas cualquiera: **un agente puede tomar una
tarea y ejecutarla**. La descripción es su instrucción, el resultado queda guardado en
la tarea, y el equipo lo lee sin abrir ninguna conversación.

Permisos: los de la Sesión, resueltos en `permissions.py`. Cualquier miembro crea,
edita y completa tareas — son items de trabajo livianos, no configuración. Lo único
que se comprueba aparte es que el agente asignado sea uno de la empresa.
"""

import logging

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.workspaces.permissions import require_membership

from .models import TAREA_ESTADOS, TAREA_LISTA, TAREA_PENDIENTE, Task
from .permissions import require_sesion

logger = logging.getLogger(__name__)

# Pendientes primero, listas al final: la lista se lee para saber qué falta.
PRIORIDAD_DE_ESTADO = {'pendiente': 0, 'en_curso': 1, 'lista': 2}

MAX_RESULTADO = 8000


def serializar(tarea, quien=None, con_sesion=False):
    """`con_sesion` agrega de qué Sesión es.

    Solo hace falta en la vista que cruza Sesiones: dentro de una Sesión el dato es el
    encabezado de la pantalla y repetirlo en cada fila sería ruido.
    """
    datos = {
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
        'es_mia': tarea.assignee_id == quien.id if quien is not None else None,
        'created_at': tarea.created_at,
    }
    if con_sesion:
        datos['sesion'] = {
            'slug': tarea.sesion.slug, 'name': tarea.sesion.name,
            'archivada': tarea.sesion.archivada,
        }
    return datos


def _ordenadas(qs):
    """Por estado (pendiente → en curso → lista) y dentro de cada uno, lo más nuevo.

    El orden se arma acá y no en el `Meta` del modelo porque ahí `state` se ordenaría
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


def resolver(request, sesion_slug):
    """Los dos niveles de permiso: el Workspace y después la Sesión.

    Devuelve (sesion, error). El Workspace llega por `?workspace=` o en el cuerpo,
    igual que en el resto de la API.
    """
    slug = request.query_params.get('workspace') or request.data.get('workspace')
    if not slug:
        return None, Response(
            {'detail': 'Falta el Workspace.'}, status=status.HTTP_400_BAD_REQUEST,
        )
    membership = require_membership(request.user, slug)
    return require_sesion(membership, sesion_slug), None


def _agente(sesion, agent_id):
    """El agente que se le puede asignar a una tarea. Devuelve (agente, error).

    Solo de la empresa de esta Sesión: asignar y ejecutar sería la forma de poner a
    trabajar a un agente ajeno con su propio acceso a datos.
    """
    from apps.agents.models import Agent

    if agent_id in (None, '', 0):
        return None, None
    org_id = sesion.workspace.organization_id
    agente = Agent.objects.filter(organization_id=org_id, pk=agent_id, is_active=True).first()
    if agente is None:
        return None, 'Ese agente no está disponible en esta empresa.'
    return agente, None


def _persona(sesion, user_id):
    """La persona a la que se le puede asignar: cualquier miembro del Workspace.

    No se exige que esté agregada a la Sesión porque en una Sesión abierta esa lista
    está vacía y entran todos: exigirla dejaría sin poder asignar a nadie justo en el
    caso más común.
    """
    from apps.workspaces.models import Membership

    if user_id in (None, '', 0):
        return None, None
    membership = Membership.objects.filter(
        workspace=sesion.workspace, user_id=user_id,
    ).select_related('user').first()
    if membership is None:
        return None, 'Esa persona no es parte de este Workspace.'
    return membership.user, None


class TareaListCreateView(APIView):
    """GET y POST /api/v1/sesiones/<sesion_slug>/tareas/?workspace=<slug>

    `mias=1` deja solo las asignadas a quien pregunta (el "Mine / Everyone" de la
    pantalla) y `estado=` filtra por estado (`abiertas` = todo lo que no está listo).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, sesion_slug):
        sesion, error = resolver(request, sesion_slug)
        if error:
            return error

        qs = Task.objects.filter(sesion=sesion).select_related('assignee', 'agent', 'created_by')
        if request.query_params.get('mias') in ('1', 'true'):
            qs = qs.filter(assignee=request.user)
        estado = request.query_params.get('estado')
        if estado == 'abiertas':
            qs = qs.exclude(state=TAREA_LISTA)
        elif estado in dict(TAREA_ESTADOS):
            qs = qs.filter(state=estado)

        tareas = list(_ordenadas(qs))
        return Response({
            'count': len(tareas),
            'pendientes': sum(1 for t in tareas if t.state != TAREA_LISTA),
            'results': [serializar(t, request.user) for t in tareas],
        })

    def post(self, request, sesion_slug):
        sesion, error = resolver(request, sesion_slug)
        if error:
            return error

        title = (request.data.get('title') or '').strip()[:255]
        if not title:
            return Response(
                {'detail': 'La tarea necesita un título.'}, status=status.HTTP_400_BAD_REQUEST,
            )

        agente, err = _agente(sesion, request.data.get('agent'))
        if err:
            return Response({'detail': err}, status=status.HTTP_400_BAD_REQUEST)
        persona, err = _persona(sesion, request.data.get('assignee'))
        if err:
            return Response({'detail': err}, status=status.HTTP_400_BAD_REQUEST)

        tarea = Task.objects.create(
            sesion=sesion,
            title=title,
            description=(request.data.get('description') or '').strip(),
            agent=agente,
            assignee=persona,
            created_by=request.user,
        )
        return Response(serializar(tarea, request.user), status=status.HTTP_201_CREATED)


class TareaDetailView(APIView):
    """PATCH y DELETE de una tarea."""

    permission_classes = [IsAuthenticated]

    def _tarea(self, request, sesion_slug, pk):
        sesion, error = resolver(request, sesion_slug)
        if error:
            return None, None, error
        tarea = Task.objects.filter(sesion=sesion, pk=pk).first()
        if tarea is None:
            return None, None, Response(
                {'detail': 'Tarea no encontrada.'}, status=status.HTTP_404_NOT_FOUND,
            )
        return tarea, sesion, None

    def patch(self, request, sesion_slug, pk):
        tarea, sesion, error = self._tarea(request, sesion_slug, pk)
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
            agente, err = _agente(sesion, request.data.get('agent'))
            if err:
                return Response({'detail': err}, status=status.HTTP_400_BAD_REQUEST)
            tarea.agent = agente
        if 'assignee' in request.data:
            persona, err = _persona(sesion, request.data.get('assignee'))
            if err:
                return Response({'detail': err}, status=status.HTTP_400_BAD_REQUEST)
            tarea.assignee = persona

        tarea.save()
        return Response(serializar(tarea, request.user))

    def delete(self, request, sesion_slug, pk):
        tarea, _, error = self._tarea(request, sesion_slug, pk)
        if error:
            return error
        tarea.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TareaEjecutarView(APIView):
    """POST .../tareas/<pk>/ejecutar/ — el agente asignado hace la tarea.

    Corre el MISMO agente del chat, con el mismo contexto: el resultado es igual al que
    daría preguntárselo a mano. Se reusa `automation_runner._run_prompt` a propósito —
    un segundo camino de ejecución daría respuestas distintas según por dónde se pidió.

    Sincrónico, como el "ejecutar ahora" de las Automatizaciones: la llamada al modelo
    puede tardar y quien aprieta el botón está esperando el resultado.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, sesion_slug, pk):
        sesion, error = resolver(request, sesion_slug)
        if error:
            return error
        tarea = Task.objects.filter(sesion=sesion, pk=pk).select_related('agent').first()
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
        organization = sesion.workspace.organization
        if organization is None:
            return Response(
                {'detail': 'Este Workspace todavía no está enlazado a una empresa.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Se marca en curso ANTES de llamar al modelo: la llamada tarda, y sin esto la
        # tarea se ve pendiente mientras alguien más podría apretar ejecutar de nuevo.
        Task.objects.filter(pk=tarea.pk).update(state='en_curso')

        from services.automation_runner import _run_prompt

        try:
            # El agente corre con el contexto del dueño de la empresa, igual que en las
            # Automatizaciones: es quien tiene la Organization enlazada.
            salida = _run_prompt(organization.owner, organization, instruccion, tarea.agent)
        except Exception as e:
            logger.exception('Fallo la ejecucion de la tarea %s', tarea.pk)
            tarea.refresh_from_db()
            tarea.state = TAREA_PENDIENTE
            tarea.resultado_error = str(e)[:500]
            tarea.save(update_fields=['state', 'resultado_error', 'updated_at'])
            return Response(
                {'detail': 'El agente no pudo completar la tarea.',
                 **serializar(tarea, request.user)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        tarea.refresh_from_db()
        tarea.resultado = (salida or '')[:MAX_RESULTADO]
        tarea.resultado_error = ''
        tarea.ejecutada_at = timezone.now()
        # Queda LISTA, no pendiente: el agente ya la hizo. Si el resultado no sirve, se
        # vuelve a pendiente a mano — es una decisión de la persona, no del agente.
        tarea.state = TAREA_LISTA
        tarea.save(update_fields=[
            'resultado', 'resultado_error', 'ejecutada_at', 'state', 'updated_at',
        ])
        return Response(serializar(tarea, request.user))


class TareasDelWorkspaceView(APIView):
    """GET /api/v1/tareas/?workspace=<slug> — TODAS las tareas, cruzando Sesiones.

    Es la pantalla que faltaba. Las tareas solo existían adentro de su Sesión, cuatro
    niveles adentro de la barra lateral, así que la pregunta que uno se hace de verdad
    —"¿qué tengo pendiente?"— no se podía contestar sin abrir Sesión por Sesión y acordarse
    de todas. Una tarea que hay que ir a buscar no es un pendiente: es un papel perdido.

    Solo las Sesiones que la persona ve (`sesiones_visibles`), que es el mismo embudo que
    usa la barra lateral. Sin eso, una vista que cruza Sesiones sería la forma de leer las
    tareas de una Sesión restringida.

    `mias=1` deja las asignadas a quien pregunta, `estado=` filtra igual que dentro de una
    Sesión, y `agente=1` deja solo las que tiene que ejecutar un agente.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        slug = request.query_params.get('workspace')
        if not slug:
            return Response(
                {'detail': 'Falta el Workspace.'}, status=status.HTTP_400_BAD_REQUEST,
            )
        membership = require_membership(request.user, slug)

        from .permissions import sesiones_visibles

        # Las archivadas quedan afuera: una Sesión archivada es trabajo cerrado, y sus
        # pendientes en la lista de pendientes serían ruido permanente.
        visibles = sesiones_visibles(membership)
        qs = Task.objects.filter(sesion__in=visibles).select_related(
            'assignee', 'agent', 'created_by', 'sesion',
        )

        if request.query_params.get('mias') in ('1', 'true'):
            qs = qs.filter(assignee=request.user)
        if request.query_params.get('agente') in ('1', 'true'):
            qs = qs.filter(agent__isnull=False)

        estado = request.query_params.get('estado')
        if estado == 'abiertas':
            qs = qs.exclude(state=TAREA_LISTA)
        elif estado in dict(TAREA_ESTADOS):
            qs = qs.filter(state=estado)

        tareas = list(_ordenadas(qs))

        # Los contadores salen SIN los filtros de estado y de a quién: son los que pintan
        # las pestañas, y una pestaña que cuenta solo lo que ya está filtrado no sirve para
        # decidir a cuál ir.
        todas = Task.objects.filter(sesion__in=visibles)
        return Response({
            'count': len(tareas),
            'totales': {
                'todas': todas.count(),
                'pendientes': todas.exclude(state=TAREA_LISTA).count(),
                'mias': todas.filter(assignee=request.user).exclude(state=TAREA_LISTA).count(),
                'de_agentes': todas.filter(agent__isnull=False).exclude(state=TAREA_LISTA).count(),
            },
            'results': [serializar(t, request.user, con_sesion=True) for t in tareas],
        })

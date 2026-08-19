"""El feed de una Sesión: lo que pasó ahí, sin importar de qué tipo sea.

La idea que se copia del cuadro de referencia: **una tarea y una conversación son el
mismo tipo de item en la lista**. Las dos son "algo que alguien empezó, con respuestas
debajo". Separarlas en dos listas obliga a mirar en dos lados para saber qué pasó.

Se agrupan por tiempo (hoy / esta semana / este mes / antes) porque una Sesión se lee
para ponerse al día, no para buscar algo puntual — para eso está el buscador.
"""
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Task
from .tareas import resolver

# Saludos que rotan en el título, como en el cuadro de referencia. No es adorno: le
# pone cara a una pantalla que si no arranca con un formulario vacío.
SALUDOS = [
    'buen día',
    '¿qué se cocina hoy?',
    'a trabajar',
    '¿en qué andamos?',
    'aquí estamos',
    'manos a la obra',
]


def _grupo(fecha, ahora):
    dias = (ahora.date() - fecha.date()).days
    if dias <= 0:
        return 'Hoy'
    if dias == 1:
        return 'Ayer'
    if dias < 7:
        return 'Esta semana'
    if dias < 30:
        return 'Este mes'
    return 'Antes'


ORDEN_DE_GRUPOS = ['Hoy', 'Ayer', 'Esta semana', 'Este mes', 'Antes']


class FeedView(APIView):
    """GET /api/v1/sesiones/<sesion_slug>/feed/?workspace=<slug>

    Devuelve los items ya agrupados: el frontend los dibuja, no los ordena.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, sesion_slug):
        sesion, error = resolver(request, sesion_slug)
        if error:
            return error

        from apps.agents.models import Conversation

        ahora = timezone.localtime()
        items = []

        conversaciones = (
            Conversation.objects.filter(sesion=sesion)
            .select_related('user', 'agent')
            .prefetch_related('messages')
        )
        for c in conversaciones:
            mensajes = list(c.messages.all())
            respuestas = [m for m in mensajes if m.role == 'assistant']
            ultima = max(mensajes, key=lambda m: m.created_at) if mensajes else None
            items.append({
                'tipo': 'conversacion',
                'id': c.id,
                'titulo': c.title or 'Conversación',
                'detalle': (mensajes[0].content[:180] if mensajes else ''),
                'autor': (c.user.get_full_name() or c.user.email) if c.user else None,
                # Una conversación que abrió el agente no es "mía" aunque figure a mi
                # nombre: nadie la escribió.
                'es_mio': c.user_id == request.user.id and not c.autonoma,
                'agente': c.agent.name if c.agent else None,
                # La abrió el agente por su cuenta, sin que nadie preguntara. Es la
                # diferencia que hay que poder ver en la lista: "lo escribió alguien"
                # contra "lo trajo un agente solo".
                'autonoma': c.autonoma,
                'respuestas': len(respuestas),
                'ultima_de': (
                    (ultima.agent.name if ultima.agent else None)
                    if ultima and ultima.role == 'assistant' else None
                ),
                'cuando': c.updated_at,
            })

        tareas = Task.objects.filter(sesion=sesion).select_related(
            'created_by', 'agent', 'assignee',
        )
        for t in tareas:
            items.append({
                'tipo': 'tarea',
                'id': t.id,
                'titulo': t.title,
                'detalle': (t.description or '')[:180],
                'autor': (
                    (t.created_by.get_full_name() or t.created_by.email)
                    if t.created_by else None
                ),
                'es_mio': t.assignee_id == request.user.id,
                'agente': t.agent.name if t.agent else None,
                # La anotó un agente: `created_by` vacío con un agente puesto.
                'autonoma': t.created_by_id is None and t.agent_id is not None,
                # Un resultado del agente es la "respuesta" de una tarea: es lo que la
                # vuelve equivalente a una conversación en la lista.
                'respuestas': 1 if t.resultado else 0,
                'ultima_de': (t.agent.name if (t.resultado and t.agent) else None),
                'estado': t.state,
                'cuando': t.updated_at,
            })

        items.sort(key=lambda i: i['cuando'], reverse=True)

        agrupados = {}
        for item in items:
            agrupados.setdefault(_grupo(item['cuando'], ahora), []).append(item)

        return Response({
            # El saludo se elige acá y no en el navegador para que no cambie en cada
            # dibujado de React: rota por día.
            'saludo': SALUDOS[ahora.timetuple().tm_yday % len(SALUDOS)],
            'count': len(items),
            'grupos': [
                {'titulo': g, 'items': agrupados[g]}
                for g in ORDEN_DE_GRUPOS if g in agrupados
            ],
        })

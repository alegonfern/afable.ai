"""Qué hizo Afable mientras usted no estaba.

⭐ **El producto promete que los agentes trabajan solos, y eso ya funciona** —un Disparador
publica en una Sesión y anota la tarea, un agente ejecuta un encargo y deja el resultado—
pero no había ningún lugar donde verlo junto. El trabajo autónomo pasaba desapercibido:
quien abre el lunes ve la misma pantalla del viernes y siente que paga por un chat.

Esto es la evidencia. No inventa nada ni resume con IA: **cuenta lo que quedó registrado**
en cuatro lugares que ya existían, y por eso no puede exagerar.

- Las conversaciones marcadas `autonoma` — las que abrió un agente sin que nadie pidiera.
- Las tareas que **ejecutó un agente** (`ejecutada_at` con agente asignado).
- Las versiones de documentos escritas por un agente (`origen='agente'`).
- Los Disparadores que corrieron en el período.

**Si no hubo nada, no se muestra nada.** Un panel que dice "0 cosas esta semana" es un
recordatorio semanal de que el producto no está haciendo su trabajo; mejor que desaparezca
hasta que tenga algo que contar.
"""

from datetime import timedelta

from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import IsMember, workspaces_visible_to

# Una semana es el período que la gente reconoce sin pensar ("¿qué pasó mientras no
# estuve?"). Se puede pedir otro con `?dias=`.
DIAS_POR_OMISION = 7


def lo_que_hizo(membership, dias=DIAS_POR_OMISION):
    """Lo que los agentes hicieron solos, dentro de lo que esta persona alcanza.

    Sale de los Workspaces que ve: si le mostráramos lo que pasó en un área a la que no
    entra, este resumen sería la forma más tonta de filtrar lo que los permisos cuidan en
    todo el resto de la app.
    """
    from apps.agents.models import Automation, Conversation
    from apps.archivos.models import Version
    from apps.sesiones.models import Task

    desde = timezone.now() - timedelta(days=dias)
    empresa = membership.organization
    visibles = workspaces_visible_to(membership)

    publicaciones = list(
        Conversation.objects
        .filter(
            agent__organization=empresa, autonoma=True, created_at__gte=desde,
            sesion__workspace__in=visibles,
        )
        .select_related('agent', 'sesion')
        .order_by('-created_at')[:20]
    )

    tareas = list(
        Task.objects
        .filter(
            sesion__workspace__in=visibles, ejecutada_at__gte=desde, agent__isnull=False,
        )
        .select_related('agent', 'sesion')
        .order_by('-ejecutada_at')[:20]
    )

    escrituras = list(
        Version.objects
        .filter(document__organization=empresa, origen='agente', created_at__gte=desde)
        .select_related('document', 'agente')
        .order_by('-created_at')[:20]
    )

    disparadores = Automation.objects.filter(
        organization=empresa, last_run_at__gte=desde,
    ).count()

    items = []
    for c in publicaciones:
        items.append({
            'tipo': 'publicacion',
            'titulo': c.title or 'Publicó en una Sesión',
            'donde': c.sesion.name if c.sesion else None,
            'quien': c.agent.name if c.agent else 'un agente',
            'cuando': c.created_at,
            'ruta': f'/app/sesiones/{c.sesion.slug}' if c.sesion else '/app/chat',
        })
    for t in tareas:
        items.append({
            'tipo': 'tarea',
            'titulo': t.title,
            'donde': t.sesion.name if t.sesion else None,
            'quien': t.agent.name if t.agent else 'un agente',
            'cuando': t.ejecutada_at,
            'ruta': f'/app/sesiones/{t.sesion.slug}' if t.sesion else '/app/tareas',
        })
    for v in escrituras:
        items.append({
            'tipo': 'escritura',
            'titulo': v.document.title,
            'donde': None,
            'quien': v.agente.name if v.agente else 'un agente',
            'cuando': v.created_at,
            'ruta': f'/app/archivos/{v.document_id}',
        })

    items.sort(key=lambda i: i['cuando'], reverse=True)

    return {
        'items': items[:12],
        'total': len(items),
        'disparadores_que_corrieron': disparadores,
        'dias': dias,
    }


class LoQueHizoAfableView(APIView):
    """GET: qué hicieron los agentes solos en los últimos días."""

    permission_classes = [IsMember]

    def get(self, request, slug):
        try:
            dias = max(1, min(int(request.query_params.get('dias', DIAS_POR_OMISION)), 90))
        except (TypeError, ValueError):
            dias = DIAS_POR_OMISION
        return Response(lo_que_hizo(request.membership, dias))

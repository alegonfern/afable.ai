"""Quién es `@algo` en un mensaje: un agente, o un compañero.

⭐ **El `@` es la interfaz del producto.** Hasta acá solo resolvía agentes, y además solo
el PRIMERO: escribir "@analisis busca X y @datos hazme el gráfico" hacía contestar a uno y
descartaba al otro en silencio. Y en un hilo de equipo, mencionar a una persona disparaba
igual al agente, porque la regla era "¿hay un @ en el texto?" — o sea que pedirle algo a
un colega hacía hablar a la IA encima.

Un solo módulo para las dos cosas, porque son la misma pregunta hecha sobre el mismo texto
y separarlas garantiza que se contesten distinto.
"""
import logging
import re

from django.utils.text import slugify
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.workspaces.permissions import require_membership

logger = logging.getLogger(__name__)

PATRON_MENCION = re.compile(r'(?:^|\s)@([a-z0-9][a-z0-9-]{0,59})\b', re.IGNORECASE)

# ⚠️ Cuántos agentes pueden contestar un mismo mensaje. Cada uno es una llamada al modelo:
# sin tope, alguien que escribe seis menciones dispara seis consultas y espera un minuto
# sin saber por qué. Tres alcanza para que colaboren y no para que se desboque la cuenta.
MAX_AGENTES = 3


def handles_en(texto):
    """Los `@handle` del texto, en orden y sin repetir."""
    vistos, orden = set(), []
    for m in PATRON_MENCION.finditer(texto or ''):
        h = m.group(1).lower()
        if h not in vistos:
            vistos.add(h)
            orden.append(h)
    return orden


def handle_de_persona(user):
    """Con qué `@` se menciona a alguien. Se deriva del nombre, no se guarda.

    Guardarlo obligaría a resolver colisiones al invitar gente y a migrar a los que ya
    están; derivarlo deja el problema en un solo lugar —acá— y la ambigüedad se resuelve
    avisando a todos los que coincidan, que es lo seguro (ver `personas_mencionadas`).
    """
    if user is None:
        return ''
    nombre = (user.get_full_name() or '').strip()
    if nombre:
        return slugify(nombre)[:60]
    return slugify((user.email or '').split('@')[0])[:60]


def agentes_mencionados(agentes_alcanzables, texto):
    """TODOS los agentes mencionados, en el orden en que aparecen. Tope `MAX_AGENTES`.

    Devolver la lista y no el primero es lo que permite que colaboren en una misma
    conversación: cada uno contesta con SUS instrucciones y SU alcance, que es el sentido
    de tener agentes distintos.
    """
    handles = handles_en(texto)
    if not handles:
        return []
    encontrados = {a.handle: a for a in agentes_alcanzables.filter(handle__in=handles)}
    return [encontrados[h] for h in handles if h in encontrados][:MAX_AGENTES]


def personas_mencionadas(texto, usuarios):
    """Las personas mencionadas entre `usuarios` (los del hilo o la Sesión).

    ⚠️ Si dos personas del mismo equipo derivan el mismo handle, se devuelven LAS DOS. Es
    a propósito: adivinar cuál era haría que un pedido le llegue a quien no correspondía y
    nadie se entere. Que le llegue a dos es ruido; que le llegue al equivocado es un
    trabajo que no se hace.
    """
    handles = set(handles_en(texto))
    if not handles:
        return []
    return [u for u in usuarios if handle_de_persona(u) in handles]


class MencionablesView(APIView):
    """GET /api/v1/agents/mencionables/?workspace=<slug>&sesion=<slug>

    A quién se puede mencionar acá: los agentes y las personas, en una sola lista.

    Van juntos a propósito. Para quien escribe, `@` es UNA cosa —"a quién le hablo"— y no
    dos; separarlo en dos selectores obligaría a saber de antemano si lo que busca es una
    persona o un agente, que es justo lo que el `@` viene a evitar.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        slug = request.query_params.get('workspace')
        if not slug:
            return Response({'detail': 'Falta el Workspace.'}, status=400)

        membership = require_membership(request.user, slug)
        org = membership.organization

        agentes = [
            {
                'tipo': 'agente',
                'handle': a.handle,
                'nombre': a.name,
                'detalle': a.description or '',
                'cara': a.cara,
            }
            for a in org.agents.filter(is_active=True).exclude(handle='').order_by('name')
        ]

        # Las personas solo dentro de una Sesión: en un hilo privado no hay a quién
        # mencionar, y ofrecer nombres ahí prometería un aviso que no va a llegar.
        personas = []
        sesion_slug = (request.query_params.get('sesion') or '').strip()
        if sesion_slug:
            from apps.sesiones.models import Sesion

            sesion = Sesion.objects.filter(
                workspace__organization=org, slug=sesion_slug,
            ).first()
            if sesion is not None:
                personas = [
                    {
                        'tipo': 'persona',
                        'handle': handle_de_persona(u),
                        'nombre': u.get_full_name() or u.email,
                        'detalle': u.email,
                    }
                    for u in sesion.members.all()
                    if u.pk != request.user.pk and handle_de_persona(u)
                ]

        return Response({'mencionables': agentes + personas})

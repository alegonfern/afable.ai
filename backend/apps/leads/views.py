import json
import logging
import re

from django.conf import settings
from django.core.mail import send_mail
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from services.agent_service import chat_direct
from .models import Lead

logger = logging.getLogger(__name__)

# Límites anti-abuso (endpoint público, sin login).
MAX_MESSAGES = 40
MAX_CONTENT_LEN = 4000

# El asistente emite este marcador al final de su mensaje; el usuario nunca lo ve.
# Capturamos el prefijo + un objeto JSON plano (sin llaves anidadas) y consumimos un
# cierre "__" opcional — los modelos a veces lo omiten.
LEAD_MARKER_RE = re.compile(r'__AFABLE_LEAD__\s*(\{[^{}]*\})\s*(?:__)?', re.DOTALL)

SYSTEM_PROMPT = """Eres el asistente de Afable en su sitio web. Afable ofrece dos cosas:

1) PLATAFORMA (autoatención): el producto Afable completo, que el cliente usa por su cuenta \
creando una cuenta y pagando un plan. Conecta sus sistemas (ERP como SAP u Odoo, CRM, bases de \
datos, planillas) y sus archivos, y le da a todo el equipo un asistente que responde con los \
datos reales de la empresa, más tablero y gestión de equipo. Es para cuando el visitante quiere \
CONSULTAR, PREGUNTAR o TRABAJAR con sus datos él mismo.

2) WORKFLOWS: automatizaciones a medida que ARMA EL EQUIPO de Afable con n8n. Son para cuando el \
visitante quiere AUTOMATIZAR UN FLUJO o INTEGRAR sistemas: sincronizar un CRM con otra app, \
disparar una acción cuando pasa algo, mover datos de un lado a otro, procesos entre varias \
herramientas. Estas NO son autoatención: las construye el equipo.

Tu objetivo: en una conversación breve y cálida, entender qué necesita el visitante y \
clasificarlo en PLATAFORMA o WORKFLOW. Habla en español, tono cercano de "tú", mensajes cortos \
(2 a 4 frases) y una sola pregunta a la vez.

Empieza preguntando qué está buscando: usar la plataforma por su cuenta, o automatizar un \
flujo/integración.

Cómo decidir:
- PLATAFORMA: "quiero preguntarle a mis datos", "que mi equipo consulte el ERP", "ver un \
tablero", "chatear con mis sistemas". → Invítalo a crear su cuenta gratis o ver los planes. NO \
le pidas el correo.
- WORKFLOW: "quiero sincronizar mi CRM con...", "que cuando entre un pedido se dispare X", \
"mover datos entre estas apps", "automatizar este proceso". Ejemplo: si menciona un CRM y quiere \
que se conecte/sincronice/actualice solo, es un WORKFLOW, no plataforma. → Consigue su CORREO y \
un resumen claro del flujo que quiere automatizar, para que un especialista lo arme y lo contacte.

MARCADORES (obligatorio; el usuario NUNCA los ve, van al FINAL de tu mensaje, en una sola línea, \
un único objeto JSON):
- Apenas tengas claro el camino, agrega:  __AFABLE_LEAD__{"segment":"saas"}   o   \
__AFABLE_LEAD__{"segment":"workflow"}
- Cuando sea WORKFLOW y ya tengas su correo + un resumen del flujo, agrega en su lugar:
  __AFABLE_LEAD__{"segment":"workflow","ready":true,"email":"correo@dominio.com","summary":"flujo \
que quiere automatizar","name":"nombre si lo dijo","company":"empresa si la dijo"}
  (Incluye name y company solo si los mencionó; si no, omítelos.)

Reglas:
- No inventes datos ni prometas funciones que no existen.
- No le pidas el correo a un visitante de PLATAFORMA.
- El resumen debe describir, en 1 o 2 frases, qué flujo o integración quiere automatizar.
- Nunca escribas mucho: la conversación debe sentirse ágil."""


def _parse_marker(text):
    """Devuelve (texto_limpio, dict_marcador_o_None). Toma la última ocurrencia."""
    matches = list(LEAD_MARKER_RE.finditer(text))
    clean = LEAD_MARKER_RE.sub('', text).strip()
    if not matches:
        return clean, None
    try:
        data = json.loads(matches[-1].group(1))
        return clean, (data if isinstance(data, dict) else None)
    except (json.JSONDecodeError, ValueError):
        return clean, None


def _send_lead_email(lead, history):
    lines = [f'{m.get("role")}: {m.get("content", "")}' for m in history]
    body = (
        f'Nuevo lead capturado por el asistente del sitio (segmento: {lead.segment}).\n\n'
        f'Correo:  {lead.email}\n'
        f'Nombre:  {lead.name or "—"}\n'
        f'Empresa: {lead.company or "—"}\n\n'
        f'Qué necesita:\n{lead.summary}\n\n'
        f'--- Conversación ---\n' + '\n'.join(lines)
    )
    send_mail(
        subject=f'Afable — Nuevo lead: {lead.email}',
        message=body,
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'afable@localhost'),
        recipient_list=[settings.AFABLE_TEAM_EMAIL],
        fail_silently=False,
    )


class LeadChatView(APIView):
    """Chat público de captación en la landing. Sin login, stateless: el cliente
    envía todo el historial en cada request y el backend solo persiste el lead final."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'lead_chat'

    def post(self, request):
        raw = request.data.get('messages')
        if not isinstance(raw, list) or not raw:
            return Response({'detail': 'El campo messages es requerido.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if len(raw) > MAX_MESSAGES:
            return Response({'detail': 'Conversación demasiado larga.'},
                            status=status.HTTP_400_BAD_REQUEST)

        history = []
        for m in raw:
            if not isinstance(m, dict):
                continue
            role = m.get('role')
            content = (m.get('content') or '').strip()
            if role not in ('user', 'assistant') or not content:
                continue
            history.append({'role': role, 'content': content[:MAX_CONTENT_LEN]})

        if not history or history[-1]['role'] != 'user':
            return Response({'detail': 'El último mensaje debe ser del usuario.'},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            raw_reply = chat_direct(history, SYSTEM_PROMPT)
        except Exception:
            logger.exception('LeadChatView: fallo en chat_direct')
            return Response({'detail': 'No se pudo generar la respuesta.'},
                            status=status.HTTP_502_BAD_GATEWAY)

        reply, marker = _parse_marker(raw_reply)
        segment = None
        lead_captured = False

        if marker:
            segment = marker.get('segment')
            if segment == 'workflow' and marker.get('ready') and marker.get('email'):
                full_history = history + [{'role': 'assistant', 'content': reply}]
                lead = Lead.objects.create(
                    email=marker.get('email', '').strip()[:254],
                    name=(marker.get('name') or '').strip()[:160],
                    company=(marker.get('company') or '').strip()[:160],
                    segment='workflow',
                    summary=(marker.get('summary') or '').strip(),
                    transcript=full_history,
                )
                try:
                    _send_lead_email(lead, full_history)
                    lead.emailed = True
                    lead.save(update_fields=['emailed'])
                    lead_captured = True
                except Exception:
                    logger.exception('LeadChatView: fallo al enviar correo del lead %s', lead.id)
                    lead_captured = True  # el lead quedó persistido igual

        # A veces el modelo devuelve solo el marcador y el texto visible queda vacío.
        if not reply:
            reply = ('¡Listo! Registré tu solicitud. Un especialista de Afable te contactará muy '
                     'pronto por correo.') if lead_captured else 'Cuéntame un poco más, por favor.'

        return Response({
            'reply': reply,
            'segment': segment,
            'lead_captured': lead_captured,
        })

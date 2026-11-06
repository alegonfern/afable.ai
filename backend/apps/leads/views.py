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

# Actualizado el 14-10-2026 al enfoque nuevo (ver `Memoria/RESUMEN.md`) y el 25-10-2026 con
# los módulos de hoy y los proyectos de IA a medida (la última sección de la landing). Los segmentos
# del marcador se mantienen para no tocar el modelo `Lead`: "saas" = quiere probarlo por su
# cuenta; "workflow" = quiere que el equipo lo contacte.
SYSTEM_PROMPT = """Eres el asistente de Afable en su sitio web.

Qué es Afable: un ERP que se opera con IA ("Opere su empresa con IA. El ERP que las personas quieren usar."). Se maneja desde un chat: el cliente factura, analiza y revisa todo lo de su empresa pidiéndolo en el chat. Sus módulos son VENTAS (cotizaciones, órdenes de venta, entregas, facturación, clientes), COMPRAS (solicitudes, órdenes de compra, recepciones, proveedores, inventario), CONTABILIDAD (documentos, impuestos y F29, conciliación, categorías, proyectos) y FINANZAS (caja, por cobrar, por pagar), y cada módulo tiene sus AUTOMATIZACIONES: tareas repetitivas que Afable hace solo. Se conecta a los sistemas que la empresa ya usa; no obliga a dejarlos.

Además, el equipo de Afable hace PROYECTOS DE IMPLEMENTACIÓN DE IA A MEDIDA: para empresas que quieren agregar IA a sus procesos.

Tu objetivo: en una conversación breve y cálida, responder lo que pregunte el visitante sobre Afable y llevarlo a uno de dos caminos:
- PROBARLO: quiere usarlo por su cuenta. → Invítalo a crear su cuenta. NO le pidas el correo.
- CONTACTO: quiere una demostración, conversar con el equipo, que lo ayuden a ponerlo en marcha o un proyecto de IA a medida. → Consigue su CORREO y un resumen de lo que necesita, para que el equipo lo contacte.

Habla en español neutro, trata al visitante de USTED (nunca "tú" ni voseo), mensajes cortos (2 a 4 frases) y una sola pregunta a la vez.

MARCADORES (obligatorio; el usuario NUNCA los ve, van al FINAL de tu mensaje, en una sola línea, un único objeto JSON):
- Apenas tengas claro el camino, agrega:  __AFABLE_LEAD__{"segment":"saas"}   (probarlo)   o   __AFABLE_LEAD__{"segment":"workflow"}   (contacto)
- Cuando sea CONTACTO y ya tengas su correo + un resumen de lo que necesita, agrega en su lugar:
  __AFABLE_LEAD__{"segment":"workflow","ready":true,"email":"correo@dominio.com","summary":"lo que necesita","name":"nombre si lo dijo","company":"empresa si la dijo"}
  (Incluye name y company solo si los mencionó; si no, omítelos.)

Reglas:
- No inventes datos ni prometas funciones que no existen. Si preguntan por algo fuera de los módulos, di cuáles son los módulos de hoy y que, si lo que necesita es a medida, el equipo puede conversarlo como proyecto de implementación de IA.
- No inventes precios: si preguntan, ofrece que el equipo lo contacte.
- No le pidas el correo a quien solo quiere probarlo.
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
            # Sin empresa a propósito: lo usa un visitante de la landing. El gasto es
            # real igual y queda anotado con motivo 'lead', sin dueño a quien cobrarle.
            raw_reply = chat_direct(history, SYSTEM_PROMPT, motivo='lead')
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
            reply = ('Listo, registré su solicitud. El equipo de Afable lo contactará muy '
                     'pronto por correo.') if lead_captured else 'Cuénteme un poco más, por favor.'

        return Response({
            'reply': reply,
            'segment': segment,
            'lead_captured': lead_captured,
        })

"""Avisos por WhatsApp (22-10-2026), por la API oficial de Meta (WhatsApp Cloud API).

Un mensaje que inicia la empresa (no una respuesta dentro de las 24 horas de una conversación
abierta por la persona) solo se puede mandar con una plantilla aprobada por Meta. La de los
avisos de Afable tiene dos variables en el cuerpo: {{1}} el título y {{2}} el detalle.

Igual que `avisos.avisar`: enviar NUNCA voltea lo que lo provocó. Si falla, queda en el log y
se devuelve False.
"""

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

MAX_VARIABLE = 900          # Meta corta las variables de plantilla largas


def configurado():
    return bool(settings.WHATSAPP_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID)


def enviar(telefono, titulo, detalle):
    """Manda el aviso al número (solo dígitos, con código de país). Devuelve True si Meta lo aceptó."""
    if not configurado() or not telefono:
        return False
    url = (f'https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}/'
           f'{settings.WHATSAPP_PHONE_NUMBER_ID}/messages')
    cuerpo = {
        'messaging_product': 'whatsapp',
        'to': telefono,
        'type': 'template',
        'template': {
            'name': settings.WHATSAPP_PLANTILLA,
            'language': {'code': settings.WHATSAPP_IDIOMA},
            'components': [{'type': 'body', 'parameters': [
                # Las variables no aceptan saltos de línea ni más de 4 espacios seguidos.
                {'type': 'text', 'text': ' '.join(str(titulo).split())[:MAX_VARIABLE]},
                {'type': 'text', 'text': ' '.join(str(detalle).split())[:MAX_VARIABLE]},
            ]}],
        },
    }
    try:
        r = requests.post(url, json=cuerpo, timeout=15,
                          headers={'Authorization': f'Bearer {settings.WHATSAPP_TOKEN}'})
        if r.status_code >= 300:
            logger.warning('WhatsApp rechazó el aviso a %s: %s %s', telefono[-4:], r.status_code, r.text[:300])
            return False
        return True
    except requests.RequestException:
        logger.exception('WhatsApp: no se pudo enviar el aviso')
        return False

"""Las notificaciones también por correo (25-10-2026), por Resend (el SMTP de settings).

No se manda una por cada aviso: si la persona está en Afable, la ve en la campana y la lee. Sale
por correo solo la que sigue SIN LEER pasados unos minutos, una sola vez, y nunca una vieja (si el
corredor estuvo detenido, no se manda de golpe lo de la semana pasada). La revisa el corredor de
automatizaciones en cada vuelta (agents/management/commands/run_automations.py).
"""
import logging
from datetime import timedelta
from html import escape

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

from .models import Notificacion

logger = logging.getLogger(__name__)

ESPERA = timedelta(minutes=10)      # cuánto tiene la persona para verla en la campana
VIGENCIA = timedelta(days=2)        # más vieja que esto ya no se manda


def _html(n, url):
    detalle = f'<p style="margin:0 0 20px;color:#5a5f71;font-size:14px;line-height:1.5">{escape(n.detalle)}</p>' if n.detalle else ''
    return f"""<div style="font-family:Inter,Arial,sans-serif;max-width:520px;margin:0 auto;padding:24px;color:#0b0b0f">
  <p style="margin:0 0 16px;font-weight:700;font-size:16px">Afable</p>
  <div style="border:1px solid #e0e4f1;border-left:4px solid #e5484d;border-radius:12px;padding:20px">
    <p style="margin:0 0 8px;font-size:16px;font-weight:600">{escape(n.titulo)}</p>
    {detalle}
    <a href="{escape(url)}" style="display:inline-block;background:#0b0b0f;color:#fff;text-decoration:none;padding:10px 16px;border-radius:10px;font-size:14px">Ver en Afable</a>
  </div>
  <p style="margin:16px 0 0;font-size:12px;color:#8f95a5">Le llega porque tiene un aviso sin leer en Afable.</p>
</div>"""


def enviar_pendientes(ahora):
    """Manda por correo los avisos sin leer de hace más de ESPERA. Devuelve cuántos mandó."""
    pendientes = (Notificacion.objects.filter(leida=False, correo_enviado_en__isnull=True,
                                              created_at__lte=ahora - ESPERA, created_at__gte=ahora - VIGENCIA)
                  .select_related('user').order_by('created_at')[:50])
    enviados = 0
    for n in pendientes:
        # Se marca antes de mandar: si el envío falla, no se reintenta en cada vuelta para siempre.
        Notificacion.objects.filter(pk=n.pk).update(correo_enviado_en=ahora)
        if not n.user.email:
            continue
        url = settings.FRONTEND_URL.rstrip('/') + (n.enlace or '/app')
        try:
            correo = EmailMultiAlternatives(subject=n.titulo, body=f'{n.titulo}\n\n{n.detalle}\n\nVer en Afable: {url}',
                                            from_email=settings.DEFAULT_FROM_EMAIL, to=[n.user.email])
            correo.attach_alternative(_html(n, url), 'text/html')
            correo.send()
            enviados += 1
        except Exception:
            logger.exception('No se pudo mandar por correo la notificación %s', n.pk)
    return enviados

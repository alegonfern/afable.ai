"""Enviar una cotización u orden por correo, con su PDF. Lo usan el botón «Enviar» de la ficha y la
automatización que le recuerda al cliente una cotización sin respuesta."""

from django.conf import settings
from django.core.mail import EmailMessage

from . import pdf


def enviar(pedido, para, mensaje='', responder_a=None, titulo=None):
    """Manda el correo (lanza la excepción del servidor de correo si falla)."""
    nombre = pdf.titulo_de(pedido)
    titulo = titulo or f'{nombre} {pedido.numero} · {pedido.organization.name}'
    mensaje = mensaje or (
        f'Estimado(a):\n\nAdjuntamos {nombre.lower()} {pedido.numero}.\n\nSaludos,\n{pedido.organization.name}')
    correo = EmailMessage(subject=titulo, body=mensaje, to=[para],
                          from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'afable@localhost'),
                          reply_to=[responder_a] if responder_a else None)
    correo.attach(f'{pedido.numero}.pdf', pdf.generar(pedido), 'application/pdf')
    correo.send(fail_silently=False)

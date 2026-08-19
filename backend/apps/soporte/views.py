"""Recibir un mensaje para soporte y avisarle a quien lo atiende."""

import logging

from django.conf import settings
from django.core.mail import send_mail
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import MensajeSoporte

logger = logging.getLogger(__name__)

# Qué claves del contexto se aceptan. Lista blanca y no "lo que venga": el contexto lo
# arma el navegador, y guardar cualquier cosa que mande el cliente es dejar que alguien
# nos llene la base con lo que quiera.
CLAVES_DE_CONTEXTO = ['ruta', 'empresa', 'workspace', 'modelo', 'errores', 'navegador']

LARGO_MAXIMO = 4000


class MensajeSoporteView(APIView):
    """POST: manda un mensaje a soporte desde adentro de la app."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        texto = (request.data.get('texto') or '').strip()
        if not texto:
            return Response({'detail': 'Escriba qué pasó.'}, status=status.HTTP_400_BAD_REQUEST)
        if len(texto) > LARGO_MAXIMO:
            return Response(
                {'detail': f'El mensaje no puede pasar de {LARGO_MAXIMO} caracteres.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = (request.data.get('email') or '').strip() or request.user.email
        crudo = request.data.get('contexto') or {}
        contexto = {k: crudo[k] for k in CLAVES_DE_CONTEXTO if k in crudo}

        organization = None
        membresia = request.user.memberships.select_related('organization').first()
        if membresia:
            organization = membresia.organization

        mensaje = MensajeSoporte.objects.create(
            user=request.user, organization=organization,
            texto=texto, email=email, contexto=contexto,
        )

        # El correo se manda DESPUÉS de guardar y su fallo no se propaga: si el SMTP está
        # caído, el mensaje igual quedó registrado. Perder lo que alguien escribió porque
        # no salió un correo sería la peor forma de atender un problema.
        enviado = self._avisar(mensaje)
        if not enviado:
            logger.warning('Mensaje de soporte %s guardado pero sin avisar por correo.', mensaje.pk)

        return Response(
            {'id': mensaje.pk, 'email': mensaje.email, 'avisado': enviado},
            status=status.HTTP_201_CREATED,
        )

    def _avisar(self, mensaje):
        destino = getattr(settings, 'SOPORTE_EMAIL', '')
        if not destino:
            return False

        quien = mensaje.user.get_full_name() or mensaje.user.email if mensaje.user else 'Alguien'
        empresa = mensaje.organization.name if mensaje.organization else 'sin empresa'
        ctx = mensaje.contexto or {}
        errores = ctx.get('errores') or []

        cuerpo = (
            f'{quien} ({empresa}) escribió a soporte:\n\n'
            f'{mensaje.texto}\n\n'
            f'{"─" * 46}\n'
            f'Responder a: {mensaje.email}\n'
            f'Pantalla:    {ctx.get("ruta", "?")}\n'
            f'Workspace:   {ctx.get("workspace") or "todos"}\n'
            f'Modelo:      {ctx.get("modelo", "?")}\n'
            f'Navegador:   {ctx.get("navegador", "?")}\n'
        )
        if errores:
            cuerpo += '\nÚltimos errores del navegador:\n' + '\n'.join(f'  · {e}' for e in errores[:5])

        try:
            send_mail(
                subject=f'Afable · soporte — {empresa}',
                message=cuerpo,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'afable@localhost'),
                recipient_list=[destino],
                fail_silently=False,
            )
            return True
        except Exception:
            logger.exception('No se pudo avisar del mensaje de soporte %s', mensaje.pk)
            return False

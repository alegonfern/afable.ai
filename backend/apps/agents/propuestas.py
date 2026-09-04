"""Los agentes que Afable propone, y cómo se aceptan.

Reemplaza al formulario en blanco. La pantalla ya no pregunta «¿qué instrucciones le doy a
su agente?» —que es la pregunta que el usuario no técnico no puede contestar— sino que
muestra lo que ya tiene y le ofrece el agente que le corresponde.

## Por qué son tres endpoints y no uno

Redactar una propuesta cuesta una llamada al modelo. Si la lista las redactara todas de
una, abrir la pantalla con seis carpetas candidatas costaría seis llamadas antes de que la
persona mire ninguna. Así que la lista es barata —dice qué carpetas están listas y con
cuánto material— y se redacta **una** cuando alguien la abre.
"""
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.archivos.models import Carpeta
from apps.workspaces.permissions import require_membership
from services.propuestas_de_agente import (
    UMBRAL_DOCUMENTOS,
    _documentos_de,
    carpetas_con_material,
    crear_desde_propuesta,
    redactar,
)

from .builder import NoPuedeCrear, _membership_que_edita


def _slug(request):
    return request.data.get('workspace') or request.query_params.get('workspace')


def _carpeta_de(membership, carpeta_id):
    return Carpeta.objects.filter(
        organization_id=membership.organization_id, pk=carpeta_id,
    ).first()


class PropuestasView(APIView):
    """GET — qué carpetas ya están listas para tener agente."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        slug = _slug(request)
        if not slug:
            return Response({'detail': 'Falta la empresa.'}, status=status.HTTP_400_BAD_REQUEST)
        membership = require_membership(request.user, slug)

        candidatas = carpetas_con_material(membership.organization, request.user, membership)
        return Response({
            'umbral': UMBRAL_DOCUMENTOS,
            'carpetas': [
                {
                    'id': c.pk,
                    'nombre': c.name,
                    'ruta': c.ruta(),
                    'documentos': _documentos_de(c).count(),
                }
                for c in candidatas
            ],
        })


class OrigenesView(APIView):
    """GET — sobre qué puede trabajar un agente nuevo.

    Es lo que reemplaza al formulario en blanco. La regla, precisada el 31-08:

    > ⛔ Sin **material** no hay agente. El material es una carpeta con documentos **o una
    > herramienta conectada**.

    Ninguno de los dos es una pantalla vacía, que es lo que la regla existe para prohibir.
    Las herramientas entran acá porque un agente de Odoo no cuelga de ninguna carpeta —su
    alcance sale de la herramienta— y la ficha de ese conector promete justamente eso. Sin
    esta mitad, la Fase 4 ofrecería un agente que el producto no deja crear.

    Cuando no hay ninguna de las dos cosas, la respuesta viene vacía y la pantalla dice qué
    hacer primero. Es la IA como andamio: el usuario nuevo no ve un formulario que no sabe
    llenar, ve el paso que le falta.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.organizations.models import SystemConnection

        slug = _slug(request)
        if not slug:
            return Response({'detail': 'Falta la empresa.'}, status=status.HTTP_400_BAD_REQUEST)
        membership = require_membership(request.user, slug)

        carpetas = carpetas_con_material(membership.organization, request.user, membership)
        herramientas = SystemConnection.objects.filter(
            organization_id=membership.organization_id, is_active=True,
        )

        return Response({
            'umbral': UMBRAL_DOCUMENTOS,
            'carpetas': [
                {'id': c.pk, 'nombre': c.name, 'ruta': c.ruta(),
                 'documentos': _documentos_de(c).count()}
                for c in carpetas
            ],
            'herramientas': [
                {'id': h.pk, 'nombre': h.name, 'tipo': h.connector_type}
                for h in herramientas
            ],
        })


class RedactarPropuestaView(APIView):
    """POST — qué agente propone Afable para esta carpeta.

    No crea nada: devuelve el borrador para que la persona lo lea, lo corrija si quiere y
    recién entonces acepte.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        slug = _slug(request)
        if not slug:
            return Response({'detail': 'Falta la empresa.'}, status=status.HTTP_400_BAD_REQUEST)
        membership = require_membership(request.user, slug)

        carpeta = _carpeta_de(membership, request.data.get('carpeta'))
        if carpeta is None:
            return Response({'detail': 'No encuentro esa carpeta.'}, status=status.HTTP_404_NOT_FOUND)

        if carpeta not in carpetas_con_material(membership.organization, request.user, membership):
            return Response(
                {'detail': f'Esa carpeta todavía no tiene con qué trabajar. '
                           f'Sube al menos {UMBRAL_DOCUMENTOS} documentos.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(redactar(carpeta))


class AceptarPropuestaView(APIView):
    """POST — crear el agente de esa carpeta.

    Los campos vienen del borrador, con las correcciones que la persona haya hecho. Se
    aceptan editados a propósito: la propuesta es un punto de partida, no una imposición —
    lo que se quería evitar era la **pantalla en blanco**, no que se pueda ajustar.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        slug = _slug(request)
        if not slug:
            return Response({'detail': 'Falta la empresa.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            membership = _membership_que_edita(request.user, slug)
        except NoPuedeCrear as e:
            return Response({'detail': str(e)}, status=status.HTTP_403_FORBIDDEN)

        carpeta = _carpeta_de(membership, request.data.get('carpeta'))
        if carpeta is None:
            return Response({'detail': 'No encuentro esa carpeta.'}, status=status.HTTP_404_NOT_FOUND)

        nombre = (request.data.get('nombre') or '').strip()
        if not nombre:
            return Response(
                {'detail': 'El agente necesita un nombre.'}, status=status.HTTP_400_BAD_REQUEST,
            )

        propuesta = {
            'nombre': nombre,
            'descripcion': (request.data.get('descripcion') or '').strip(),
            'instrucciones': (request.data.get('instrucciones') or '').strip(),
            'icono': (request.data.get('icono') or '').strip()[:8],
        }

        try:
            agente = crear_desde_propuesta(carpeta, request.user, propuesta, membership)
        except PermissionError as e:
            return Response({'detail': str(e)}, status=status.HTTP_403_FORBIDDEN)

        return Response(
            {
                'id': agente.pk,
                'nombre': agente.name,
                'handle': agente.handle,
                'carpeta': carpeta.ruta(),
            },
            status=status.HTTP_201_CREATED,
        )


class RecomendacionesView(APIView):
    """GET — qué le conviene hacer ahora a quien pregunta.

    ⭐ **No llama al modelo ni una vez.** Todo sale de consultas al estado real de la
    empresa. La IA entra recién cuando la persona toca una de estas recomendaciones y el
    texto llega al chat como una pregunta suya.

    Es la diferencia entre acompañar y quemar presupuesto de fondo: un informe automático
    cada mañana es una llamada por empresa y por día que nadie pidió; esto es una consulta
    que se hace cuando alguien abre la pantalla.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from services.recomendaciones import para

        slug = _slug(request)
        if not slug:
            return Response({'detail': 'Falta la empresa.'}, status=status.HTTP_400_BAD_REQUEST)
        membership = require_membership(request.user, slug)

        return Response({
            'recomendaciones': para(membership.organization, request.user, membership),
        })

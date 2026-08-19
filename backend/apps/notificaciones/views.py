"""La campana: lo que le llegó a esta persona, y marcarlo como leído."""
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notificacion

# Cuántas se muestran. La campana es para lo reciente, no un archivo histórico: una lista
# infinita se deja de leer igual que una bandeja de entrada con mil correos.
CUANTAS = 20


def serializar(n):
    return {
        'id': n.id, 'tipo': n.tipo, 'titulo': n.titulo, 'detalle': n.detalle,
        'enlace': n.enlace, 'leida': n.leida, 'created_at': n.created_at,
    }


class NotificacionesView(APIView):
    """GET las últimas de esta persona. POST las marca todas como leídas."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        propias = Notificacion.objects.filter(user=request.user)
        return Response({
            'notificaciones': [serializar(n) for n in propias[:CUANTAS]],
            # El contador va aparte del listado: es sobre TODAS las sin leer, no sobre las
            # veinte que se muestran. Un "3" que en realidad son 40 miente.
            'sin_leer': propias.filter(leida=False).count(),
        })

    def post(self, request):
        Notificacion.objects.filter(user=request.user, leida=False).update(leida=True)
        return Response({'ok': True, 'sin_leer': 0})


class NotificacionView(APIView):
    """POST marca UNA como leída. Solo las propias: no hay forma de tocar las de otro."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        n = Notificacion.objects.filter(user=request.user, pk=pk).first()
        if n is None:
            return Response(
                {'detail': 'No encontrada.'}, status=status.HTTP_404_NOT_FOUND,
            )
        if not n.leida:
            n.leida = True
            n.save(update_fields=['leida'])
        return Response(serializar(n))

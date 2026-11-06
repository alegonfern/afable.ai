"""Conectores: `/api/v1/workspaces/<slug>/conectores/...`.

Ver es de cualquier miembro; sincronizar ahora, de editor; conectar, cambiar opciones y desconectar,
del administrador (la credencial es de la empresa). Las vistas son las mismas para todos los tipos:
lo propio de cada uno está en su módulo (hubspot.py, sii_rcv.py).
"""
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.workspaces.permissions import IsAdmin, IsEditor, IsMember

from . import servicio
from .models import Conexion
from .servicio import ErrorConector

NOMBRES = dict(Conexion.TIPOS)


class _Base(APIView):
    rol_escritura = IsAdmin

    def get_permissions(self):
        if self.request.method in ('GET', 'HEAD', 'OPTIONS'):
            return [IsAuthenticated(), IsMember()]
        return [IsAuthenticated(), self.rol_escritura()]

    def handle_exception(self, exc):
        if isinstance(exc, ErrorConector):
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return super().handle_exception(exc)


def _tipo(tipo):
    if tipo not in NOMBRES:
        raise ErrorConector('Ese conector no existe.')
    return tipo


def _conector(org, tipo, c=None):
    m = servicio.modulo(tipo)
    conectado = bool(c and c.activa)
    return {
        'tipo': tipo, 'nombre': NOMBRES[tipo],
        'estado': 'desconectado' if not conectado else ('error' if c.ultimo_error else 'conectado'),
        'config': {**getattr(m, 'CONFIG_POR_DEFECTO', {}), **(c.config if c else {})},
        'cuenta': c.cuenta if c else {},
        'ultima_sincronizacion': c.ultima_sincronizacion if c else None,
        'ultimo_resultado': c.ultimo_resultado if c else {},
        'ultimo_error': c.ultimo_error if c else '',
        'requisitos': m.requisitos(org) if hasattr(m, 'requisitos') else [],
    }


class ConectoresView(_Base):
    def get(self, request, slug):
        existentes = {c.tipo: c for c in Conexion.objects.filter(organization=request.empresa)}
        return Response([_conector(request.empresa, t, existentes.get(t)) for t in NOMBRES])


class ConectorView(_Base):
    def get(self, request, slug, tipo):
        return Response(_conector(request.empresa, _tipo(tipo), servicio.de(request.empresa, tipo)))

    def patch(self, request, slug, tipo):
        c = servicio.de(request.empresa, _tipo(tipo), crear=True)
        m = servicio.modulo(tipo)
        nueva = dict(request.data.get('config') or {})
        if hasattr(m, 'validar_config'):
            nueva = m.validar_config(nueva)
        c.config = {**c.config, **nueva}
        c.save(update_fields=['config', 'actualizado_en'])
        return Response(_conector(request.empresa, tipo, c))


class ConectarView(_Base):
    def post(self, request, slug, tipo):
        c = servicio.de(request.empresa, _tipo(tipo), crear=True)
        servicio.modulo(tipo).conectar(c, request.data)  # valida con el servicio y deja secreto/cuenta
        c.activa, c.ultimo_error = True, ''
        if not c.creado_por_id:
            c.creado_por = request.user
        c.save()
        return Response(_conector(request.empresa, tipo, c))


class SincronizarView(_Base):
    rol_escritura = IsEditor

    def post(self, request, slug, tipo):
        c = servicio.de(request.empresa, _tipo(tipo))
        if not c or not c.activa:
            raise ErrorConector(f'Primero conecte {NOMBRES[tipo]}.')
        resumen = servicio.sincronizar(c, request.data or {}, request.user)
        return Response({'conector': _conector(request.empresa, tipo, c), 'resumen': resumen})


class DesconectarView(_Base):
    def post(self, request, slug, tipo):
        c = servicio.de(request.empresa, _tipo(tipo))
        if c:
            c.activa = False
            c.guardar_secreto('')
            c.save()
        return Response(_conector(request.empresa, tipo, c))


class HistorialView(_Base):
    def get(self, request, slug, tipo):
        c = servicio.de(request.empresa, _tipo(tipo))
        if not c:
            return Response([])
        return Response([{
            'id': s.id, 'inicio': s.inicio, 'fin': s.fin, 'estado': s.estado, 'automatica': s.automatica,
            'resumen': s.resumen, 'error': s.error, 'usuario': (s.usuario.get_full_name() or s.usuario.email) if s.usuario else '',
        } for s in c.sincronizaciones.select_related('usuario')[:20]])

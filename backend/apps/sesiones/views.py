"""La Sesión: su lista, su ficha y sus ajustes.

Las Tareas y los Archivos viven en sus propios archivos (`tareas.py`, `archivos.py`)
para que este no crezca como creció `apps/agents/views.py`.
"""
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.workspaces.models import ROLE_ADMIN
from apps.workspaces.permissions import require_membership

from .models import (
    ROL_EDITOR, ROL_MIEMBRO, ROLES, TAREA_LISTA, VISIBILIDADES,
    Sesion, SesionMiembro,
)
from .permissions import require_sesion, sesiones_visibles

LARGOS = {'name': 120, 'description': 4000, 'icon': 8}


def serializar(sesion, rol=None, detalle=False):
    datos = {
        'id': sesion.id,
        'name': sesion.name,
        'slug': sesion.slug,
        'description': sesion.description,
        'icon': sesion.icon,
        'visibility': sesion.visibility,
        'archivada': sesion.archivada,
        'mi_rol': rol,
        'puedo_administrar': rol == ROL_EDITOR,
        'updated_at': sesion.updated_at,
    }
    if detalle:
        datos.update({
            'pendientes': sesion.tasks.exclude(state=TAREA_LISTA).count(),
            'miembros': [
                {
                    'id': m.user_id,
                    'name': m.user.get_full_name() or m.user.email,
                    'email': m.user.email,
                    'role': m.role,
                    'joined_at': m.joined_at,
                }
                for m in sesion.miembros.select_related('user')
            ],
        })
    return datos


def _limpiar(datos):
    limpio = {}
    for campo, tope in LARGOS.items():
        if campo in datos:
            valor = datos.get(campo) or ''
            if not isinstance(valor, str):
                valor = str(valor)
            limpio[campo] = valor.strip()[:tope]
    return limpio


class SesionListCreateView(APIView):
    """GET y POST /api/v1/sesiones/?workspace=<slug>"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        slug = request.query_params.get('workspace')
        if not slug:
            return Response({'detail': 'Falta el Workspace.'}, status=status.HTTP_400_BAD_REQUEST)
        membership = require_membership(request.user, slug)

        archivadas = request.query_params.get('archivadas') in ('1', 'true')
        sesiones = sesiones_visibles(membership, incluir_archivadas=archivadas).prefetch_related(
            'miembros__user', 'tasks',
        )
        return Response({
            'count': sesiones.count(),
            'results': [
                serializar(s, s.rol_de(request.user, membership), detalle=True)
                for s in sesiones
            ],
        })

    def post(self, request):
        slug = request.data.get('workspace')
        if not slug:
            return Response({'detail': 'Falta el Workspace.'}, status=status.HTTP_400_BAD_REQUEST)
        membership = require_membership(request.user, slug)

        campos = _limpiar(request.data)
        if not campos.get('name'):
            return Response(
                {'detail': 'La Sesión necesita un nombre.'}, status=status.HTTP_400_BAD_REQUEST,
            )

        visibilidad = request.data.get('visibility')
        if visibilidad and visibilidad not in dict(VISIBILIDADES):
            return Response(
                {'detail': f'Visibilidad desconocida: {visibilidad}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sesion = Sesion.objects.create(
            workspace=membership.workspace, created_by=request.user,
            visibility=visibilidad or 'abierta', **campos,
        )
        # Quien la crea queda editor: si no, nadie podria configurar la Sesion que
        # acaba de abrir (salvo un administrador del Workspace).
        SesionMiembro.objects.create(sesion=sesion, user=request.user, role=ROL_EDITOR)
        return Response(
            serializar(sesion, ROL_EDITOR, detalle=True), status=status.HTTP_201_CREATED,
        )


class SesionDetailView(APIView):
    """GET, PATCH y DELETE de una Sesión."""

    permission_classes = [IsAuthenticated]

    def _resolver(self, request, sesion_slug, minimo=None):
        slug = request.query_params.get('workspace') or request.data.get('workspace')
        if not slug:
            return None, None, Response(
                {'detail': 'Falta el Workspace.'}, status=status.HTTP_400_BAD_REQUEST,
            )
        membership = require_membership(request.user, slug)
        sesion = require_sesion(membership, sesion_slug, minimo)
        return membership, sesion, None

    def get(self, request, sesion_slug):
        membership, sesion, error = self._resolver(request, sesion_slug)
        if error:
            return error
        return Response(
            serializar(sesion, sesion.rol_de(request.user, membership), detalle=True),
        )

    def patch(self, request, sesion_slug):
        membership, sesion, error = self._resolver(request, sesion_slug, minimo=ROL_EDITOR)
        if error:
            return error

        campos = _limpiar(request.data)
        if 'name' in campos and not campos['name']:
            return Response(
                {'detail': 'La Sesión necesita un nombre.'}, status=status.HTTP_400_BAD_REQUEST,
            )
        for campo, valor in campos.items():
            setattr(sesion, campo, valor)

        if 'visibility' in request.data:
            visibilidad = request.data.get('visibility')
            if visibilidad not in dict(VISIBILIDADES):
                return Response(
                    {'detail': f'Visibilidad desconocida: {visibilidad}.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            sesion.visibility = visibilidad

        # Archivar no borra: la Sesion sale de la barra lateral y su contenido queda.
        if 'archivada' in request.data:
            archivar = bool(request.data.get('archivada'))
            sesion.archivada = archivar
            sesion.archivada_at = timezone.now() if archivar else None

        # El slug NO se recalcula al renombrar: es la URL de la Sesión, y cambiarla
        # rompe los enlaces que el equipo ya se pasó.
        sesion.save()
        return Response(
            serializar(sesion, sesion.rol_de(request.user, membership), detalle=True),
        )

    def delete(self, request, sesion_slug):
        """Borra la Sesión con todo lo suyo. Solo un administrador del Workspace.

        Archivar lo puede hacer un editor; borrar se lleva conversaciones, tareas y
        archivos del equipo, así que es una decisión de la empresa.
        """
        slug = request.query_params.get('workspace') or request.data.get('workspace')
        if not slug:
            return Response({'detail': 'Falta el Workspace.'}, status=status.HTTP_400_BAD_REQUEST)
        membership = require_membership(request.user, slug, minimum_role=ROLE_ADMIN)
        sesion = require_sesion(membership, sesion_slug)
        sesion.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SesionMiembrosView(APIView):
    """POST y DELETE de los miembros de una Sesión."""

    permission_classes = [IsAuthenticated]

    def _resolver(self, request, sesion_slug):
        slug = request.query_params.get('workspace') or request.data.get('workspace')
        if not slug:
            return None, None, Response(
                {'detail': 'Falta el Workspace.'}, status=status.HTTP_400_BAD_REQUEST,
            )
        membership = require_membership(request.user, slug)
        sesion = require_sesion(membership, sesion_slug, minimo=ROL_EDITOR)
        return membership, sesion, None

    def post(self, request, sesion_slug):
        membership, sesion, error = self._resolver(request, sesion_slug)
        if error:
            return error

        rol = request.data.get('role') or ROL_MIEMBRO
        if rol not in dict(ROLES):
            return Response(
                {'detail': f'Rol desconocido: {rol}.'}, status=status.HTTP_400_BAD_REQUEST,
            )

        # Solo gente del Workspace: una Sesión no invita a desconocidos, para eso están
        # las invitaciones al Workspace.
        from apps.workspaces.models import Membership

        del_workspace = Membership.objects.filter(
            workspace=membership.workspace, user_id__in=_ids(request.data.get('ids')),
        ).select_related('user')
        if not del_workspace.exists():
            return Response(
                {'detail': 'Esas personas no son parte de este Workspace.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        for m in del_workspace:
            SesionMiembro.objects.update_or_create(
                sesion=sesion, user=m.user, defaults={'role': rol},
            )
        return Response(serializar(sesion, ROL_EDITOR, detalle=True))

    def delete(self, request, sesion_slug):
        membership, sesion, error = self._resolver(request, sesion_slug)
        if error:
            return error
        SesionMiembro.objects.filter(
            sesion=sesion, user_id__in=_ids(request.data.get('ids')),
        ).delete()
        return Response(serializar(sesion, sesion.rol_de(request.user, membership), detalle=True))


class SesionDisponiblesView(APIView):
    """Lo que se le puede agregar a la Sesión: por ahora, la gente del Workspace."""

    permission_classes = [IsAuthenticated]

    def get(self, request, sesion_slug):
        slug = request.query_params.get('workspace')
        if not slug:
            return Response({'detail': 'Falta el Workspace.'}, status=status.HTTP_400_BAD_REQUEST)
        membership = require_membership(request.user, slug)
        sesion = require_sesion(membership, sesion_slug)

        from apps.workspaces.models import Membership

        ya_estan = set(sesion.miembros.values_list('user_id', flat=True))
        personas = Membership.objects.filter(
            workspace=membership.workspace,
        ).exclude(user_id__in=ya_estan).select_related('user')
        return Response({
            'personas': [
                {
                    'id': m.user_id,
                    'name': m.user.get_full_name() or m.user.email,
                    'email': m.user.email,
                }
                for m in personas
            ],
        })


def _ids(valor):
    if not isinstance(valor, (list, tuple)):
        return []
    limpios = []
    for v in valor:
        try:
            limpios.append(int(v))
        except (TypeError, ValueError):
            continue
    return limpios

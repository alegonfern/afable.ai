import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ROLE_ADMIN, Invitation, Membership, Space, Workspace
from .permissions import (
    IsAdmin, IsEditor, IsMember, require_space, spaces_visible_to, workspaces_of,
)
from .serializers import (
    SECTORES,
    InvitationCreateSerializer, InvitationPreviewSerializer, InvitationSerializer,
    MembershipRoleSerializer, MembershipSerializer,
    SpaceDetailSerializer, SpaceListSerializer, SpaceWriteSerializer,
    WorkspaceCreateSerializer, WorkspaceSerializer,
)

logger = logging.getLogger(__name__)


def _send_invitation_email(invitation):
    """Manda el correo de la invitación. Devuelve si salió.

    No se propaga la excepción: la invitación ya existe y el administrador puede
    reenviarla o pasar el link a mano. Si el SMTP no está configurado, el backend
    de correo es la consola (ver settings/base.py) y esto igual devuelve True.
    """
    link = f'{settings.FRONTEND_URL}/invitacion/{invitation.token}'
    quien = None
    if invitation.invited_by:
        quien = invitation.invited_by.get_full_name() or invitation.invited_by.email

    cuerpo = (
        f'{quien or "Alguien"} lo invitó a unirse al Workspace '
        f'"{invitation.workspace.name}" en Afable.\n\n'
        f'Para aceptar la invitación, abra este enlace:\n{link}\n\n'
        f'El enlace vence el {invitation.expires_at.strftime("%d-%m-%Y")}.\n'
    )
    try:
        send_mail(
            subject=f'Afable — Invitación al Workspace {invitation.workspace.name}',
            message=cuerpo,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'afable@localhost'),
            recipient_list=[invitation.email],
            fail_silently=False,
        )
        return True
    except Exception:
        logger.exception('No se pudo enviar la invitación %s', invitation.pk)
        return False


class WorkspaceListCreateView(APIView):
    """Los Workspace del usuario (para el conmutador) y la creación de uno nuevo."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        memberships = workspaces_of(request.user)
        roles = {m.workspace_id: m.role for m in memberships}
        serializer = WorkspaceSerializer(
            [m.workspace for m in memberships], many=True,
            context={'request': request, 'roles': roles},
        )
        return Response(serializer.data)

    def post(self, request):
        serializer = WorkspaceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        workspace = serializer.save()
        workspace.add_member(request.user, ROLE_ADMIN)
        # Puente con la app anterior: el chat, las conexiones y los documentos
        # todavia cuelgan de Organization (ver Workspace.ensure_organization).
        workspace.ensure_organization(request.user)
        workspace.mirror_to_organization()
        return Response(
            WorkspaceSerializer(
                workspace, context={'request': request, 'roles': {workspace.id: ROLE_ADMIN}}
            ).data,
            status=status.HTTP_201_CREATED,
        )


class WorkspaceDetailView(APIView):
    """Ver el Workspace (cualquier miembro) y editarlo (solo administrador)."""

    def get_permissions(self):
        if self.request.method in ('PATCH', 'PUT'):
            return [IsAuthenticated(), IsAdmin()]
        return [IsAuthenticated(), IsMember()]

    def get(self, request, slug):
        return Response(WorkspaceSerializer(request.workspace, context={'request': request}).data)

    def patch(self, request, slug):
        serializer = WorkspaceSerializer(
            request.workspace, data=request.data, partial=True, context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        workspace = serializer.save()
        workspace.mirror_to_organization()
        return Response(serializer.data)


class SectorListView(APIView):
    """Los sectores para el selector. Misma lista que usa la Organization enlazada."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(SECTORES)


class MemberListView(APIView):
    """Admin › Personas, pestaña Miembros."""

    permission_classes = [IsAuthenticated, IsMember]

    def get(self, request, slug):
        memberships = (
            Membership.objects
            .select_related('user')
            .filter(workspace=request.workspace)
            .order_by('joined_at')
        )
        return Response(MembershipSerializer(memberships, many=True, context={'request': request}).data)


class MemberDetailView(APIView):
    """Cambiar el rol de un miembro o sacarlo del Workspace."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def _get_membership(self, request, pk):
        membership = (
            Membership.objects
            .select_related('user')
            .filter(workspace=request.workspace, pk=pk)
            .first()
        )
        if membership is None:
            raise NotFound('Miembro no encontrado.')
        return membership

    def _es_ultimo_admin(self, request, membership):
        if membership.role != ROLE_ADMIN:
            return False
        return Membership.objects.filter(workspace=request.workspace, role=ROLE_ADMIN).count() <= 1

    def patch(self, request, slug, pk):
        membership = self._get_membership(request, pk)

        serializer = MembershipRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        nuevo_rol = serializer.validated_data['role']

        if membership.user_id == request.user.id and nuevo_rol != ROLE_ADMIN:
            return Response(
                {'detail': 'No puede quitarse a sí mismo el rol de administrador.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if nuevo_rol != ROLE_ADMIN and self._es_ultimo_admin(request, membership):
            return Response(
                {'detail': 'El Workspace necesita al menos un administrador.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        membership.role = nuevo_rol
        membership.save(update_fields=['role'])
        return Response(MembershipSerializer(membership, context={'request': request}).data)

    def delete(self, request, slug, pk):
        membership = self._get_membership(request, pk)

        if membership.user_id == request.user.id:
            return Response(
                {'detail': 'No puede sacarse a sí mismo del Workspace.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if self._es_ultimo_admin(request, membership):
            return Response(
                {'detail': 'El Workspace necesita al menos un administrador.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        membership.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class InvitationListCreateView(APIView):
    """Admin › Personas, pestaña Invitaciones, y el botón + Invitar miembros."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request, slug):
        invitations = (
            Invitation.objects
            .select_related('invited_by')
            .filter(workspace=request.workspace, accepted_at__isnull=True, revoked_at__isnull=True)
        )
        return Response(InvitationSerializer(invitations, many=True).data)

    def post(self, request, slug):
        serializer = InvitationCreateSerializer(
            data=request.data, context={'workspace': request.workspace},
        )
        serializer.is_valid(raise_exception=True)

        invitation = Invitation.create_for(
            workspace=request.workspace,
            email=serializer.validated_data['email'],
            role=serializer.validated_data['role'],
            invited_by=request.user,
        )
        enviado = _send_invitation_email(invitation)

        data = InvitationSerializer(invitation).data
        data['emailed'] = enviado
        return Response(data, status=status.HTTP_201_CREATED)


class InvitationDetailView(APIView):
    """Revocar una invitación pendiente."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def delete(self, request, slug, pk):
        invitation = Invitation.objects.filter(workspace=request.workspace, pk=pk).first()
        if invitation is None:
            return Response({'detail': 'Invitación no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        if invitation.accepted_at:
            return Response(
                {'detail': 'La invitación ya fue aceptada.'}, status=status.HTTP_400_BAD_REQUEST,
            )

        invitation.revoked_at = timezone.now()
        invitation.save(update_fields=['revoked_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class InvitationResendView(APIView):
    """Reenviar: token nuevo, plazo nuevo, correo de nuevo. El link viejo muere."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, slug, pk):
        invitation = Invitation.objects.select_related('workspace', 'invited_by').filter(
            workspace=request.workspace, pk=pk, accepted_at__isnull=True, revoked_at__isnull=True,
        ).first()
        if invitation is None:
            return Response(
                {'detail': 'No hay una invitación pendiente con ese identificador.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        invitation.renew()
        enviado = _send_invitation_email(invitation)
        data = InvitationSerializer(invitation).data
        data['emailed'] = enviado
        return Response(data)


class InvitationPreviewView(APIView):
    """Público: qué dice el link de invitación antes de tener sesión."""

    permission_classes = [AllowAny]

    def get(self, request, token):
        invitation = Invitation.objects.select_related('workspace', 'invited_by').filter(
            token=token,
        ).first()
        if invitation is None:
            return Response({'detail': 'Invitación no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(InvitationPreviewSerializer.from_invitation(invitation).data)


class InvitationAcceptView(APIView):
    """Aceptar la invitación con la sesión del invitado."""

    permission_classes = [IsAuthenticated]

    def post(self, request, token):
        invitation = Invitation.objects.select_related('workspace').filter(token=token).first()
        if invitation is None:
            return Response({'detail': 'Invitación no encontrada.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            membership = invitation.accept(request.user)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'workspace': WorkspaceSerializer(
                membership.workspace,
                context={'request': request, 'roles': {membership.workspace_id: membership.role}},
            ).data,
            'role': membership.role,
        })


# ---------------------------------------------------------------------------
# Espacios
# ---------------------------------------------------------------------------

# Qué colección del Espacio toca cada segmento de la URL, y de dónde salen los
# objetos que se pueden enganchar. Todo se filtra por la Organization del
# Workspace: no se puede meter en un Espacio una fuente de otra empresa.
COLECCIONES_DE_ESPACIO = {
    'conexiones': ('connections', 'SystemConnection'),
    'documentos': ('documents', 'CompanyDocument'),
    'agentes': ('agents', 'Agent'),
    'personas': ('members', 'User'),
}


def _queryset_enganchable(nombre_modelo, workspace):
    """Los objetos que ese Workspace tiene derecho a enganchar a un Espacio."""
    from apps.agents.models import Agent
    from apps.organizations.models import CompanyDocument, SystemConnection

    organization = workspace.organization
    if nombre_modelo == 'SystemConnection':
        return SystemConnection.objects.filter(organization=organization)
    if nombre_modelo == 'CompanyDocument':
        return CompanyDocument.objects.filter(organization=organization)
    if nombre_modelo == 'Agent':
        return Agent.objects.filter(organization=organization)
    # Personas: sólo miembros del Workspace.
    return get_user_model().objects.filter(memberships__workspace=workspace)


class SpaceListCreateView(APIView):
    """Contexto › Espacios: la lista, y crear uno nuevo."""

    def get_permissions(self):
        # Ver la lista es de cualquier miembro; crear un Espacio, de editor
        # para arriba: un Espacio nuevo reparte acceso a datos.
        if self.request.method == 'POST':
            return [IsAuthenticated(), IsEditor()]
        return [IsAuthenticated(), IsMember()]

    def get(self, request, slug):
        espacios = spaces_visible_to(request.membership).prefetch_related(
            'connections', 'documents', 'agents', 'members'
        )
        return Response(SpaceListSerializer(espacios, many=True, context={'request': request}).data)

    def post(self, request, slug):
        serializer = SpaceWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        espacio = serializer.save(workspace=request.workspace, created_by=request.user)
        # Quien lo crea queda adentro, si no un Espacio restringido nace sin nadie.
        espacio.members.add(request.user)
        return Response(
            SpaceDetailSerializer(espacio, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class SpaceDetailView(APIView):
    """El Espacio abierto, con sus tres pestañas. Editarlo y borrarlo."""

    permission_classes = [IsAuthenticated, IsMember]

    def get(self, request, slug, space_slug):
        espacio = require_space(request.membership, space_slug)
        return Response(SpaceDetailSerializer(espacio, context={'request': request}).data)

    def patch(self, request, slug, space_slug):
        espacio = require_space(request.membership, space_slug)
        self._exigir_edicion(request)
        serializer = SpaceWriteSerializer(espacio, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(SpaceDetailSerializer(espacio, context={'request': request}).data)

    def delete(self, request, slug, space_slug):
        espacio = require_space(request.membership, space_slug)
        self._exigir_edicion(request)
        espacio.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _exigir_edicion(self, request):
        from rest_framework.exceptions import PermissionDenied

        from .models import ROLE_EDITOR

        if not request.membership.has_at_least(ROLE_EDITOR):
            raise PermissionDenied('Sólo un editor puede cambiar un Espacio.')


class SpaceContentView(APIView):
    """Enganchar y soltar contenido de un Espacio.

    POST agrega, DELETE saca. Un solo endpoint para las cuatro colecciones
    (conexiones, documentos, agentes, personas) porque la operación es la misma
    y así la pantalla no tiene que aprenderse cuatro rutas.
    """

    permission_classes = [IsAuthenticated, IsEditor]

    def post(self, request, slug, space_slug, coleccion):
        espacio, campo, objetos, ids = self._resolver(request, space_slug, coleccion)
        encontrados = list(objetos.filter(pk__in=ids))
        campo.add(*encontrados)
        return Response(SpaceDetailSerializer(espacio, context={'request': request}).data)

    def delete(self, request, slug, space_slug, coleccion):
        espacio, campo, objetos, ids = self._resolver(request, space_slug, coleccion)
        campo.remove(*objetos.filter(pk__in=ids))
        return Response(SpaceDetailSerializer(espacio, context={'request': request}).data)

    def _resolver(self, request, space_slug, coleccion):
        if coleccion not in COLECCIONES_DE_ESPACIO:
            raise NotFound('Esa colección no existe en un Espacio.')
        espacio = require_space(request.membership, space_slug)
        nombre_campo, nombre_modelo = COLECCIONES_DE_ESPACIO[coleccion]
        ids = request.data.get('ids')
        if ids is None:
            ids = [request.data.get('id')] if request.data.get('id') else []
        if not isinstance(ids, list) or not ids:
            raise ValidationError({'ids': 'Mande al menos un id.'})
        objetos = _queryset_enganchable(nombre_modelo, request.workspace)
        return espacio, getattr(espacio, nombre_campo), objetos, ids


class SpaceAvailableView(APIView):
    """Lo que todavía se puede enganchar a este Espacio, para los selectores."""

    permission_classes = [IsAuthenticated, IsEditor]

    def get(self, request, slug, space_slug):
        espacio = require_space(request.membership, space_slug)
        salida = {}
        for coleccion, (nombre_campo, nombre_modelo) in COLECCIONES_DE_ESPACIO.items():
            ya_estan = getattr(espacio, nombre_campo).values_list('pk', flat=True)
            disponibles = _queryset_enganchable(nombre_modelo, request.workspace).exclude(
                pk__in=list(ya_estan)
            )
            salida[coleccion] = [
                {'id': o.pk, 'label': _etiqueta(o, nombre_modelo)} for o in disponibles[:200]
            ]
        return Response(salida)


def _etiqueta(obj, nombre_modelo):
    if nombre_modelo == 'CompanyDocument':
        return obj.title
    if nombre_modelo == 'User':
        return obj.get_full_name() or obj.email
    return obj.name

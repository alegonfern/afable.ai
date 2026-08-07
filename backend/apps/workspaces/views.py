import logging

from django.conf import settings
from django.contrib.auth import get_user_model

from apps.organizations.models import Organization
from django.core.mail import send_mail
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ROLE_ADMIN, Invitation, Membership, Workspace
from .permissions import (
    IsAdmin, IsEditor, IsMember, empresas_of, require_workspace, workspaces_visible_to,
)
from .serializers import (
    SECTORES,
    EmpresaCreateSerializer, EmpresaSerializer,
    InvitationCreateSerializer, InvitationPreviewSerializer, InvitationSerializer,
    MembershipRoleSerializer, MembershipSerializer,
    WorkspaceDetailSerializer, WorkspaceListSerializer, WorkspaceWriteSerializer,
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
        f'{quien or "Alguien"} lo invitó a unirse a la empresa '
        f'"{invitation.organization.name}" en Afable.\n\n'
        f'Para aceptar la invitación, abra este enlace:\n{link}\n\n'
        f'El enlace vence el {invitation.expires_at.strftime("%d-%m-%Y")}.\n'
    )
    try:
        send_mail(
            subject=f'Afable — Invitación a {invitation.organization.name}',
            message=cuerpo,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'afable@localhost'),
            recipient_list=[invitation.email],
            fail_silently=False,
        )
        return True
    except Exception:
        logger.exception('No se pudo enviar la invitación %s', invitation.pk)
        return False


class EmpresaListCreateView(APIView):
    """Las Empresas de la persona (para el conmutador) y la creación de una nueva."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        memberships = empresas_of(request.user)
        roles = {m.organization_id: m.role for m in memberships}
        serializer = EmpresaSerializer(
            [m.organization for m in memberships], many=True,
            context={'request': request, 'roles': roles},
        )
        return Response(serializer.data)

    def post(self, request):
        serializer = EmpresaCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # `crear_para_dueno` deja las tres cosas que hacen falta para trabajar: la
        # empresa, su primer administrador y un Workspace General.
        empresa = Organization.crear_para_dueno(
            request.user, name=serializer.validated_data['name'],
        )
        for campo in ('sector', 'description', 'employees'):
            if serializer.validated_data.get(campo):
                setattr(empresa, campo, serializer.validated_data[campo])
        empresa.save()
        return Response(
            EmpresaSerializer(
                empresa, context={'request': request, 'roles': {empresa.id: ROLE_ADMIN}}
            ).data,
            status=status.HTTP_201_CREATED,
        )


class EmpresaDetailView(APIView):
    """Ver la Empresa (cualquier miembro) y editarla (solo administrador)."""

    def get_permissions(self):
        if self.request.method in ('PATCH', 'PUT'):
            return [IsAuthenticated(), IsAdmin()]
        return [IsAuthenticated(), IsMember()]

    def get(self, request, slug):
        return Response(EmpresaSerializer(request.empresa, context={'request': request}).data)

    def patch(self, request, slug):
        # Ya no hay espejo que mantener: la identidad vive en un solo lugar.
        serializer = EmpresaSerializer(
            request.empresa, data=request.data, partial=True, context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
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
            .filter(organization=request.empresa)
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
            .filter(organization=request.empresa, pk=pk)
            .first()
        )
        if membership is None:
            raise NotFound('Miembro no encontrado.')
        return membership

    def _es_ultimo_admin(self, request, membership):
        if membership.role != ROLE_ADMIN:
            return False
        return Membership.objects.filter(organization=request.empresa, role=ROLE_ADMIN).count() <= 1

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
                {'detail': 'La empresa necesita al menos un administrador.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        membership.role = nuevo_rol
        membership.save(update_fields=['role'])
        return Response(MembershipSerializer(membership, context={'request': request}).data)

    def delete(self, request, slug, pk):
        membership = self._get_membership(request, pk)

        if membership.user_id == request.user.id:
            return Response(
                {'detail': 'No puede sacarse a sí mismo de la empresa.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if self._es_ultimo_admin(request, membership):
            return Response(
                {'detail': 'La empresa necesita al menos un administrador.'},
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
            .filter(organization=request.empresa, accepted_at__isnull=True, revoked_at__isnull=True)
        )
        return Response(InvitationSerializer(invitations, many=True).data)

    def post(self, request, slug):
        serializer = InvitationCreateSerializer(
            data=request.data, context={'empresa': request.empresa},
        )
        serializer.is_valid(raise_exception=True)

        invitation = Invitation.create_for(
            organization=request.empresa,
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
        invitation = Invitation.objects.filter(organization=request.empresa, pk=pk).first()
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
        invitation = Invitation.objects.select_related('organization', 'invited_by').filter(
            organization=request.empresa, pk=pk, accepted_at__isnull=True, revoked_at__isnull=True,
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
        invitation = Invitation.objects.select_related('organization', 'invited_by').filter(
            token=token,
        ).first()
        if invitation is None:
            return Response({'detail': 'Invitación no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(InvitationPreviewSerializer.from_invitation(invitation).data)


class InvitationAcceptView(APIView):
    """Aceptar la invitación con la sesión del invitado."""

    permission_classes = [IsAuthenticated]

    def post(self, request, token):
        invitation = Invitation.objects.select_related('organization').filter(token=token).first()
        if invitation is None:
            return Response({'detail': 'Invitación no encontrada.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            membership = invitation.accept(request.user)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'empresa': EmpresaSerializer(
                membership.organization,
                context={'request': request, 'roles': {membership.organization_id: membership.role}},
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


def _queryset_enganchable(nombre_modelo, organization):
    """Lo que esa Empresa tiene derecho a enganchar a uno de sus Workspaces."""
    from apps.agents.models import Agent
    from apps.organizations.models import CompanyDocument, SystemConnection

    if nombre_modelo == 'SystemConnection':
        return SystemConnection.objects.filter(organization=organization)
    if nombre_modelo == 'CompanyDocument':
        return CompanyDocument.objects.filter(organization=organization)
    if nombre_modelo == 'Agent':
        return Agent.objects.filter(organization=organization)
    # Personas: sólo miembros del Workspace.
    return get_user_model().objects.filter(memberships__organization=organization)


class WorkspaceListCreateView(APIView):
    """Contexto › Espacios: la lista, y crear uno nuevo."""

    def get_permissions(self):
        # Ver la lista es de cualquier miembro; crear un Espacio, de editor
        # para arriba: un Espacio nuevo reparte acceso a datos.
        if self.request.method == 'POST':
            return [IsAuthenticated(), IsEditor()]
        return [IsAuthenticated(), IsMember()]

    def get(self, request, slug):
        espacios = workspaces_visible_to(request.membership).prefetch_related(
            'connections', 'documents', 'agents', 'members'
        )
        return Response(WorkspaceListSerializer(espacios, many=True, context={'request': request}).data)

    def post(self, request, slug):
        serializer = WorkspaceWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        espacio = serializer.save(organization=request.empresa, created_by=request.user)
        # Quien lo crea queda adentro, si no un Espacio restringido nace sin nadie.
        espacio.members.add(request.user)
        return Response(
            WorkspaceDetailSerializer(espacio, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class WorkspaceDetailView(APIView):
    """El Espacio abierto, con sus tres pestañas. Editarlo y borrarlo."""

    permission_classes = [IsAuthenticated, IsMember]

    def get(self, request, slug, space_slug):
        espacio = require_workspace(request.membership, space_slug)
        return Response(WorkspaceDetailSerializer(espacio, context={'request': request}).data)

    def patch(self, request, slug, space_slug):
        espacio = require_workspace(request.membership, space_slug)
        self._exigir_edicion(request)
        serializer = WorkspaceWriteSerializer(espacio, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(WorkspaceDetailSerializer(espacio, context={'request': request}).data)

    def delete(self, request, slug, space_slug):
        espacio = require_workspace(request.membership, space_slug)
        self._exigir_edicion(request)
        espacio.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _exigir_edicion(self, request):
        from rest_framework.exceptions import PermissionDenied

        from .models import ROLE_EDITOR

        if not request.membership.has_at_least(ROLE_EDITOR):
            raise PermissionDenied('Sólo un editor puede cambiar un Espacio.')


class WorkspaceContentView(APIView):
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
        return Response(WorkspaceDetailSerializer(espacio, context={'request': request}).data)

    def delete(self, request, slug, space_slug, coleccion):
        espacio, campo, objetos, ids = self._resolver(request, space_slug, coleccion)
        campo.remove(*objetos.filter(pk__in=ids))
        return Response(WorkspaceDetailSerializer(espacio, context={'request': request}).data)

    def _resolver(self, request, space_slug, coleccion):
        if coleccion not in COLECCIONES_DE_ESPACIO:
            raise NotFound('Esa colección no existe en un Espacio.')
        espacio = require_workspace(request.membership, space_slug)
        nombre_campo, nombre_modelo = COLECCIONES_DE_ESPACIO[coleccion]
        ids = request.data.get('ids')
        if ids is None:
            ids = [request.data.get('id')] if request.data.get('id') else []
        if not isinstance(ids, list) or not ids:
            raise ValidationError({'ids': 'Mande al menos un id.'})
        objetos = _queryset_enganchable(nombre_modelo, request.empresa)
        return espacio, getattr(espacio, nombre_campo), objetos, ids


class WorkspaceAvailableView(APIView):
    """Lo que todavía se puede enganchar a este Espacio, para los selectores."""

    permission_classes = [IsAuthenticated, IsEditor]

    def get(self, request, slug, space_slug):
        espacio = require_workspace(request.membership, space_slug)
        salida = {}
        for coleccion, (nombre_campo, nombre_modelo) in COLECCIONES_DE_ESPACIO.items():
            ya_estan = getattr(espacio, nombre_campo).values_list('pk', flat=True)
            disponibles = _queryset_enganchable(nombre_modelo, request.empresa).exclude(
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


class WorkspaceConversationsView(APIView):
    """Las conversaciones que se trabajaron en este Espacio.

    A diferencia del historial personal, acá el hilo es del equipo: lo ve cualquiera
    que pertenezca al Espacio, sin importar quién lo escribió. Es lo que convierte al
    Espacio en un lugar de trabajo y no solo en una carpeta de permisos — el trabajo
    de un compañero queda a la vista en vez de perderse en su historial privado.
    """

    permission_classes = [IsAuthenticated, IsMember]

    def get(self, request, slug, space_slug):
        from apps.agents.models import Conversation

        espacio = require_workspace(request.membership, space_slug)
        conversaciones = (
            Conversation.objects
            .filter(workspace=espacio)
            .select_related('user', 'agent')
            .order_by('-updated_at')[:100]
        )
        return Response([
            {
                'id': c.id,
                'title': c.title or 'Sin título',
                'agent': c.agent.name if c.agent else None,
                'agent_handle': c.agent.handle if c.agent else None,
                'author': (c.user.get_full_name() or c.user.email) if c.user else None,
                'es_mia': c.user_id == request.user.id,
                'updated_at': c.updated_at,
            }
            for c in conversaciones
        ])

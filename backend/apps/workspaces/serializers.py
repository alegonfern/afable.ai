from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import (
    ROLE_CHOICES, ROLE_MEMBER, SECTOR_CHOICES, VISIBILITY_CHOICES,
    Invitation, Membership, Space, Workspace,
)

User = get_user_model()


class MemberUserSerializer(serializers.ModelSerializer):
    """El usuario visto desde la tabla de Personas: lo justo para la fila."""

    full_name = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'full_name', 'avatar_url']

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.email

    def get_avatar_url(self, obj):
        if obj.avatar:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.avatar.url) if request else obj.avatar.url
        return obj.google_avatar_url or None


class MembershipSerializer(serializers.ModelSerializer):
    user = MemberUserSerializer(read_only=True)

    class Meta:
        model = Membership
        fields = ['id', 'user', 'role', 'joined_at']


class MembershipRoleSerializer(serializers.Serializer):
    """Cambiar el rol de un miembro. Lo único editable de una membresía."""

    role = serializers.ChoiceField(choices=ROLE_CHOICES)


class WorkspaceSerializer(serializers.ModelSerializer):
    my_role = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()
    logo_url = serializers.SerializerMethodField()
    sector_label = serializers.SerializerMethodField()

    class Meta:
        model = Workspace
        fields = [
            'id', 'name', 'slug', 'sector', 'sector_label', 'description', 'employees',
            'tax_id', 'agent_creation_policy', 'created_at', 'my_role', 'member_count',
            'organization_id', 'logo', 'logo_url',
        ]
        # `organization_id` es el puente: el frontend lo usa para que, al cambiar de
        # Workspace, las pantallas que todavia consultan por Organization apunten a
        # la correcta. Se expone solo de lectura — el enlace lo maneja el backend.
        read_only_fields = ['id', 'slug', 'created_at', 'organization_id']
        extra_kwargs = {'logo': {'write_only': True, 'required': False, 'allow_null': True}}

    def get_my_role(self, obj):
        """El rol de quien pide, para que el frontend sepa qué mostrar.

        Sale del mapa que arma la vista (`roles`) o de la membresía que ya dejó
        puesta el permiso; nunca de una consulta nueva por fila.
        """
        roles = self.context.get('roles')
        if roles is not None:
            return roles.get(obj.id)
        membership = getattr(self.context.get('request'), 'membership', None)
        return membership.role if membership else None

    def get_member_count(self, obj):
        return obj.memberships.count()

    def get_logo_url(self, obj):
        if not obj.logo:
            return None
        request = self.context.get('request')
        return request.build_absolute_uri(obj.logo.url) if request else obj.logo.url

    def get_sector_label(self, obj):
        """El sector en palabras. El selector muestra esto y no el código guardado."""
        return dict(SECTOR_CHOICES).get(obj.sector, '')


class WorkspaceCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workspace
        fields = ['name', 'sector', 'description', 'employees', 'tax_id', 'agent_creation_policy']


# Para que el selector de sector del frontend no repita la lista a mano.
SECTORES = [{'value': v, 'label': etiqueta} for v, etiqueta in SECTOR_CHOICES]


class InvitationSerializer(serializers.ModelSerializer):
    status = serializers.CharField(read_only=True)
    invited_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Invitation
        fields = ['id', 'email', 'role', 'status', 'created_at', 'expires_at', 'invited_by_name']

    def get_invited_by_name(self, obj):
        if not obj.invited_by:
            return None
        return obj.invited_by.get_full_name() or obj.invited_by.email


class InvitationCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=ROLE_CHOICES, default=ROLE_MEMBER)

    def validate_email(self, value):
        email = value.strip().lower()
        workspace = self.context['workspace']

        if Membership.objects.filter(workspace=workspace, user__email__iexact=email).exists():
            raise serializers.ValidationError('Esa persona ya es miembro del Workspace.')

        pendientes = Invitation.objects.filter(
            workspace=workspace, email=email,
            accepted_at__isnull=True, revoked_at__isnull=True,
        )
        if any(inv.is_pending for inv in pendientes):
            raise serializers.ValidationError('Ya hay una invitación pendiente para ese correo.')

        return email


class InvitationPreviewSerializer(serializers.Serializer):
    """Lo que ve alguien con el link, ANTES de tener sesión.

    Solo el nombre del Workspace, quién invita y a qué correo — nada del contenido
    del Workspace ni de sus miembros.
    """

    workspace_name = serializers.CharField()
    workspace_slug = serializers.CharField()
    email = serializers.EmailField()
    role = serializers.CharField()
    invited_by_name = serializers.CharField(allow_null=True)
    status = serializers.CharField()

    @classmethod
    def from_invitation(cls, invitation):
        invited_by = invitation.invited_by
        return cls({
            'workspace_name': invitation.workspace.name,
            'workspace_slug': invitation.workspace.slug,
            'email': invitation.email,
            'role': invitation.role,
            'invited_by_name': (invited_by.get_full_name() or invited_by.email) if invited_by else None,
            'status': invitation.status,
        })


class SpaceListSerializer(serializers.ModelSerializer):
    """El Espacio como tarjeta: nombre, acceso y cuánto tiene adentro."""

    counts = serializers.SerializerMethodField()

    class Meta:
        model = Space
        fields = [
            'id', 'name', 'slug', 'description', 'icon', 'visibility',
            'counts', 'created_at',
        ]

    def get_counts(self, obj):
        return {
            'connections': obj.connections.count(),
            'documents': obj.documents.count(),
            'agents': obj.agents.count(),
            'members': obj.members.count(),
        }


class SpaceDetailSerializer(SpaceListSerializer):
    """El Espacio abierto: las tres pestañas en una sola respuesta."""

    connections = serializers.SerializerMethodField()
    documents = serializers.SerializerMethodField()
    agents = serializers.SerializerMethodField()
    members = MemberUserSerializer(many=True, read_only=True)

    class Meta(SpaceListSerializer.Meta):
        fields = SpaceListSerializer.Meta.fields + [
            'connections', 'documents', 'agents', 'members',
        ]

    def get_connections(self, obj):
        return [
            {'id': c.id, 'name': c.name, 'connector_type': c.connector_type,
             'category': c.category, 'is_active': c.is_active}
            for c in obj.connections.all()
        ]

    def get_documents(self, obj):
        return [
            {'id': d.id, 'title': d.title, 'category': d.category, 'source': d.source}
            for d in obj.documents.all()
        ]

    def get_agents(self, obj):
        return [
            {'id': a.id, 'name': a.name, 'description': a.description,
             'area': a.area, 'is_active': a.is_active}
            for a in obj.agents.all()
        ]


class SpaceWriteSerializer(serializers.ModelSerializer):
    """Crear y editar un Espacio. El contenido se engancha por endpoints aparte."""

    visibility = serializers.ChoiceField(choices=VISIBILITY_CHOICES, required=False)

    class Meta:
        model = Space
        fields = ['name', 'description', 'icon', 'visibility']

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('El Espacio necesita un nombre.')
        return value

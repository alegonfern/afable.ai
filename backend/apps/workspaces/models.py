import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


ROLE_MEMBER = 'miembro'
ROLE_EDITOR = 'editor'
ROLE_ADMIN = 'admin'

ROLE_CHOICES = [
    (ROLE_MEMBER, 'Miembro'),
    (ROLE_EDITOR, 'Editor'),
    (ROLE_ADMIN, 'Administrador'),
]

# De menor a mayor privilegio. La resolución de permisos compara por posición en
# esta lista, así que el orden importa: no reordenar sin revisar permissions.py.
ROLE_ORDER = [ROLE_MEMBER, ROLE_EDITOR, ROLE_ADMIN]

# Slugs que no puede tomar un Workspace, porque son segmentos literales de la API
# o palabras que conviene reservar para rutas futuras.
RESERVED_SLUGS = {'invitations', 'invitacion', 'me', 'new', 'nuevo', 'admin', 'api'}

INVITATION_TTL_DAYS = 7

# Mismos valores que `Organization.SECTORS`: lo que se elige acá se refleja en la
# Organization enlazada, que es la que hoy lee el prompt del agente. Si se cambian,
# cambiar los dos lados.
SECTOR_CHOICES = [
    ('manufactura', 'Manufactura'),
    ('tecnologia', 'Tecnología / Software'),
    ('retail', 'Retail / Comercio'),
    ('servicios', 'Servicios profesionales'),
    ('alimentos', 'Alimentos y bebidas'),
    ('construccion', 'Construcción'),
    ('logistica', 'Logística / Transporte'),
    ('energia', 'Energía'),
    ('turismo', 'Turismo / Hospitalidad'),
    ('otro', 'Otro'),
]


class Workspace(models.Model):
    """El contenedor de todo lo que hace una empresa dentro de Afable.

    Reemplaza a `Organization` del enfoque anterior, que era mono-tenant de hecho:
    el primer usuario de la plataforma quedaba administrador de todo y las
    consultas no filtraban por pertenencia. Acá la pertenencia es explícita y vive
    en `Membership`.
    """

    AGENT_CREATION_CHOICES = [
        ('todos', 'Todos los miembros'),
        ('editores', 'Editores y administradores'),
        ('admins', 'Solo administradores'),
    ]

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    sector = models.CharField(max_length=120, choices=SECTOR_CHOICES, blank=True)
    description = models.TextField(blank=True)
    employees = models.CharField(max_length=50, blank=True)
    tax_id = models.CharField(max_length=30, blank=True, help_text='RUT / NIF.')

    # El Workspace es la empresa vista desde Afable, así que su marca es la de la empresa.
    # No estaba en ningún modelo —tampoco en `Organization`— y hace falta para que el
    # selector pueda decir en qué empresa se está trabajando SIN leerle el nombre: quien
    # tiene dos Workspaces los distingue de un vistazo por la marca, no por el texto.
    #
    # Vacío es lo normal, no un caso de error: sin logo cargado, la pantalla dibuja un
    # monograma con la inicial y un color derivado del slug (ver `SelectorWorkspace`).
    logo = models.ImageField(upload_to='workspace_logos/', blank=True, null=True)

    # ── Puente hacia la app anterior ──────────────────────────────────────────
    # `Organization` sigue siendo el dueño de las conexiones, los documentos, el
    # contexto y los agentes, y `agent_service` lee su `sector` para el prompt.
    # Mientras eso siga así, cada Workspace apunta a la Organization que
    # reemplaza, y lo que se edita en la pantalla de Workspace se refleja en ella
    # (ver `mirror_to_organization`). Cuando ninguna pantalla dependa de
    # Organization, este campo y ese método se borran.
    organization = models.OneToOneField(
        'organizations.Organization', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='workspace',
    )
    agent_creation_policy = models.CharField(
        max_length=16, choices=AGENT_CREATION_CHOICES, default='editores',
        help_text='Quién puede crear agentes en este Workspace.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'workspaces'
        ordering = ['name']
        verbose_name = 'Workspace'
        verbose_name_plural = 'Workspaces'

    def __str__(self):
        return self.name

    @classmethod
    def build_slug(cls, name):
        """Slug único a partir del nombre, esquivando los reservados y los tomados."""
        base = slugify(name)[:120] or 'workspace'
        if base in RESERVED_SLUGS:
            base = f'{base}-workspace'
        candidate = base
        suffix = 2
        while cls.objects.filter(slug=candidate).exists():
            candidate = f'{base}-{suffix}'
            suffix += 1
        return candidate

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self.build_slug(self.name)
        super().save(*args, **kwargs)

    @classmethod
    def create_for_owner(cls, user, name=None):
        """El Workspace propio de quien recién se registró; queda administrador.

        Es lo que reemplaza al viejo `if User.objects.count() == 1: org_admin = True`:
        cada quien es administrador de lo suyo, no de la plataforma entera.
        """
        if not name:
            quien = (user.first_name or '').strip() or user.email.split('@')[0]
            name = f'Workspace de {quien}'
        workspace = cls.objects.create(name=name)
        workspace.add_member(user, ROLE_ADMIN)
        workspace.ensure_organization(user)
        return workspace

    def ensure_organization(self, owner):
        """Enlaza (o crea) la Organization que este Workspace administra.

        Parte del mismo puente que `mirror_to_organization`: el chat, las conexiones
        y los documentos todavía cuelgan de Organization, así que un Workspace sin
        una enlazada quedaría a medias.
        """
        from apps.organizations.models import Organization

        if self.organization_id:
            return self.organization

        propias = Organization.objects.filter(owner=owner)
        # Se prefiere una real sobre la "Personal" que crea sola apps/agents/views.py.
        org = propias.exclude(name='Personal').first() or propias.first()
        if org is None:
            org = Organization.objects.create(owner=owner, name=self.name, sector=self.sector or 'otro')
        elif Workspace.objects.filter(organization=org).exclude(pk=self.pk).exists():
            # Ya la administra otro Workspace: este estrena la suya.
            org = Organization.objects.create(owner=owner, name=self.name, sector=self.sector or 'otro')

        self.organization = org
        self.save(update_fields=['organization'])
        return org

    def mirror_to_organization(self):
        """Copia a la Organization enlazada lo que el código viejo todavía lee.

        Sin esto, editar el sector en la pantalla de Workspace no tendría ningún
        efecto: el prompt del agente seguiría leyendo el de la Organization. Es
        una sola dirección a propósito — el Workspace es la verdad.
        """
        org = self.organization
        if org is None:
            return None
        org.name = self.name
        org.sector = self.sector or org.sector
        org.description = self.description
        org.employees = self.employees
        org.rut = self.tax_id
        org.save(update_fields=['name', 'sector', 'description', 'employees', 'rut'])
        return org

    def add_member(self, user, role=ROLE_MEMBER, invited_by=None):
        """Suma a un usuario, o le sube el rol si ya estaba y el nuevo es mayor."""
        membership, created = Membership.objects.get_or_create(
            workspace=self, user=user,
            defaults={'role': role, 'invited_by': invited_by},
        )
        if not created and ROLE_ORDER.index(role) > ROLE_ORDER.index(membership.role):
            membership.role = role
            membership.save(update_fields=['role'])
        return membership


class Membership(models.Model):
    """La pertenencia de un usuario a un Workspace, con su rol.

    Es la única fuente de verdad de los permisos. Reemplaza a `User.org_admin`
    (un booleano global de plataforma) y a `User.areas`.
    """

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='memberships')
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default=ROLE_MEMBER)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='invited_memberships',
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'workspace_memberships'
        ordering = ['joined_at']
        constraints = [
            models.UniqueConstraint(fields=['workspace', 'user'], name='unica_membresia_por_workspace'),
        ]
        verbose_name = 'Membresía'
        verbose_name_plural = 'Membresías'

    def __str__(self):
        return f'{self.user.email} — {self.workspace.name} ({self.role})'

    def has_at_least(self, role):
        return ROLE_ORDER.index(self.role) >= ROLE_ORDER.index(role)


class Invitation(models.Model):
    """Invitación por correo con token.

    No crea usuario: mientras no se acepte, del invitado solo existe su correo.
    Así no quedan cuentas huérfanas sin contraseña, como pasaba con el
    `UserInviteView` anterior, que creaba el usuario en el acto.
    """

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='invitations')
    email = models.EmailField()
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default=ROLE_MEMBER)
    token = models.CharField(max_length=64, unique=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='sent_invitations',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='accepted_invitations',
    )
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'workspace_invitations'
        ordering = ['-created_at']
        constraints = [
            # Una sola invitación viva por correo y workspace. Las aceptadas y las
            # revocadas quedan fuera del índice, para poder reinvitar a alguien.
            models.UniqueConstraint(
                fields=['workspace', 'email'],
                condition=models.Q(accepted_at__isnull=True, revoked_at__isnull=True),
                name='unica_invitacion_viva_por_correo',
            ),
        ]
        verbose_name = 'Invitación'
        verbose_name_plural = 'Invitaciones'

    def __str__(self):
        return f'{self.email} → {self.workspace.name} ({self.status})'

    @classmethod
    def create_for(cls, workspace, email, role=ROLE_MEMBER, invited_by=None):
        return cls.objects.create(
            workspace=workspace,
            email=email.strip().lower(),
            role=role,
            token=secrets.token_urlsafe(32),
            invited_by=invited_by,
            expires_at=timezone.now() + timedelta(days=INVITATION_TTL_DAYS),
        )

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_pending(self):
        return self.accepted_at is None and self.revoked_at is None and not self.is_expired

    @property
    def status(self):
        if self.accepted_at:
            return 'aceptada'
        if self.revoked_at:
            return 'revocada'
        if self.is_expired:
            return 'vencida'
        return 'pendiente'

    def renew(self):
        """Reenviar: token nuevo y plazo nuevo. El link viejo deja de servir."""
        self.token = secrets.token_urlsafe(32)
        self.expires_at = timezone.now() + timedelta(days=INVITATION_TTL_DAYS)
        self.save(update_fields=['token', 'expires_at'])
        return self

    def accept(self, user):
        """Convierte la invitación en membresía.

        Exige que el correo del usuario sea el invitado: si no, cualquiera con el
        link entraría al Workspace. Devuelve la `Membership` creada.
        """
        if not self.is_pending:
            raise ValueError(f'La invitación está {self.status}.')
        if user.email.strip().lower() != self.email:
            raise ValueError('La invitación es para otro correo.')

        membership = self.workspace.add_member(user, self.role, invited_by=self.invited_by)
        self.accepted_at = timezone.now()
        self.accepted_by = user
        self.save(update_fields=['accepted_at', 'accepted_by'])
        return membership


# ---------------------------------------------------------------------------
# Espacios de contexto
# ---------------------------------------------------------------------------

VISIBILITY_OPEN = 'abierto'
VISIBILITY_RESTRICTED = 'restringido'

VISIBILITY_CHOICES = [
    (VISIBILITY_OPEN, 'Abierto — lo ve todo el Workspace'),
    (VISIBILITY_RESTRICTED, 'Restringido — solo quienes se agreguen'),
]


class Space(models.Model):
    """Un Espacio: contenedor que junta fuentes, agentes y personas.

    Es la unidad con la que se decide quién ve qué. Sin Espacios, todas las
    conexiones y documentos de la empresa quedan revueltos y cualquiera puede
    preguntarle al agente por la carpeta de Recursos Humanos. Con Espacios,
    el agente de Ventas sólo alcanza las fuentes del Espacio de Ventas.

    La visibilidad se resuelve en `permissions.spaces_visible_to`, junto al
    resto de los permisos del Workspace: acá sólo viven los datos.
    """

    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name='spaces'
    )
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=8, blank=True, help_text='Emoji de la tarjeta.')
    visibility = models.CharField(
        max_length=16, choices=VISIBILITY_CHOICES, default=VISIBILITY_OPEN
    )

    # Quiénes entran cuando el Espacio es restringido. En un Espacio abierto esta
    # lista se ignora al resolver el acceso: la usa igual la pantalla para mostrar
    # a los responsables del Espacio.
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name='spaces'
    )

    # Lo que el Espacio le presta a sus agentes.
    connections = models.ManyToManyField(
        'organizations.SystemConnection', blank=True, related_name='spaces'
    )
    documents = models.ManyToManyField(
        'organizations.CompanyDocument', blank=True, related_name='spaces'
    )
    agents = models.ManyToManyField(
        'agents.Agent', blank=True, related_name='spaces'
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'workspace_spaces'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['workspace', 'slug'], name='unico_slug_de_espacio_por_workspace'
            ),
        ]
        verbose_name = 'Espacio'
        verbose_name_plural = 'Espacios'

    def __str__(self):
        return f'{self.workspace.name} — {self.name}'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._slug_disponible(slugify(self.name) or 'espacio')
        super().save(*args, **kwargs)

    def _slug_disponible(self, base):
        candidato, n = base, 2
        hermanos = Space.objects.filter(workspace=self.workspace).exclude(pk=self.pk)
        while hermanos.filter(slug=candidato).exists():
            candidato = f'{base}-{n}'
            n += 1
        return candidato

    @property
    def is_open(self):
        return self.visibility == VISIBILITY_OPEN

    def allows(self, user, membership=None):
        """Si `user` puede ver este Espacio.

        Un Espacio abierto lo ve cualquier miembro del Workspace. Uno restringido,
        sólo quien esté en `members` — con la excepción del administrador, que
        tiene que poder administrar lo que no usa.
        """
        if self.is_open:
            return True
        if membership is not None and membership.role == ROLE_ADMIN:
            return True
        return self.members.filter(pk=user.pk).exists()


"""Los Workspaces de una Empresa, y quién entra a cada uno.

⭐ **Tres niveles, no cuatro** (decisión del 2026-08-06):

    Empresa  →  Workspace  →  Sesión

- La **Empresa** (`organizations.Organization`) es el titular: quién es, su gente con su
  rol, el plan que paga, y todo el conocimiento — archivos, conexiones, contexto.
- Un **Workspace** es un pedazo de esa empresa con su propia gente: Ventas, Finanzas, o un
  cliente si quien usa Afable es una consultora. Decide **qué parte del conocimiento y qué
  agentes** alcanza quien trabaja ahí.
- Una **Sesión** es el trabajo en curso adentro de un Workspace.

**Este modelo era el `Space`.** Hasta hoy había un `Workspace` que era la empresa (1 a 1 con
`Organization`, con los mismos campos duplicados en las dos tablas) y adentro unos
`Espacios` que hacían de contenedor con permisos. Eran dos nombres para dos niveles y una
tabla de más: el "Workspace-empresa" no aportaba nada que la Empresa no tuviera, y el
Espacio ya era exactamente lo que uno espera de un workspace. Así que la empresa se quedó
arriba con un solo nombre, y el Espacio se quedó con el nombre de Workspace.

El rol (miembro / editor / administrador) es **de la Empresa**, no del Workspace: con varias
áreas, ser editor en una y miembro en otra sería un permiso que nadie puede explicar en una
línea. Lo que decide cada Workspace es más simple: si es abierto, entra toda la empresa; si
es restringido, sólo quien esté agregado.
"""

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

# Slugs que no puede tomar una Empresa ni un Workspace, porque son segmentos
# literales de la API o palabras que conviene reservar para rutas futuras.
RESERVED_SLUGS = {'invitations', 'invitacion', 'me', 'new', 'nuevo', 'admin', 'api'}

INVITATION_TTL_DAYS = 7

VISIBILITY_OPEN = 'abierto'
VISIBILITY_RESTRICTED = 'restringido'

VISIBILITY_CHOICES = [
    (VISIBILITY_OPEN, 'Abierto — entra toda la empresa'),
    (VISIBILITY_RESTRICTED, 'Restringido — solo quienes se agreguen'),
]

# Cómo se llama el Workspace que recibe a todos cuando la empresa recién parte, y el que
# hereda lo que existía antes de que hubiera Workspaces. Una empresa sin ninguno no
# tendría dónde abrir una Sesión.
WORKSPACE_GENERAL = 'General'


class Workspace(models.Model):
    """Un pedazo de la empresa con su propia gente, su conocimiento y sus agentes.

    Es la unidad con la que se decide **quién ve qué**. Sin esto, todas las conexiones y
    documentos de la empresa quedan revueltos y cualquiera puede preguntarle al agente por
    la carpeta de Remuneraciones.

    La visibilidad se resuelve en `permissions.workspaces_visible_to`, junto al resto de
    los permisos: acá sólo viven los datos.
    """

    organization = models.ForeignKey(
        'organizations.Organization', on_delete=models.CASCADE, related_name='workspaces',
    )
    name = models.CharField(max_length=120)
    # Único en toda la instalación, no por empresa: el slug viaja solo en la URL
    # (`/workspaces/<slug>/`) y con un unique por empresa habría que arrastrar también el
    # slug de la empresa en cada dirección.
    slug = models.SlugField(max_length=140, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=8, blank=True, help_text='Emoji de la tarjeta.')
    visibility = models.CharField(
        max_length=16, choices=VISIBILITY_CHOICES, default=VISIBILITY_OPEN
    )

    # Quiénes entran cuando es restringido. En uno abierto esta lista se ignora al
    # resolver el acceso: la usa igual la pantalla para mostrar a los responsables.
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name='workspaces'
    )

    # Lo que este Workspace le presta a sus agentes. El conocimiento es de la Empresa; acá
    # se elige qué parte alcanza.
    connections = models.ManyToManyField(
        'organizations.SystemConnection', blank=True, related_name='workspaces'
    )
    documents = models.ManyToManyField(
        'organizations.CompanyDocument', blank=True, related_name='workspaces'
    )
    agents = models.ManyToManyField(
        'agents.Agent', blank=True, related_name='workspaces'
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'workspaces'
        ordering = ['name']
        verbose_name = 'Workspace'
        verbose_name_plural = 'Workspaces'

    def __str__(self):
        return f'{self.organization.name} — {self.name}'

    @property
    def es_abierto(self):
        return self.visibility == VISIBILITY_OPEN

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
    def general_de(cls, organization, creado_por=None):
        """El Workspace donde entra todo el mundo, creándolo si la empresa no tiene ninguno.

        Existe para que nunca haya una empresa sin dónde trabajar: es el que recibe las
        Sesiones y las conversaciones de quien todavía no armó áreas.
        """
        # ⚠️ Por NOMBRE primero, y sólo después "cualquiera abierto". Buscar sólo por
        # visibilidad devolvía el primero por orden alfabético, así que en cuanto la
        # empresa cargó los datos de ejemplo ("Empresa de ejemplo" < "General") las
        # Sesiones nuevas empezaron a caer entre los documentos de prueba. Lo que se crea
        # sin elegir área tiene que ir al General, no al primero de la lista.
        general = cls.objects.filter(
            organization=organization, name=WORKSPACE_GENERAL,
        ).first()
        if general:
            return general
        abierto = cls.objects.filter(
            organization=organization, visibility=VISIBILITY_OPEN,
        ).exclude(name__istartswith='Empresa de ejemplo').first()
        if abierto:
            return abierto
        return cls.objects.create(
            organization=organization, name=WORKSPACE_GENERAL,
            visibility=VISIBILITY_OPEN, created_by=creado_por,
        )


class Membership(models.Model):
    """La pertenencia de un usuario a una **Empresa**, con su rol.

    Es la única fuente de verdad de los permisos. El rol vive acá y no en el Workspace: una
    persona es editora *de la empresa*, y después entra o no a cada Workspace. Repartir el
    rol por área daría permisos que no se pueden explicar ("editor en Ventas, miembro en
    Finanzas, ¿puede borrar este archivo?").
    """

    organization = models.ForeignKey(
        'organizations.Organization', on_delete=models.CASCADE, related_name='memberships',
    )
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
            models.UniqueConstraint(fields=['organization', 'user'], name='unica_membresia_por_empresa'),
        ]
        verbose_name = 'Membresía'
        verbose_name_plural = 'Membresías'

    def __str__(self):
        return f'{self.user.email} — {self.organization.name} ({self.role})'

    def has_at_least(self, role):
        return ROLE_ORDER.index(self.role) >= ROLE_ORDER.index(role)


class Invitation(models.Model):
    """Invitación por correo con token, a una Empresa.

    No crea usuario: mientras no se acepte, del invitado solo existe su correo.
    Así no quedan cuentas huérfanas sin contraseña.
    """

    organization = models.ForeignKey(
        'organizations.Organization', on_delete=models.CASCADE, related_name='invitations',
    )
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
            # Una sola invitación viva por correo y empresa. Las aceptadas y las
            # revocadas quedan fuera del índice, para poder reinvitar a alguien.
            models.UniqueConstraint(
                fields=['organization', 'email'],
                condition=models.Q(accepted_at__isnull=True, revoked_at__isnull=True),
                name='unica_invitacion_viva_por_correo',
            ),
        ]
        verbose_name = 'Invitación'
        verbose_name_plural = 'Invitaciones'

    def __str__(self):
        return f'{self.email} → {self.organization.name} ({self.status})'

    @classmethod
    def create_for(cls, organization, email, role=ROLE_MEMBER, invited_by=None):
        return cls.objects.create(
            organization=organization,
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
        """Convierte la invitación en membresía de la Empresa.

        Exige que el correo del usuario sea el invitado: si no, cualquiera con el
        link entraría. Devuelve la `Membership` creada.
        """
        if not self.is_pending:
            raise ValueError(f'La invitación está {self.status}.')
        if user.email.strip().lower() != self.email:
            raise ValueError('La invitación es para otro correo.')

        membership = self.organization.agregar_miembro(
            user, self.role, invited_by=self.invited_by,
        )
        self.accepted_at = timezone.now()
        self.accepted_by = user
        self.save(update_fields=['accepted_at', 'accepted_by'])
        return membership

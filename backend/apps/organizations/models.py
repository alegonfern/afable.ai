from django.db import models
from django.conf import settings
from services.encryption import encrypt, decrypt


class Organization(models.Model):
    """La **Empresa**: el titular de todo lo que hay adentro de Afable.

    ⭐ Es el nivel de arriba, y dentro de ella viven **varios Workspaces** (Ventas,
    Finanzas, un cliente si quien usa Afable es una consultora). Hasta el 2026-08-06 esto
    era 1 a 1 con el Workspace y los mismos datos vivían en las dos tablas, sincronizados a
    mano por un método espejo; el reparto de ahora es:

    - **Acá arriba, lo que es de la empresa entera**: quién es, su gente y los roles, el
      plan que paga, y **todo el conocimiento** — archivos, carpetas, conexiones y
      contexto. Se carga una vez y sirve a todos los Workspaces.
    - **Abajo, en cada Workspace, el trabajo**: qué parte de ese conocimiento alcanza,
      qué agentes, quiénes entran, y las Sesiones donde se trabaja.

    Cargar los archivos arriba es lo que evita que algo que le sirve a dos áreas haya que
    subirlo dos veces; restringir abajo es lo que evita que el agente de Ventas alcance la
    carpeta de Remuneraciones.

    El nombre del modelo sigue siendo `Organization` **por ahora**: renombrarlo a `Empresa`
    es un paso mecánico aparte, para que este cambio de estructura se pueda leer sin que lo
    tape un renombre de 169 líneas.
    """

    SECTORS = [
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

    AGENT_CREATION_CHOICES = [
        ('todos', 'Todos los miembros'),
        ('editores', 'Editores y administradores'),
        ('admins', 'Solo administradores'),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='owned_organizations'
    )
    name = models.CharField(max_length=255)
    # Con qué se la nombra en la URL. Venía del Workspace, que era el que viajaba en las
    # direcciones de la API; ahora que la empresa es el nivel de arriba, es suyo.
    slug = models.SlugField(max_length=140, unique=True, null=True, blank=True)
    owner_role = models.CharField(max_length=255, blank=True)
    employees = models.CharField(max_length=50, blank=True)
    rut = models.CharField(max_length=30, blank=True)
    sector = models.CharField(max_length=50, choices=SECTORS, blank=True)
    description = models.TextField(blank=True)

    # ── Lo que subió del Workspace ────────────────────────────────────────────
    # Estos campos vivían duplicados en las dos tablas y un método espejo los copiaba en
    # cada guardado. Eran la causa de "lo edité y no se vio": la pantalla escribía en una
    # tabla y el prompt del agente leía la otra.
    logo = models.ImageField(upload_to='workspace_logos/', blank=True, null=True)
    billing_email = models.EmailField(blank=True, help_text='Correo para comprobantes de pago.')
    agent_creation_policy = models.CharField(
        max_length=16, choices=AGENT_CREATION_CHOICES, default='editores',
        help_text='Quién puede crear agentes en esta empresa.',
    )
    onboarding_oculto = models.BooleanField(default=False)

    # Odoo integration
    odoo_url = models.URLField(blank=True)
    odoo_db = models.CharField(max_length=255, blank=True)
    odoo_username = models.EmailField(blank=True)
    odoo_api_key = models.CharField(max_length=512, blank=True)
    odoo_connected = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'organizations'
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    # ── Identidad ─────────────────────────────────────────────────────────────

    @classmethod
    def build_slug(cls, name):
        """Slug único a partir del nombre, esquivando los reservados y los tomados."""
        from django.utils.text import slugify

        from apps.workspaces.models import RESERVED_SLUGS

        base = slugify(name)[:120] or 'empresa'
        if base in RESERVED_SLUGS:
            base = f'{base}-empresa'
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

    # ── Su gente ──────────────────────────────────────────────────────────────

    def agregar_miembro(self, user, role=None, invited_by=None):
        """Suma a una persona, o le sube el rol si ya estaba y el nuevo es mayor."""
        from apps.workspaces.models import ROLE_MEMBER, ROLE_ORDER, Membership

        role = role or ROLE_MEMBER
        membership, creado = Membership.objects.get_or_create(
            organization=self, user=user,
            defaults={'role': role, 'invited_by': invited_by},
        )
        if not creado and ROLE_ORDER.index(role) > ROLE_ORDER.index(membership.role):
            membership.role = role
            membership.save(update_fields=['role'])
        return membership

    @classmethod
    def crear_para_dueno(cls, user, name=None):
        """La Empresa de quien recién se registró, con su Workspace General listo.

        Reemplaza a `Workspace.create_for_owner`. Crea las tres cosas que hacen falta para
        poder trabajar: la empresa, su primer administrador, y un Workspace abierto — sin
        ese último no habría dónde abrir una Sesión.
        """
        from apps.workspaces.models import ROLE_ADMIN, Workspace

        if not name:
            quien = (user.first_name or '').strip() or user.email.split('@')[0]
            name = f'Empresa de {quien}'

        empresa = cls.objects.create(owner=user, name=name)
        empresa.agregar_miembro(user, ROLE_ADMIN)
        Workspace.general_de(empresa, creado_por=user)

        # ⭐ Y con quién hablar. Sin esto la empresa nace sin un solo agente: quien se
        # registra abre la galería y no encuentra a nadie, que es la peor primera
        # pantalla posible para un producto que se llama "IA para equipos".
        from apps.agents.agentes_base import sembrar_en
        sembrar_en(empresa)

        return empresa


class IntegrationScan(models.Model):
    SYSTEM_TYPES = [('odoo', 'Odoo'), ('sap_b1', 'SAP B1'), ('hubspot', 'HubSpot'), ('shopify', 'Shopify')]

    organization = models.ForeignKey(
        'Organization', on_delete=models.CASCADE, related_name='scans'
    )
    system_name  = models.CharField(max_length=100)
    system_type  = models.CharField(max_length=20, choices=SYSTEM_TYPES)
    modules_found = models.JSONField(default=list)
    ai_context   = models.TextField(blank=True)
    recommendations = models.JSONField(default=list)
    scanned_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'integration_scans'
        ordering = ['-scanned_at']


class ActiveIntegration(models.Model):
    INTEGRATION_TYPES = [
        ('dummyjson', 'DummyJSON Store'),
        ('sheets', 'Google Sheets'),
        ('notion', 'Notion'),
        ('postgres', 'PostgreSQL'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='active_integrations'
    )
    integration_type = models.CharField(max_length=50, choices=INTEGRATION_TYPES)
    is_active = models.BooleanField(default=True)
    connected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'active_integrations'
        unique_together = ('user', 'integration_type')

    def __str__(self):
        return f'{self.user} — {self.integration_type}'


class SystemConnection(models.Model):
    """
    Conexión a un sistema externo (Odoo, SAP via MSSQL, PostgreSQL, CSV).
    Las credenciales se almacenan cifradas con Fernet.
    """
    CONNECTOR_TYPES = [
        ('odoo', 'Odoo'),
        ('mssql', 'SQL Server / SAP Business One'),
        ('postgresql', 'PostgreSQL'),
        ('csv', 'Excel / CSV'),
        ('google_drive', 'Google Drive'),
    ]

    # Categoría del sistema en la operación del cliente. ERP y CRM son las
    # integraciones profundas (tier 1); el resto entra como conector.
    CATEGORIES = [
        ('erp', 'ERP'),
        ('crm', 'CRM'),
        ('db', 'Base de datos'),
        ('otro', 'Otro'),
    ]

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='connections'
    )
    name = models.CharField(max_length=255)  # ej: "SAP Producción", "Odoo Chile"
    connector_type = models.CharField(max_length=50, choices=CONNECTOR_TYPES)
    category = models.CharField(max_length=20, choices=CATEGORIES, default='otro')
    _config_encrypted = models.TextField(db_column='config_encrypted', blank=True)
    schema_cache = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'system_connections'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.organization.name} — {self.name}'

    def set_config(self, config: dict):
        import json
        self._config_encrypted = encrypt(json.dumps(config))

    def get_config(self) -> dict:
        import json
        if not self._config_encrypted:
            return {}
        return json.loads(decrypt(self._config_encrypted))

    @property
    def config(self) -> dict:
        return self.get_config()

    @config.setter
    def config(self, value: dict):
        self.set_config(value)


class OrganizationContext(models.Model):
    """
    Contexto cualitativo de la empresa que se inyecta SIEMPRE en el system
    prompt de todos los agentes (a diferencia de Organization.description,
    que hoy no se usa en el prompt). Complementa al 'modelo vivo' (esquemas
    de datos): esto es lo que no está en ninguna tabla.
    """
    organization = models.OneToOneField(
        Organization, on_delete=models.CASCADE, related_name='context'
    )
    business_description = models.TextField(blank=True)  # qué hace la empresa
    products_services = models.TextField(blank=True)      # qué vende/ofrece
    target_customers = models.TextField(blank=True)       # a quién le vende
    glossary = models.TextField(blank=True)                # diccionario de negocio: cómo le dicen a las cosas
    tone_guidelines = models.TextField(blank=True)          # cómo debe hablar el agente
    restrictions = models.TextField(blank=True)             # qué NUNCA debe decir/hacer
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'organization_contexts'

    def __str__(self):
        return f'Contexto — {self.organization.name}'

    def is_empty(self) -> bool:
        return not any([
            self.business_description, self.products_services, self.target_customers,
            self.glossary, self.tone_guidelines, self.restrictions,
        ])


class CompanyDocument(models.Model):
    """
    Archivo subido por el usuario como fuente de contexto para la IA (política,
    manual, catálogo, etc). El texto extraído y el resumen se generan una sola
    vez al subir, no en cada request de chat.
    """
    CATEGORIES = [
        ('politica', 'Política'),
        ('manual', 'Manual'),
        ('catalogo', 'Catálogo'),
        ('financiero', 'Financiero'),
        ('otro', 'Otro'),
    ]
    SOURCES = [
        ('manual', 'Subido manualmente'),
        ('drive_sync', 'Sincronizado desde Google Drive'),
        # Los datos de ejemplo se marcan para poder sacarlos de una: quien probó con
        # ellos y después cargó los suyos no puede quedar con las dos cosas mezcladas,
        # porque el agente citaría un contrato inventado como si fuera de la empresa.
        ('ejemplo', 'Datos de ejemplo'),
    ]

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='documents'
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+'
    )
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=20, choices=CATEGORIES, default='otro')
    file = models.FileField(upload_to='company_documents/%Y/%m/')
    is_public = models.BooleanField(
        default=False,
        help_text='Privado (solo lo ve quien lo subió) o público (visible para toda la empresa).',
    )
    content_type = models.CharField(max_length=100, blank=True)
    extracted_text = models.TextField(blank=True)
    summary = models.TextField(blank=True)
    processing_error = models.CharField(max_length=255, blank=True)
    source = models.CharField(max_length=20, choices=SOURCES, default='manual')
    # El archivo pertenece a una Sesion cuando se subio ahi. Es un campo y no un
    # modelo aparte a proposito: asi el archivo de una Sesion hereda TODO lo que ya
    # funciona sobre CompanyDocument — la extraccion de texto, el indexado semantico
    # (apps.sources) y el alcance de los agentes. Un modelo propio de archivos habria
    # obligado a duplicar las tres cosas.
    sesion = models.ForeignKey(
        'sesiones.Sesion', on_delete=models.CASCADE,
        null=True, blank=True, related_name='archivos',
    )
    # Donde vive el archivo en el arbol. `null` = la raiz. Al borrar la carpeta el
    # documento NO se borra: sube a la raiz (SET_NULL). Borrar una carpeta no puede
    # llevarse el trabajo que hay dentro sin avisar.
    carpeta = models.ForeignKey(
        'archivos.Carpeta', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='documentos',
    )
    # Si el texto de este documento se puede editar en Afable. Lo decide el tipo de
    # archivo al subirlo: un .md o .txt si, un PDF/Word/Excel no — se les extrae el
    # texto para leerlos, pero escribirles de vuelta les rompe el formato.
    editable = models.BooleanField(default=False)
    # Restringir es la excepcion (ver `apps.archivos.models.Permiso`): sin esto, el
    # archivo lo ve y lo edita cualquier miembro del Workspace, o hereda la restriccion
    # de su carpeta si esa esta restringida.
    restringido = models.BooleanField(default=False)
    # id del archivo en el sistema de origen (ej. fileId de Drive) — permite hacer
    # upsert en cada sync sin duplicar el mismo archivo como documento nuevo.
    external_id = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'company_documents'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'external_id'],
                condition=~models.Q(external_id=''),
                name='unique_org_external_id',
            ),
        ]

    def __str__(self):
        return f'{self.organization.name} — {self.title}'


class ContextCubicle(models.Model):
    """
    Cubículo de contexto: bloque libre (título + contenido) que el usuario
    arma para explicarle algo puntual a la IA sobre su empresa. La unión de
    todos los cubículos de una organización se compila en un archivo
    Markdown real (ver services/context_compiler.py) — pensado para que
    alguien sin ninguna noción de "contexto de IA" vea con sus propios ojos
    de dónde sale lo que el agente sabe.
    """
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='context_cubicles'
    )
    title = models.CharField(max_length=120)
    content = models.TextField()
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'context_cubicles'
        ordering = ['order', 'id']

    def __str__(self):
        return f'{self.organization.name} — {self.title}'

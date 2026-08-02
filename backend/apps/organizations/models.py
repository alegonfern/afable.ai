from django.db import models
from django.conf import settings
from services.encryption import encrypt, decrypt


class Organization(models.Model):
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

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='owned_organizations'
    )
    name = models.CharField(max_length=255)
    owner_role = models.CharField(max_length=255, blank=True)
    employees = models.CharField(max_length=50, blank=True)
    rut = models.CharField(max_length=30, blank=True)
    sector = models.CharField(max_length=50, choices=SECTORS, blank=True)
    description = models.TextField(blank=True)

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

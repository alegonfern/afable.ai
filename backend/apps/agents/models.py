from django.db import models
from django.conf import settings


class Agent(models.Model):
    ERP_TYPES = [('odoo', 'Odoo'), ('sap_b1', 'SAP Business One')]

    organization = models.ForeignKey(
        'organizations.Organization', on_delete=models.CASCADE, related_name='agents'
    )
    name = models.CharField(max_length=255)
    erp_type = models.CharField(max_length=20, choices=ERP_TYPES, default='odoo', blank=True)  # legado
    description = models.TextField(blank=True)
    # Configuración real del agente:
    instructions = models.TextField(blank=True)          # cómo debe comportarse / tono / foco
    area = models.CharField(max_length=30, blank=True)    # área de negocio (ventas, inventario…)
    systems = models.ManyToManyField(                     # a qué sistemas conectados puede consultar
        'organizations.SystemConnection', blank=True, related_name='agents'
    )
    model = models.CharField(max_length=120, blank=True)  # override opcional del modelo de IA
    # Contenido de la "tarjeta del agente" (ventana de detalle antes de chatear):
    tools_summary = models.CharField(max_length=280, blank=True)          # qué herramientas usa / cómo analiza
    recommended_frequency = models.CharField(max_length=60, blank=True)   # ej. "Diario", "Semanal"
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='agents_creados',
        help_text='Quien lo creó. Vacío = agente que vino con Afable.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'agents'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.organization.name})"


class AgentTemplate(models.Model):
    """Receta compartible de un agente (galería 'Explorar' de la comunidad).

    NO guarda credenciales ni datos ni conexiones — solo la configuración del
    agente (instrucciones/área/modelo). Al 'usar' una plantilla se crea un
    Agent en la org del usuario, que luego mapea sus propios sistemas.

    `kind` separa la galería comunitaria ('community', página Explorar) de los
    agentes oficiales por rol ('role', sección "Agentes por rol" en Agentes).
    """
    KINDS = [('community', 'Comunidad'), ('role', 'Rol')]

    kind = models.CharField(max_length=12, choices=KINDS, default='community')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    instructions = models.TextField(blank=True)
    area = models.CharField(max_length=30, blank=True)
    model = models.CharField(max_length=120, blank=True)
    tools_summary = models.CharField(max_length=280, blank=True)          # qué herramientas usa / cómo analiza
    recommended_frequency = models.CharField(max_length=60, blank=True)   # ej. "Diario", "Semanal"
    category = models.CharField(max_length=40, blank=True)   # Ventas, Inventario, Finanzas…
    icon = models.CharField(max_length=8, blank=True)         # emoji para la card
    accent = models.CharField(max_length=9, blank=True)       # color de acento (#RRGGBB)
    # "Imagen de proceso": apps involucradas en orden, se renderiza como flujo
    # con iconos conectados (Shopify → Afable → WhatsApp). Cada paso:
    # {"app": "Shopify", "icon": "🛍️", "color": "#96BF48"}
    flow = models.JSONField(default=list, blank=True)
    author_name = models.CharField(max_length=120, blank=True)  # handle de la comunidad
    uses_count = models.PositiveIntegerField(default=0)       # prueba social
    is_featured = models.BooleanField(default=False)          # se muestra en el landing
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'agent_templates'
        ordering = ['-is_featured', '-uses_count', 'name']

    def __str__(self):
        return self.name


class Conversation(models.Model):
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='conversations')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='conversations'
    )
    title = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'conversations'
        ordering = ['-updated_at']

    def __str__(self):
        return self.title or f"Conversación {self.pk}"


class Message(models.Model):
    ROLES = [('user', 'Usuario'), ('assistant', 'Asistente')]

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=20, choices=ROLES)
    content = models.TextField()
    model_used = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'messages'
        ordering = ['created_at']


class Document(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='documents'
    )
    title = models.CharField(max_length=500)
    content = models.TextField()
    conversation = models.ForeignKey(
        Conversation, on_delete=models.SET_NULL, null=True, blank=True, related_name='documents'
    )
    grid_x = models.IntegerField(default=0)
    grid_y = models.IntegerField(default=0)
    grid_w = models.IntegerField(default=6)
    grid_h = models.IntegerField(default=5)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'documents'
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class Automation(models.Model):
    """
    Automatización = automatiza qué quieres obtener de Afable. Dos disparadores:

    - 'interval' (programado): UN prompt que se ejecuta solo cada X minutos con
      el mismo agente del chat (datos reales) y cuyo resultado llega por correo.
    - 'event' (por evento): Afable vigila una conexión cada X minutos
      (event_state guarda el snapshot; services/event_detector.py compara) y
      cuando el evento dispara avisa por correo; si además hay prompt, lo
      ejecuta con el detalle del evento como contexto.

    La corre el comando `run_automations`.
    """
    TRIGGER_TYPES = [
        ('interval', 'Programado'),
        ('event', 'Por evento'),
    ]
    EVENT_TYPES = [
        ('new_table', 'Nueva tabla o base de datos'),
        ('new_rows', 'Nuevas filas en una tabla'),
        ('connection_down', 'Conexión caída'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='automations'
    )
    organization = models.ForeignKey(
        'organizations.Organization', on_delete=models.CASCADE, related_name='automations'
    )
    name = models.CharField(max_length=255)
    prompt = models.TextField(blank=True)  # obligatorio en 'interval', opcional en 'event'
    interval_minutes = models.PositiveIntegerField(default=60)  # en 'event' = cada cuánto revisar
    notify_email = models.EmailField()
    is_active = models.BooleanField(default=True)

    trigger_type = models.CharField(max_length=20, choices=TRIGGER_TYPES, default='interval')
    connection = models.ForeignKey(
        'organizations.SystemConnection', on_delete=models.CASCADE,
        related_name='automations', null=True, blank=True,
    )
    event_type = models.CharField(max_length=30, choices=EVENT_TYPES, blank=True)
    event_config = models.JSONField(default=dict, blank=True)  # ej: {"table": "sale_order"}
    event_state = models.JSONField(default=dict, blank=True)   # snapshot de la última revisión

    last_run_at = models.DateTimeField(null=True, blank=True)
    last_result = models.TextField(blank=True)
    last_error = models.CharField(max_length=500, blank=True)
    run_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'automations'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} (cada {self.interval_minutes} min)'

    def is_due(self, now) -> bool:
        if not self.is_active:
            return False
        if self.last_run_at is None:
            return True
        return (now - self.last_run_at).total_seconds() >= self.interval_minutes * 60


class Routine(models.Model):
    """
    Mi rutina: secuencia de pasos (prompts) que se ejecutan en orden; el
    resultado de cada paso se pasa como contexto al siguiente. Cada paso puede
    usar un agente específico (ej: Científico de Datos). Se ejecuta manualmente
    ("Ejecutar ahora") o cada X minutos; si tiene correo, se envía el resultado.

    steps: [{"prompt": "...", "agent_id": 3 | null}, ...]
    last_steps_results: [{"step": 1, "prompt": "...", "result": "...", "error": ""}, ...]
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='routines'
    )
    organization = models.ForeignKey(
        'organizations.Organization', on_delete=models.CASCADE, related_name='routines'
    )
    name = models.CharField(max_length=255)
    steps = models.JSONField(default=list)
    interval_minutes = models.PositiveIntegerField(null=True, blank=True)  # null = solo manual
    notify_email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)

    last_run_at = models.DateTimeField(null=True, blank=True)
    last_steps_results = models.JSONField(default=list)
    last_error = models.CharField(max_length=500, blank=True)
    run_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'routines'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({len(self.steps)} pasos)'

    def is_due(self, now) -> bool:
        if not self.is_active or not self.interval_minutes:
            return False
        if self.last_run_at is None:
            return True
        return (now - self.last_run_at).total_seconds() >= self.interval_minutes * 60


class AgentFavorite(models.Model):
    """Un agente marcado como favorito por una persona.

    Es por usuario, no por Workspace: dos personas del mismo equipo tienen
    favoritos distintos aunque vean los mismos agentes.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='agentes_favoritos',
    )
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='favoritos')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'agent_favorites'
        constraints = [
            models.UniqueConstraint(fields=['user', 'agent'], name='un_favorito_por_usuario_y_agente'),
        ]
        verbose_name = 'Favorito'
        verbose_name_plural = 'Favoritos'

    def __str__(self):
        return f'{self.user.email} ♥ {self.agent.name}'


class AgentConfig(models.Model):
    """Lo que la empresa le entrega a un agente cuando lo carga a su Workspace.

    Es el paso que sigue a "cargar el agente": el agente trae su oficio (sabe de
    facturación, del SII, de contabilidad), pero no sabe nada de ESTA empresa.
    Acá se le entrega lo que le falta, y por eso vive en Admin y no en la vista de
    trabajo: es una decisión de la empresa, no de quien conversa.

    Tres cosas, en el orden en que se piensan:
      1. Datos     — a qué datos específicos puede mirar.
      2. Reglas    — qué debe y qué no debe hacer.
      3. Útil      — lo que conviene que sepa y no está en ningún sistema.

    `completed_at` marca cuándo quedó configurado por primera vez; mientras esté
    vacío, el agente aparece como pendiente en Admin > Agentes.
    """

    agent = models.OneToOneField(Agent, on_delete=models.CASCADE, related_name='config')
    datos = models.TextField(
        blank=True, help_text='Qué datos específicos de la empresa puede consultar.',
    )
    reglas = models.TextField(
        blank=True, help_text='Qué debe y qué no debe hacer al responder.',
    )
    info_util = models.TextField(
        blank=True, help_text='Información de la empresa que le sirve y no está en ningún sistema.',
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='configuraciones_de_agente',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'agent_configs'
        verbose_name = 'Configuración de agente'
        verbose_name_plural = 'Configuraciones de agente'

    def __str__(self):
        return f'Configuración de {self.agent.name}'

    @property
    def esta_configurado(self):
        return bool(self.completed_at)

    def como_contexto(self):
        """El texto que se le suma al prompt del agente. Vacío si no hay nada cargado."""
        partes = []
        if self.datos:
            partes.append(f'DATOS QUE PUEDE CONSULTAR:\n{self.datos}')
        if self.reglas:
            partes.append(f'REGLAS DE ESTA EMPRESA:\n{self.reglas}')
        if self.info_util:
            partes.append(f'INFORMACIÓN ÚTIL DE LA EMPRESA:\n{self.info_util}')
        return '\n\n'.join(partes)

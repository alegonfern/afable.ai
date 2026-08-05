"""
Sesiones: donde el equipo y sus agentes trabajan sobre un objetivo comun.

Una Sesion junta tres cosas —conversaciones, tareas y archivos— alrededor de algo
concreto: un cliente, un proyecto, un cierre de mes. El principio que la define es
que **todo lo que puede hacer una persona ahi, lo puede hacer un agente**: abrir una
conversacion, tomar una tarea, dejar un archivo.

## Sesion y Espacio no son lo mismo, y conviene tenerlo claro

- El **Espacio** (`apps.workspaces.Space`) es el contenedor de PERMISOS sobre el
  conocimiento: decide que conexiones y documentos alcanza cada agente. Es
  infraestructura.
- La **Sesion** es la SUPERFICIE de trabajo: donde se conversa, se anota lo que falta
  y se guardan los archivos de ese trabajo.

Una empresa puede tener tres Espacios (Ventas, Finanzas, RRHH) y quince Sesiones
(una por cliente), y cada Sesion usa el conocimiento de los Espacios que le
correspondan a sus agentes.
"""
from django.conf import settings
from django.db import models
from django.utils.text import slugify

VISIBILIDAD_ABIERTA = 'abierta'
VISIBILIDAD_RESTRINGIDA = 'restringida'
VISIBILIDADES = [
    (VISIBILIDAD_ABIERTA, 'Abierta — cualquiera del Workspace entra'),
    (VISIBILIDAD_RESTRINGIDA, 'Restringida — solo quien se invite'),
]

ROL_MIEMBRO = 'miembro'
ROL_EDITOR = 'editor'
ROLES = [
    (ROL_MIEMBRO, 'Miembro'),
    (ROL_EDITOR, 'Editor'),
]
# Orden de mando: un editor puede todo lo del miembro y ademas administrar la Sesion.
JERARQUIA = {ROL_MIEMBRO: 0, ROL_EDITOR: 1}


class Sesion(models.Model):
    """Un lugar de trabajo del equipo, con sus agentes adentro."""

    workspace = models.ForeignKey(
        'workspaces.Workspace', on_delete=models.CASCADE, related_name='sesiones',
    )
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140)
    description = models.TextField(blank=True, help_text='De que se trata esta Sesion.')
    icon = models.CharField(max_length=8, blank=True, help_text='Emoji de la tarjeta.')

    visibility = models.CharField(
        max_length=16, choices=VISIBILIDADES, default=VISIBILIDAD_ABIERTA,
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, through='SesionMiembro', related_name='sesiones',
    )

    # Lo que TODOS los agentes de esta Sesion ven, ademas de sus propias
    # instrucciones. Es lo que hace que la Sesion no sea solo una carpeta: "en esta
    # Sesion hablamos con el cliente Rever, nunca prometas fechas".
    instrucciones_para_agentes = models.TextField(
        blank=True,
        help_text='Lo ven todos los agentes que trabajen en esta Sesion.',
    )
    # Con quien contesta un hilo nuevo si nadie eligio otro agente.
    agente_por_defecto = models.ForeignKey(
        'agents.Agent', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='sesiones_por_defecto',
    )
    # Las Habilidades que vienen preseleccionadas en las conversaciones de la Sesion.
    habilidades_por_defecto = models.ManyToManyField(
        'agents.Skill', blank=True, related_name='sesiones',
    )

    # Archivar no es borrar: la Sesion sale de la barra lateral pero su contenido
    # sigue existiendo. Es la distincion que hace Dust y vale la pena conservarla —
    # borrar se lleva el trabajo del equipo, archivar solo lo saca de la vista.
    archivada = models.BooleanField(default=False)
    archivada_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sesiones'
        ordering = ['archivada', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['workspace', 'slug'], name='unico_slug_de_sesion_por_workspace',
            ),
        ]
        verbose_name = 'Sesión'
        verbose_name_plural = 'Sesiones'

    def __str__(self):
        return f'{self.workspace.name} — {self.name}'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._slug_disponible(slugify(self.name) or 'sesion')
        super().save(*args, **kwargs)

    def _slug_disponible(self, base):
        candidato, n = base, 2
        hermanas = Sesion.objects.filter(workspace=self.workspace).exclude(pk=self.pk)
        while hermanas.filter(slug=candidato).exists():
            candidato = f'{base}-{n}'
            n += 1
        return candidato

    @property
    def es_abierta(self):
        return self.visibility == VISIBILIDAD_ABIERTA

    def rol_de(self, user, membership=None):
        """El rol de `user` en esta Sesion, o None si no entra.

        Un administrador del Workspace entra siempre como editor: no puede administrar
        lo que no ve. En una Sesion abierta, cualquier miembro del Workspace entra como
        miembro aunque no este agregado — eso es lo que significa "abierta".
        """
        from apps.workspaces.models import ROLE_ADMIN

        if membership is not None and membership.role == ROLE_ADMIN:
            return ROL_EDITOR
        propio = (
            SesionMiembro.objects.filter(sesion=self, user=user)
            .values_list('role', flat=True).first()
        )
        if propio:
            return propio
        if self.es_abierta and membership is not None:
            return ROL_MIEMBRO
        return None

    def alcanza(self, user, membership=None, minimo=ROL_MIEMBRO):
        rol = self.rol_de(user, membership)
        return rol is not None and JERARQUIA[rol] >= JERARQUIA[minimo]


class SesionMiembro(models.Model):
    """Quien participa de una Sesion y con que rol."""

    sesion = models.ForeignKey(Sesion, on_delete=models.CASCADE, related_name='miembros')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sesiones_miembro',
    )
    role = models.CharField(max_length=12, choices=ROLES, default=ROL_MIEMBRO)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sesion_miembros'
        ordering = ['user__first_name', 'user__email']
        constraints = [
            models.UniqueConstraint(fields=['sesion', 'user'], name='una_vez_por_sesion'),
        ]
        verbose_name = 'Miembro de Sesión'
        verbose_name_plural = 'Miembros de Sesión'

    def __str__(self):
        return f'{self.user} en {self.sesion.name} ({self.role})'


# ── Tareas ────────────────────────────────────────────────────────────────────

TAREA_PENDIENTE = 'pendiente'
TAREA_EN_CURSO = 'en_curso'
TAREA_LISTA = 'lista'
TAREA_ESTADOS = [
    (TAREA_PENDIENTE, 'Pendiente'),
    (TAREA_EN_CURSO, 'En curso'),
    (TAREA_LISTA, 'Lista'),
]


class Task(models.Model):
    """Una tarea de la Sesion: un pendiente que toma una persona o un agente.

    Nacio colgada del Espacio y se mudo aca, que es su lugar: el pendiente es del
    trabajo (la Sesion), no del contenedor de permisos (el Espacio).

    Lo que la separa de un tablero de tareas cualquiera: **el agente asignado la
    ejecuta**. La descripcion es su instruccion, corre el mismo agente del chat y el
    resultado queda guardado en la tarea para que el equipo lo lea sin abrir ninguna
    conversacion.
    """

    sesion = models.ForeignKey(Sesion, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=255)
    description = models.TextField(
        blank=True,
        help_text='Lo que hay que hacer. Si la toma un agente, esto es su instruccion.',
    )
    state = models.CharField(max_length=12, choices=TAREA_ESTADOS, default=TAREA_PENDIENTE)

    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='tareas_asignadas',
    )
    agent = models.ForeignKey(
        'agents.Agent', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='tareas',
    )

    resultado = models.TextField(blank=True)
    resultado_error = models.CharField(max_length=500, blank=True)
    ejecutada_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sesion_tasks'
        # Solo por fecha. Ordenar por `state` aca seria ordenar por el TEXTO del estado
        # ('en_curso' < 'lista' < 'pendiente'), o sea las tareas ya hechas antes que las
        # que faltan. El orden por estado se arma en la vista.
        ordering = ['-created_at']
        verbose_name = 'Tarea'
        verbose_name_plural = 'Tareas'

    def __str__(self):
        return f'{self.sesion.name} — {self.title}'

    @property
    def esta_lista(self):
        return self.state == TAREA_LISTA

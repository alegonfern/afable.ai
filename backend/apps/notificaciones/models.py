"""Lo que pasó mientras la persona no estaba mirando.

⭐ **Por qué existe.** Afable dejó de ser una app de una sola persona: en una Sesión
escriben varios, los agentes trabajan solos y las tareas se asignan. Todo eso ya quedaba
registrado, pero había que ir a buscarlo pantalla por pantalla — y lo que hay que ir a
buscar, no se busca. Sin un lugar donde se acumule lo dirigido a UNO, el trabajo del
equipo se pierde igual que se perdía el del agente.

Dos reglas que no hay que romper:

- **Es POR PERSONA.** Una notificación tiene dueño; no hay "notificaciones de la empresa"
  que todos leen y nadie atiende.
- **A nadie se le avisa de lo que hizo él mismo.** Es la forma más rápida de que la
  campana se vuelva ruido y se deje de mirar.
"""
from django.conf import settings
from django.db import models

TIPO_MENSAJE = 'mensaje'
TIPO_TAREA = 'tarea'
TIPO_AGENTE = 'agente'
TIPOS = [
    (TIPO_MENSAJE, 'Mensaje en una Sesión'),
    (TIPO_TAREA, 'Tarea'),
    (TIPO_AGENTE, 'Trabajo de un agente'),
]


class Notificacion(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notificaciones',
    )
    # De qué empresa es. Sin esto, alguien que trabaja en dos empresas vería mezclado lo
    # de una en la otra, que es una fuga de contexto aunque no lo sea de datos.
    organization = models.ForeignKey(
        'organizations.Organization', on_delete=models.CASCADE,
        related_name='notificaciones', null=True, blank=True,
    )
    tipo = models.CharField(max_length=16, choices=TIPOS, default=TIPO_MENSAJE)
    titulo = models.CharField(max_length=200)
    # Una línea de contexto: sin ella, "Tienes un mensaje nuevo" obliga a entrar para
    # saber si importaba.
    detalle = models.CharField(max_length=300, blank=True)
    # A dónde lleva. Una notificación que no se puede abrir es un aviso de que uno se
    # perdió algo, sin decir dónde.
    enlace = models.CharField(max_length=300, blank=True)

    leida = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notificaciones'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', 'leida'])]

    def __str__(self):
        return f'{self.user_id}: {self.titulo}'

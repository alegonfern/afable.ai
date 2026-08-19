"""Los mensajes que la gente le manda a soporte desde adentro de la app.

**No es un chat.** Es un formulario, y esa decisión es deliberada: un chat que dice
"estamos en línea" y no contesta en tres horas es peor que un formulario que promete una
respuesta por correo y la cumple. Cuando haya alguien dedicado a atender, esto se puede
apuntar a una bandeja de verdad sin rehacer la pantalla.

Lo que lo hace útil de verdad es el **contexto**: el mensaje viaja con dónde estaba la
persona, en qué empresa y Workspace, qué modelo tenía activo y los últimos errores que
tiró el navegador. Es lo que evita el ida y vuelta de "¿qué estabas haciendo cuando pasó?",
que es donde se va la mitad del tiempo de soporte — y es justo lo que un widget de un
tercero no puede saber.
"""

from django.conf import settings
from django.db import models


class MensajeSoporte(models.Model):
    ESTADO_NUEVO = 'nuevo'
    ESTADO_ATENDIDO = 'atendido'
    ESTADOS = [(ESTADO_NUEVO, 'Nuevo'), (ESTADO_ATENDIDO, 'Atendido')]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='mensajes_soporte',
    )
    # La empresa desde la que escribe. `SET_NULL` y no `CASCADE`: si la empresa se da de
    # baja, el mensaje —y lo que se haya respondido— tiene que sobrevivir.
    organization = models.ForeignKey(
        'organizations.Organization', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='mensajes_soporte',
    )
    texto = models.TextField()
    # A dónde se responde. Se guarda aparte del usuario porque puede escribir desde una
    # cuenta y pedir la respuesta en otro correo.
    email = models.EmailField()
    # Dónde estaba y qué se rompió: ruta, Workspace, modelo activo, últimos errores.
    # Va como JSON y no en columnas porque lo que conviene mandar va a cambiar, y no
    # quiero una migración cada vez que se agregue un dato al diagnóstico.
    contexto = models.JSONField(default=dict, blank=True)
    estado = models.CharField(max_length=12, choices=ESTADOS, default=ESTADO_NUEVO)
    creado_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'mensajes_soporte'
        ordering = ['-creado_at']
        verbose_name = 'Mensaje a soporte'
        verbose_name_plural = 'Mensajes a soporte'

    def __str__(self):
        return f'{self.email} — {self.texto[:40]}'

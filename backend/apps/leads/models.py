from django.db import models


class Lead(models.Model):
    """Oportunidad captada por el asistente del sitio web (landing).

    Solo se persiste cuando el asistente clasifica al visitante como `workflow`
    (automatización a medida con n8n que arma el equipo) y ya reunió correo +
    resumen. Los visitantes `saas` usan la plataforma por autoatención y NO
    generan Lead."""

    SEGMENT_CHOICES = [
        ('workflow', 'Workflow — automatización a medida con n8n'),
        ('saas', 'Plataforma — autoatención'),
    ]

    email = models.EmailField()
    name = models.CharField(max_length=160, blank=True)
    company = models.CharField(max_length=160, blank=True)
    segment = models.CharField(max_length=16, choices=SEGMENT_CHOICES, default='workflow')
    summary = models.TextField(help_text='Qué flujo quiere automatizar (redactado por la IA).')
    transcript = models.JSONField(default=list, blank=True, help_text='Conversación completa.')
    emailed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.email} ({self.segment})'

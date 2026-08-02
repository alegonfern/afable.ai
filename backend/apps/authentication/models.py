import secrets
from datetime import timedelta
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


RESPONSE_STYLES = [
    ('ejecutivo', 'Ejecutivo — resumido, bullet points'),
    ('analitico', 'Analítico — detallado con cifras'),
    ('tecnico',   'Técnico — con terminología especializada'),
]


class User(AbstractUser):
    email          = models.EmailField(unique=True)
    avatar         = models.ImageField(upload_to='avatars/', null=True, blank=True)
    google_avatar_url = models.URLField(blank=True)
    role           = models.CharField(max_length=100, blank=True)
    department     = models.CharField(max_length=100, blank=True)
    objectives     = models.TextField(blank=True)
    response_style = models.CharField(max_length=20, choices=RESPONSE_STYLES, default='ejecutivo')

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        db_table = 'users'
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'


class UserContext(models.Model):
    """
    Capa PERSONAL de "Mi contexto": lo que cada usuario le cuenta a la IA sobre
    sí mismo. Se inyecta siempre en el system prompt de sus chats, junto con la
    capa de empresa (OrganizationContext), que es compartida.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='context')
    about_me = models.TextField(blank=True)             # a qué se dedica día a día
    priorities = models.TextField(blank=True)           # prioridades/proyectos actuales
    custom_instructions = models.TextField(blank=True)  # cómo quiere que la IA le responda
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_contexts'

    def __str__(self):
        return f'Contexto personal — {self.user.email}'

    def is_empty(self) -> bool:
        return not any([self.about_me, self.priorities, self.custom_instructions])


class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reset_tokens')
    token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    used = models.BooleanField(default=False)

    class Meta:
        db_table = 'password_reset_tokens'

    def is_valid(self):
        return not self.used and (timezone.now() - self.created_at) < timedelta(hours=1)

    @classmethod
    def create_for_user(cls, user):
        cls.objects.filter(user=user, used=False).delete()
        return cls.objects.create(user=user, token=secrets.token_urlsafe(48))

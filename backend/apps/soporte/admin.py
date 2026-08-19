from django.contrib import admin

from .models import MensajeSoporte


@admin.register(MensajeSoporte)
class MensajeSoporteAdmin(admin.ModelAdmin):
    list_display = ['creado_at', 'email', 'organization', 'estado', 'texto']
    list_filter = ['estado', 'creado_at']
    search_fields = ['texto', 'email']
    readonly_fields = ['user', 'organization', 'texto', 'email', 'contexto', 'creado_at']

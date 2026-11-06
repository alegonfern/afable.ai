"""Los conectores de cada empresa (27-10-2026): la conexión con un servicio externo (su credencial,
cifrada, y sus opciones) y el historial de cada sincronización.

Cada tipo vive en su propio módulo (hubspot.py, sii_rcv.py) con la misma forma: `probar`,
`sincronizar` y, si corre solo, `toca_correr`.
"""
from django.conf import settings
from django.db import models

from services.encryption import decrypt, encrypt


class Conexion(models.Model):
    HUBSPOT, SII_RCV = 'hubspot', 'sii_rcv'
    TIPOS = [(HUBSPOT, 'HubSpot'), (SII_RCV, 'SII · Libros contables')]

    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE,
                                     related_name='conectores')
    tipo = models.CharField(max_length=20, choices=TIPOS)
    activa = models.BooleanField(default=True)
    # La credencial (token de HubSpot…), cifrada. El SII usa el certificado del facturador.
    _secreto = models.TextField(db_column='secreto_cifrado', blank=True)
    # Opciones del conector (qué se importa, si corre solo…).
    config = models.JSONField(default=dict, blank=True)
    # Lo que el servicio dice de la cuenta conectada (nombre del portal, RUT…), para mostrarlo.
    cuenta = models.JSONField(default=dict, blank=True)
    ultima_sincronizacion = models.DateTimeField(null=True, blank=True)
    ultimo_resultado = models.JSONField(default=dict, blank=True)
    ultimo_error = models.TextField(blank=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name='+')
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['organization', 'tipo'], name='conector_unico_por_empresa')]

    def guardar_secreto(self, valor):
        self._secreto = encrypt(valor) if valor else ''

    @property
    def secreto(self):
        return decrypt(self._secreto) if self._secreto else ''


class Sincronizacion(models.Model):
    """Una corrida de un conector: cuándo, si salió bien y qué trajo."""

    OK, ERROR = 'ok', 'error'
    conexion = models.ForeignKey(Conexion, on_delete=models.CASCADE, related_name='sincronizaciones')
    inicio = models.DateTimeField(auto_now_add=True)
    fin = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(max_length=8, default=OK)
    automatica = models.BooleanField(default=False)
    resumen = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                related_name='+')

    class Meta:
        ordering = ['-inicio']

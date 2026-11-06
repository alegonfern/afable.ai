"""Señales de Finanzas para los módulos que dependen de ella (Compras y Ventas), sin que
Finanzas tenga que conocerlos."""

from django.dispatch import Signal

# Se importó una carga del SII. `documentos`: los DocumentoTributario nuevos.
carga_importada = Signal()

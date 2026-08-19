"""Las tarifas de los modelos: US$ por millón de tokens, entrada y salida.

Se corre en cada despliegue y es idempotente. Vive acá y no como constante en el código
porque un cambio de precio del proveedor tiene que quedar con fecha: el consumo que ya
se anotó se sigue explicando con el precio que corría ese día.

Estos dos números son también el peso del modelo dentro del plan del cliente. Con el
anclaje de 1 crédito = US$0,000001, un token de entrada de Sonnet gasta 3 créditos y uno
de Haiku 1, que es lo que hace que usar el modelo barato le rinda más al cliente.

Ollama entra con precio 0 a propósito: corre en nuestro propio servidor, así que su
costo es el fierro y no la llamada.
"""

from datetime import datetime, timezone as tz

from django.core.management.base import BaseCommand

from apps.payments.models import TarifaModelo

# Fecha de vigencia de esta tanda. Fija y no "ahora": si fuera la hora de correr el
# comando, cada despliegue crearía otra fila con los mismos precios.
VIGENTE_DESDE = datetime(2026, 8, 1, tzinfo=tz.utc)

TARIFAS = [
    # (modelo, proveedor, entrada, salida, notas)
    ('claude-haiku-4-5-20251001', 'anthropic', 1, 5, 'Haiku 4.5'),
    ('claude-sonnet-5', 'anthropic', 3, 15, 'Sonnet 5'),
    ('claude-opus-5', 'anthropic', 5, 25, 'Opus 5'),
    ('claude-fable-5', 'anthropic', 10, 50, 'Fable 5'),
    # Los identificadores que el código usa hoy (agent_service, document_processing).
    # Van explícitos para que la tarifa no dependa de adivinar la familia por el nombre.
    ('claude-sonnet-4-6', 'anthropic', 3, 15, 'el modelo por omisión del agente'),
    ('claude-opus-4-8', 'anthropic', 5, 25, 'el agente con Odoo conectado'),
]


class Command(BaseCommand):
    help = 'Crea o actualiza las tarifas por millón de tokens de cada modelo.'

    def handle(self, *args, **options):
        for modelo, proveedor, entrada, salida, notas in TARIFAS:
            _, creado = TarifaModelo.objects.update_or_create(
                modelo=modelo, vigente_desde=VIGENTE_DESDE,
                defaults={
                    'proveedor': proveedor,
                    'precio_entrada_usd_millon': entrada,
                    'precio_salida_usd_millon': salida,
                    'notas': notas,
                },
            )
            self.stdout.write(
                f'{"creada " if creado else "al día"} · {modelo}: '
                f'US${entrada}/{salida} por millón'
            )
        self.stdout.write(
            '\nDeepSeek no tiene tarifa cargada: sus llamadas quedan anotadas con 0 '
            'créditos y marcadas en `sin_tarifa` hasta que se confirmen sus dos precios.'
        )

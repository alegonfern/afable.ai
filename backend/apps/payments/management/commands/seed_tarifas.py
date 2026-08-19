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
from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.payments.models import TarifaModelo

# Fecha de vigencia de esta tanda. Fija y no "ahora": si fuera la hora de correr el
# comando, cada despliegue crearía otra fila con los mismos precios.
VIGENTE_DESDE = datetime(2026, 8, 1, tzinfo=tz.utc)

# Multiplicadores de caché de Anthropic: leer 0,1 de la entrada, escribir 1,25 por
# cinco minutos y 2 por una hora.
ANTHROPIC = (Decimal('0.1'), Decimal('1.25'), Decimal('2'))

# DeepSeek cobra la caché muy distinto: el acierto vale 0,014 sobre 0,44 de entrada en
# `flash` y 0,044 sobre 1,32 en `pro`, o sea del orden de 0,032 y no 0,1. Y no cobra
# premio por escribir: el token que no acierta se paga a precio de entrada y queda
# guardado. Tampoco tiene caché de una hora, así que ese factor no se usa nunca.
DEEPSEEK_FLASH = (Decimal('0.0318'), Decimal('1'), Decimal('1'))
DEEPSEEK_PRO = (Decimal('0.0333'), Decimal('1'), Decimal('1'))

TARIFAS = [
    # (modelo, proveedor, entrada, salida, factores, notas)
    ('claude-haiku-4-5-20251001', 'anthropic', 1, 5, ANTHROPIC, 'Haiku 4.5'),
    ('claude-sonnet-5', 'anthropic', 3, 15, ANTHROPIC, 'Sonnet 5'),
    ('claude-opus-5', 'anthropic', 5, 25, ANTHROPIC, 'Opus 5'),
    ('claude-fable-5', 'anthropic', 10, 50, ANTHROPIC, 'Fable 5'),
    # Los identificadores que el código usa hoy (agent_service, document_processing).
    # Van explícitos para que la tarifa no dependa de adivinar la familia por el nombre.
    ('claude-sonnet-4-6', 'anthropic', 3, 15, ANTHROPIC, 'el modelo por omisión del agente'),
    ('claude-opus-4-8', 'anthropic', 5, 25, ANTHROPIC, 'el agente con Odoo conectado'),
    # DeepSeek a precio de PUNTA a propósito, que es el doble del de fuera de punta.
    # Es una decisión de precio, no un descuido: así el crédito del cliente vale
    # siempre lo mismo y su cupo no rinde distinto según la hora en que trabaje. Como
    # las horas punta de DeepSeek (01-04 y 06-10 UTC) caen de noche en Chile, en la
    # práctica se cobra el peor caso y se paga el mejor casi siempre.
    ('deepseek-v4-flash', 'deepseek', Decimal('0.44'), Decimal('1.32'), DEEPSEEK_FLASH,
     'punta; fuera de punta es la mitad'),
    ('deepseek-v4-pro', 'deepseek', Decimal('1.32'), Decimal('3.96'), DEEPSEEK_PRO,
     'punta; fuera de punta es la mitad'),
]


class Command(BaseCommand):
    help = 'Crea o actualiza las tarifas por millón de tokens de cada modelo.'

    def handle(self, *args, **options):
        for modelo, proveedor, entrada, salida, factores, notas in TARIFAS:
            lectura, escritura, escritura_1h = factores
            _, creado = TarifaModelo.objects.update_or_create(
                modelo=modelo, vigente_desde=VIGENTE_DESDE,
                defaults={
                    'proveedor': proveedor,
                    'precio_entrada_usd_millon': entrada,
                    'precio_salida_usd_millon': salida,
                    'factor_cache_lectura': lectura,
                    'factor_cache_escritura': escritura,
                    'factor_cache_escritura_1h': escritura_1h,
                    'notas': notas,
                },
            )
            self.stdout.write(
                f'{"creada " if creado else "al día"} · {modelo}: '
                f'US${entrada}/{salida} por millón'
            )
        self.stdout.write(
            '\nDeepSeek queda cargado a precio de PUNTA: fuera de punta el proveedor '
            'cobra la mitad, y esa diferencia es margen y no descuento al cliente.'
        )

"""Punto único de medición del consumo de modelos.

Todo lo que le cuesta plata a Afable pasa por acá. La regla es una sola: donde se
llame a un modelo, `registrar()` escribe una fila con lo que esa llamada gastó. Una
fila **por llamada a la API**, no por mensaje del usuario: una sola pregunta con
herramientas conectadas puede dar 8 vueltas al modelo, y el costo real es la suma de
las 8. Medir por mensaje escondería justamente lo que se quiere ver.

## El anclaje: 1 crédito = US$0,000001 de costo del proveedor

Los tokens crudos no sirven para vender: son iguales para todos los modelos por
construcción, así que 25 millones rendirían lo mismo en Haiku que en Opus y el cliente
no tendría ningún incentivo para usar el modelo barato. Con el anclaje en un
micro-dólar, **el peso de cada modelo es su precio por millón**:

    créditos = tokens × precio_por_millón

Haiku entrada vale 1 crédito por token, Sonnet 3, Opus 5. Sale exacto: 25 millones de
créditos son US$25 de costo, que es el peor caso del plan Starter. Un modelo nuevo es
una fila en `TarifaModelo` con sus dos precios; un cambio de precio es editar dos
números con fecha de vigencia.

La caché sigue el precio del proveedor: leer vale ×0,1 del precio de entrada y escribir
×1,25.

## Lo que esta capa NO hace

No bloquea nada. `estado()` calcula cuánto se usó y si el cupo está pasado, pero la
compuerta que corta el servicio es otro cambio y va al inicio del turno, nunca dentro
del bucle de herramientas: cortar en la iteración 6 de 8 deja media respuesta y el
costo ya está gastado.
"""

import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

# Precio de lista del proveedor en US$ por millón de tokens (entrada, salida).
# Es la tarifa por omisión: si hay una fila vigente en `TarifaModelo` para el modelo,
# manda la fila. Ollama corre en nuestro propio fierro, así que no tiene precio por
# token — su costo es el servidor, no la llamada.
TARIFAS_POR_OMISION = {
    'haiku':   (1, 5),
    'sonnet':  (3, 15),
    'opus':    (5, 25),
    'fable':   (10, 50),
    'ollama':  (0, 0),
}

# Multiplicadores de caché del proveedor, sobre el precio de ENTRADA. En Decimal y no
# en float porque los precios que vienen de `TarifaModelo` son Decimal, y Python no
# multiplica Decimal por float.
FACTOR_CACHE_LECTURA = Decimal('0.1')
FACTOR_CACHE_ESCRITURA = Decimal('1.25')

PROVEEDOR_ANTHROPIC = 'anthropic'
PROVEEDOR_DEEPSEEK = 'deepseek'
PROVEEDOR_OLLAMA = 'ollama'

VACIO = {'entrada': 0, 'salida': 0, 'cache_lectura': 0, 'cache_escritura': 0}


def medir(proveedor: str, respuesta) -> dict:
    """Normaliza el consumo que reporta cada proveedor a las mismas cuatro cifras.

    Cada API lo nombra distinto y algunas cuentan la caché dentro de la entrada, así
    que sin este adaptador cada sitio de llamada tendría que acordarse del detalle de
    su proveedor. Devuelve siempre las cuatro claves; si la respuesta no trae uso
    (un error, un stream cortado), devuelve ceros en vez de fallar.
    """
    try:
        if proveedor == PROVEEDOR_ANTHROPIC:
            return _medir_anthropic(respuesta)
        if proveedor == PROVEEDOR_DEEPSEEK:
            return _medir_deepseek(respuesta)
        if proveedor in (PROVEEDOR_OLLAMA, 'ollama_cloud'):
            return _medir_ollama(respuesta)
    except Exception:
        logger.exception('medir() no pudo leer el uso de %s', proveedor)
    return dict(VACIO)


def _medir_anthropic(respuesta) -> dict:
    """El SDK entrega un objeto. `input_tokens` NO incluye la caché: los tokens leídos
    y los escritos vienen aparte, así que se suman sin restar nada."""
    uso = getattr(respuesta, 'usage', None)
    if uso is None:
        return dict(VACIO)
    return {
        'entrada': int(getattr(uso, 'input_tokens', 0) or 0),
        'salida': int(getattr(uso, 'output_tokens', 0) or 0),
        'cache_lectura': int(getattr(uso, 'cache_read_input_tokens', 0) or 0),
        'cache_escritura': int(getattr(uso, 'cache_creation_input_tokens', 0) or 0),
    }


def _medir_deepseek(respuesta) -> dict:
    """Formato OpenAI: `prompt_tokens` SÍ incluye los aciertos de caché, así que hay
    que restarlos o el mismo token se cobra dos veces, una a precio lleno."""
    uso = (respuesta or {}).get('usage') or {}
    cache_lectura = int(uso.get('prompt_cache_hit_tokens', 0) or 0)
    entrada = int(uso.get('prompt_tokens', 0) or 0) - cache_lectura
    return {
        'entrada': max(entrada, 0),
        'salida': int(uso.get('completion_tokens', 0) or 0),
        'cache_lectura': cache_lectura,
        'cache_escritura': 0,
    }


def _medir_ollama(respuesta) -> dict:
    """La API nativa de Ollama no habla de tokens sino de evaluaciones, y no tiene
    caché de prompt que reportar."""
    datos = respuesta or {}
    return {
        'entrada': int(datos.get('prompt_eval_count', 0) or 0),
        'salida': int(datos.get('eval_count', 0) or 0),
        'cache_lectura': 0,
        'cache_escritura': 0,
    }


def tarifa_de(modelo: str):
    """Los dos precios por millón del modelo, o None si nadie los cargó.

    Busca primero la fila exacta vigente en `TarifaModelo`; después la familia
    ('sonnet', 'opus', 'haiku'…) dentro del nombre. Lo segundo es a propósito: los
    identificadores traen versión y fecha (`claude-sonnet-4-6`) y no queremos que
    subir de versión deje un modelo sin tarifa y por lo tanto gratis.

    Devolver None en vez de 0 es deliberado: un modelo sin precio cargado se anota
    igual y queda marcado, para que aparezca como cifra que falta en vez de como
    consumo que no existió.
    """
    nombre = (modelo or '').strip().lower()
    if not nombre:
        return None

    fila = _tarifa_en_base(nombre)
    if fila is not None:
        return fila

    for familia, precios in TARIFAS_POR_OMISION.items():
        if familia in nombre:
            return precios
    return None


def _tarifa_en_base(nombre: str):
    from apps.payments.models import TarifaModelo

    try:
        tarifa = TarifaModelo.vigente_para(nombre)
    except Exception:
        # La medición nunca puede tumbar un chat: si la tabla no está migrada
        # todavía, se cae a las tarifas del código.
        logger.exception('No se pudo leer TarifaModelo para %s', nombre)
        return None
    if tarifa is None:
        return None
    return (tarifa.precio_entrada_usd_millon, tarifa.precio_salida_usd_millon)


def creditos(modelo: str, medicion: dict) -> int:
    """Los créditos que gastó una llamada, con 1 crédito = US$0,000001 de costo.

    Como el crédito es un micro-dólar, `tokens × precio_por_millón` da el resultado
    directo sin dividir por nada. Devuelve 0 si el modelo no tiene tarifa: quién es
    lo dice `sin_tarifa`.
    """
    tarifa = tarifa_de(modelo)
    if tarifa is None:
        return 0
    # Los precios llegan como int si salieron del código y como Decimal si salieron de
    # la tabla. Se normalizan acá para que la cuenta sea la misma en los dos casos.
    precio_entrada = Decimal(str(tarifa[0]))
    precio_salida = Decimal(str(tarifa[1]))
    m = medicion or VACIO
    total = (
        m.get('entrada', 0) * precio_entrada
        + m.get('salida', 0) * precio_salida
        + m.get('cache_lectura', 0) * precio_entrada * FACTOR_CACHE_LECTURA
        + m.get('cache_escritura', 0) * precio_entrada * FACTOR_CACHE_ESCRITURA
    )
    return int(round(total))


def registrar(proveedor: str, modelo: str, respuesta, organization=None,
              usuario=None, motivo: str = '') -> None:
    """Anota lo que gastó una llamada. No devuelve nada y no levanta nunca.

    Se llama justo después de recibir la respuesta del modelo, dentro del bucle y no
    al final: si la pregunta dio 8 vueltas, quedan 8 filas. Que no levante es una
    decisión: preferimos perder una medición antes que romperle la respuesta al
    usuario porque la base de datos estaba ocupada.

    `organization` puede venir en None a propósito. El chat de la landing lo usa un
    visitante que todavía no es empresa, y ese gasto es igual de real: sin la fila,
    el costo de vender queda invisible.
    """
    try:
        from apps.payments.models import ConsumoTokens

        medicion = medir(proveedor, respuesta)
        if not any(medicion.values()):
            return

        ConsumoTokens.objects.create(
            organization=organization,
            usuario=usuario if getattr(usuario, 'is_authenticated', False) else None,
            proveedor=proveedor or '',
            modelo=(modelo or '')[:120],
            motivo=(motivo or '')[:40],
            tokens_entrada=medicion['entrada'],
            tokens_salida=medicion['salida'],
            tokens_cache_lectura=medicion['cache_lectura'],
            tokens_cache_escritura=medicion['cache_escritura'],
            creditos=creditos(modelo, medicion),
            sin_tarifa=tarifa_de(modelo) is None,
        )
    except Exception:
        logger.exception('No se pudo registrar el consumo de %s/%s', proveedor, modelo)


def estado(organization) -> dict:
    """Cuánto lleva gastado la empresa en el período y cuánto le queda.

    Es lectura: informa, no corta. `bloqueada` es el veredicto que la compuerta va a
    usar cuando exista, calculado acá para que la regla viva en un solo lugar.

    El período es el que pagó la empresa (`current_period_end` menos un mes). Si no
    hay suscripción con fecha, cae al mes calendario, que es lo único defendible
    frente a alguien que está probando.
    """
    from apps.payments.models import ConsumoTokens, SaldoAdicional, Subscription
    from django.db.models import Sum

    suscripcion = (
        Subscription.objects
        .filter(organization=organization, status__in=Subscription.ESTADOS_VIGENTES)
        .select_related('plan')
        .order_by('-created_at')
        .first()
    )
    incluido = suscripcion.plan.tokens_por_mes if suscripcion else 0
    desde = _inicio_del_periodo(suscripcion)

    filas = ConsumoTokens.objects.filter(organization=organization, created_at__gte=desde)
    usado = filas.aggregate(t=Sum('creditos'))['t'] or 0
    sin_tarifa = sorted(set(filas.filter(sin_tarifa=True).values_list('modelo', flat=True)))

    adicional = SaldoAdicional.disponible_de(organization)
    disponible = max(incluido - usado, 0) + adicional

    return {
        'plan': suscripcion.plan.name if suscripcion else '',
        'incluido': incluido,
        'usado': usado,
        'adicional': adicional,
        'disponible': disponible,
        'porcentaje': round(usado * 100 / incluido, 1) if incluido else 0.0,
        'desde': desde,
        # Sin plan no hay cupo que pasarse: quien no tiene suscripción vigente ya está
        # detenido antes, por la suscripción y no por los tokens.
        'bloqueada': bool(incluido) and usado >= incluido and adicional <= 0,
        'modelos_sin_tarifa': sin_tarifa,
    }


def _inicio_del_periodo(suscripcion):
    from datetime import timedelta

    from django.utils import timezone

    fin = getattr(suscripcion, 'current_period_end', None) if suscripcion else None
    if fin:
        inicio = fin - timedelta(days=30)
        # Si la fecha de la pasarela quedó en el futuro lejano, el período que corre
        # es el que empezó, no el que termina.
        if inicio <= timezone.now():
            return inicio
    ahora = timezone.now()
    return ahora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

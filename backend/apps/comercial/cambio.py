"""El valor en pesos del dólar y la UF de un día.

Fuente: mindicador.cl, que publica los indicadores del Banco Central (dólar observado, UF) sin
pedir clave. El valor se guarda (`TipoCambio`) y no se vuelve a pedir. El dólar no se publica los
fines de semana ni festivos: vale el último día hábil anterior, como en la práctica contable.
"""

import logging
from datetime import timedelta
from decimal import Decimal, InvalidOperation

import requests

from .models import CLP, UF, USD, TipoCambio

logger = logging.getLogger(__name__)

INDICADOR = {USD: 'dolar', UF: 'uf'}
URL = 'https://mindicador.cl/api/{indicador}/{fecha}'
DIAS_HACIA_ATRAS = 7


def _pedir(moneda, fecha):
    try:
        r = requests.get(URL.format(indicador=INDICADOR[moneda], fecha=fecha.strftime('%d-%m-%Y')), timeout=10)
        r.raise_for_status()
        serie = r.json().get('serie') or []
        return Decimal(str(serie[0]['valor'])) if serie else None
    except (requests.RequestException, ValueError, KeyError, IndexError, InvalidOperation):
        logger.warning('tipo de cambio: no se pudo traer %s del %s', moneda, fecha)
        return None


def valor(moneda, fecha):
    """Pesos por unidad de `moneda` en `fecha` (o el último publicado antes). None si no hay forma."""
    if moneda == CLP:
        return Decimal('1')
    if moneda not in INDICADOR:
        return None
    guardado = TipoCambio.objects.filter(moneda=moneda, fecha__lte=fecha,
                                         fecha__gte=fecha - timedelta(days=DIAS_HACIA_ATRAS)).first()
    if guardado and guardado.fecha == fecha:
        return guardado.valor
    dia = fecha
    for _ in range(DIAS_HACIA_ATRAS):
        if guardado and guardado.fecha == dia:
            return guardado.valor
        v = _pedir(moneda, dia)
        if v is not None:
            TipoCambio.objects.update_or_create(moneda=moneda, fecha=dia, defaults={'valor': v, 'fuente': 'mindicador.cl'})
            return v
        dia -= timedelta(days=1)
    return guardado.valor if guardado else None


_intentado = set()


def actualizar_hoy(hoy):
    """Lo llama el proceso de automatizaciones en cada vuelta: deja guardado el valor del día.
    Se intenta una vez por día y moneda (el fin de semana el dólar no existe, y sin esto se
    pediría en cada vuelta)."""
    for moneda in INDICADOR:
        if (moneda, hoy) in _intentado:
            continue
        _intentado.add((moneda, hoy))
        if not TipoCambio.objects.filter(moneda=moneda, fecha=hoy).exists():
            valor(moneda, hoy)

"""
Generacion de embeddings: texto -> vector.

Una sola puerta de entrada (`embed_documentos` / `embed_consulta`) y detras un
proveedor intercambiable. Hoy el proveedor es Ollama corriendo al lado
(`embeddinggemma`, gratis y local); manana puede ser una API de pago sin que
cambie nada del resto del codigo.

Dos reglas que valen para todo el modulo:

1. **La dimension es parte del esquema.** `DIMENSION` entra en la migracion del
   `VectorField`, asi que no se puede cambiar de modelo a uno de otra dimension
   sin una migracion nueva. Por eso, si el proveedor devuelve un vector de largo
   distinto, esto falla con un mensaje claro en vez de guardar basura.

2. **Que no haya embeddings no es un error del usuario.** Si Ollama no esta
   corriendo o el modelo no esta bajado, `disponible()` da False y el producto
   sigue funcionando exactamente como antes de que existiera la busqueda
   semantica: los documentos se vuelcan al prompt y nadie ve una excepcion.
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# 768 = largo del vector de embeddinggemma. Fijo a proposito: ver regla 1 arriba.
DIMENSION = 768

# embeddinggemma es asimetrico: espera que la consulta y el documento se
# presenten con prefijos distintos, y rinde bastante peor sin ellos. El template
# de Ollama es `{{ .Prompt }}` pelado (verificado con `ollama show --template`),
# o sea que no los agrega nadie: los ponemos aca.
_PREFIJO_CONSULTA = 'task: search result | query: '
_PREFIJO_DOCUMENTO = 'title: {titulo} | text: '

_TIMEOUT = 120
_LOTE = 32

# `disponible()` se consulta en cada mensaje del chat; sin cache eso serian dos
# viajes de red extra por pregunta. None = todavia no se pregunto.
_cache_disponible = None


class EmbeddingsNoDisponibles(Exception):
    """El proveedor no esta alcanzable o el modelo no esta cargado."""


def modelo_activo() -> str:
    return getattr(settings, 'EMBEDDINGS_MODEL', 'embeddinggemma')


def _proveedor() -> str:
    return (getattr(settings, 'EMBEDDINGS_PROVIDER', 'ollama') or '').strip().lower()


def _base_url() -> str:
    return getattr(settings, 'EMBEDDINGS_BASE_URL', '') or getattr(
        settings, 'OLLAMA_BASE_URL', 'http://localhost:11434',
    )


def disponible(recargar: bool = False) -> bool:
    """¿Se pueden generar embeddings ahora mismo?

    Comprueba de verdad (un embedding de prueba), no solo que haya configuracion:
    el caso comun de falla es que el modelo no este bajado, y eso no se ve en el
    settings. El resultado queda en cache para no pagarlo en cada pregunta.
    """
    global _cache_disponible
    if recargar:
        _cache_disponible = None
    if _cache_disponible is not None:
        return _cache_disponible
    if _proveedor() == 'ninguno':
        _cache_disponible = False
        return False
    try:
        vectores = _embed_ollama(['prueba'])
        _cache_disponible = bool(vectores) and len(vectores[0]) == DIMENSION
        if not _cache_disponible:
            logger.warning(
                'Embeddings apagados: el modelo %s devolvio una dimension inesperada.',
                modelo_activo(),
            )
    except Exception as e:
        logger.warning('Embeddings apagados: %s', e)
        _cache_disponible = False
    return _cache_disponible


def embed_documentos(textos: list[str], titulos: list[str] = None) -> list[list[float]]:
    """Vectoriza fragmentos de documento para guardarlos.

    `titulos`, si viene, es el titulo del documento de cada fragmento: el modelo
    lo usa como parte del prefijo y mejora la recuperacion de un fragmento que
    por si solo no dice de que documento salio.
    """
    if not textos:
        return []
    titulos = titulos or [''] * len(textos)
    preparados = [
        _PREFIJO_DOCUMENTO.format(titulo=(t.strip() or 'none')) + texto
        for texto, t in zip(textos, titulos)
    ]
    return _embed(preparados)


def embed_consulta(consulta: str) -> list[float]:
    """Vectoriza una pregunta del usuario para buscar con ella."""
    return _embed([_PREFIJO_CONSULTA + consulta])[0]


def _embed(preparados: list[str]) -> list[list[float]]:
    if _proveedor() == 'ninguno':
        raise EmbeddingsNoDisponibles('El proveedor de embeddings esta en "ninguno".')
    vectores = []
    for i in range(0, len(preparados), _LOTE):
        vectores.extend(_embed_ollama(preparados[i:i + _LOTE]))
    for v in vectores:
        if len(v) != DIMENSION:
            raise EmbeddingsNoDisponibles(
                f'El modelo {modelo_activo()} devuelve vectores de {len(v)} dimensiones, '
                f'pero la base guarda {DIMENSION}. Cambiar de modelo exige una migracion '
                f'nueva del campo `embedding` y reindexar todo.'
            )
    return vectores


def _embed_ollama(preparados: list[str]) -> list[list[float]]:
    try:
        resp = requests.post(
            f'{_base_url()}/api/embed',
            json={'model': modelo_activo(), 'input': preparados},
            timeout=_TIMEOUT,
        )
    except requests.RequestException as e:
        raise EmbeddingsNoDisponibles(f'No se pudo hablar con Ollama: {e}') from e
    if resp.status_code != 200:
        raise EmbeddingsNoDisponibles(
            f'Ollama respondio {resp.status_code} al vectorizar: {resp.text[:200]}'
        )
    vectores = (resp.json() or {}).get('embeddings') or []
    if len(vectores) != len(preparados):
        raise EmbeddingsNoDisponibles(
            f'Ollama devolvio {len(vectores)} vectores para {len(preparados)} textos.'
        )
    return vectores

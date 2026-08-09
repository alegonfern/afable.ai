"""
Escribir un documento: la única puerta.

Todo cambio de texto pasa por acá — lo edite una persona en la pantalla o un agente con
sus herramientas. Es a propósito: si hubiera dos caminos, uno de los dos se olvidaría de
crear la versión o de reindexar, y el historial dejaría de ser confiable justo cuando se
lo necesita para revisar lo que hizo la IA.

Cada escritura hace tres cosas, en este orden:
  1. Guarda el texto nuevo en el documento.
  2. Crea la `Version` con quién lo escribió y por qué.
  3. Vuelve a indexarlo para la búsqueda semántica.

El indexado va al final y no puede voltear el guardado: si el proveedor de embeddings
está caído, el cambio se guarda igual y el índice se recupera después con
`manage.py indexar_conocimiento`.
"""
import logging

from django.db import transaction

logger = logging.getLogger(__name__)

# Tipos cuyo texto se puede editar y volver a guardar sin romper nada. Un PDF, un Word o
# un Excel se leen (se les extrae el texto) pero no se escriben de vuelta: hacerlo sin
# perder formato, estilos y formulas es otro proyecto, y a medias es peor que no hacerlo.
CONTENT_TYPES_EDITABLES = (
    'text/plain', 'text/markdown', 'text/x-markdown', 'text/csv',
    'application/json', 'text/html',
)
EXTENSIONES_EDITABLES = ('.md', '.markdown', '.txt', '.csv', '.json', '.html')


def es_editable(nombre='', content_type=''):
    """Si el texto de este archivo se puede editar en Afable."""
    ct = (content_type or '').split(';')[0].strip().lower()
    if ct in CONTENT_TYPES_EDITABLES or ct.startswith('text/'):
        return True
    return (nombre or '').lower().endswith(EXTENSIONES_EDITABLES)


class NoEditable(Exception):
    """El documento no es de un tipo que se pueda editar en el lugar."""


class TextoNoEncontrado(Exception):
    """El fragmento a reemplazar no aparece en el documento (o aparece varias veces)."""


@transaction.atomic
def escribir(doc, contenido, *, autor=None, agente=None, mensaje='', origen=None):
    """Guarda `contenido` como el texto del documento y deja la versión.

    Devuelve la `Version` creada. `agente` no vacío marca la versión como escrita por un
    agente, aunque `autor` también venga: para revisar un cambio hacen falta los dos —
    quién lo pidió y quién lo escribió.
    """
    from apps.archivos.models import ORIGEN_AGENTE, ORIGEN_PERSONA, Version

    if origen is None:
        origen = ORIGEN_AGENTE if agente is not None else ORIGEN_PERSONA

    ultimo = Version.objects.filter(document=doc).order_by('-numero').first()
    numero = (ultimo.numero if ultimo else 0) + 1

    doc.extracted_text = contenido
    doc.save(update_fields=['extracted_text'])

    version = Version.objects.create(
        document=doc, numero=numero, contenido=contenido,
        origen=origen, autor=autor, agente=agente, mensaje=mensaje[:300],
    )

    # Fuera de la transacción conceptualmente: si falla, el cambio ya está guardado.
    _reindexar(doc)
    return version


def asegurar_version_inicial(doc, autor=None, mensaje='Como se subió'):
    """La versión 1 de un documento que todavía no tiene ninguna.

    Sirve para dos cosas: que un documento recién subido ya tenga historia (y "volver al
    original" sea siempre posible), y para los que ya existían antes de que las versiones
    existieran.
    """
    from apps.archivos.models import ORIGEN_SISTEMA, Version

    if Version.objects.filter(document=doc).exists():
        return None
    # `get_or_create` y no `create`: dos pedidos que abren el mismo documento a la vez
    # entraban los dos al `if` y el segundo reventaba con IntegrityError contra
    # `un_numero_por_documento`. Con varias personas mirando el mismo archivo —que es
    # justamente para lo que sirve el producto— dejó de ser un caso raro.
    version, _ = Version.objects.get_or_create(
        document=doc, numero=1,
        defaults={
            'contenido': doc.extracted_text or '',
            'origen': ORIGEN_SISTEMA if autor is None else 'persona',
            'autor': autor,
            'mensaje': mensaje[:300],
        },
    )
    return version


def editar_por_reemplazo(doc, viejo, nuevo, *, autor=None, agente=None, mensaje=''):
    """Reemplaza un fragmento exacto por otro, como hace Claude Code.

    Es el modo de edición que se le da al agente en vez de "reescribí el documento
    entero": pedirle el texto completo de vuelta hace que reescriba de memoria lo que no
    tenía que tocar. Un reemplazo acotado no puede perder el resto del documento.

    El fragmento tiene que aparecer UNA sola vez. Si aparece varias, el agente no dijo
    cuál quería y adivinar sería cambiar la línea equivocada en silencio.
    """
    if not doc.editable:
        raise NoEditable(
            f'«{doc.title}» no es un documento de texto editable. Se puede leer, pero '
            f'para cambiarlo hay que crear uno nuevo.'
        )

    actual = doc.extracted_text or ''
    if not viejo:
        raise TextoNoEncontrado('Falta el texto a reemplazar.')

    apariciones = actual.count(viejo)
    if apariciones == 0:
        raise TextoNoEncontrado(
            'Ese texto no aparece en el documento. Lee el documento y copia el fragmento '
            'exacto que quieres cambiar, con sus espacios y saltos de línea.'
        )
    if apariciones > 1:
        raise TextoNoEncontrado(
            f'Ese texto aparece {apariciones} veces: no se sabe cuál cambiar. Incluye '
            f'más contexto alrededor para que el fragmento sea único.'
        )

    return escribir(
        doc, actual.replace(viejo, nuevo, 1),
        autor=autor, agente=agente, mensaje=mensaje or 'Edición puntual',
    )


def restaurar(doc, version, *, autor=None):
    """Vuelve el documento a una versión anterior.

    NO borra lo que vino después: crea una versión NUEVA con ese contenido. Borrar la
    historia para volver atrás es la única forma de perder trabajo de verdad, y restaurar
    algo por error tiene que ser tan reversible como cualquier otro cambio.
    """
    return escribir(
        doc, version.contenido, autor=autor,
        mensaje=f'Se volvió a la versión {version.numero}',
    )


def _reindexar(doc):
    from services.indexing import indexar_documento_sin_ruido

    try:
        indexar_documento_sin_ruido(doc)
    except Exception:
        logger.exception('No se pudo reindexar el documento %s tras editarlo', doc.pk)

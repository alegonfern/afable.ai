"""
Indexado: documento -> fragmentos vectorizados.

Se llama en los tres momentos en que el contenido de un documento cambia: cuando
el usuario sube un archivo, cuando la sincronizacion de Drive baja una version
nueva, y a mano desde `manage.py indexar_conocimiento` para lo que ya estaba
cargado antes de que existiera esto.

Reglas:

- **Reindexar es reemplazar.** Se borran los fragmentos viejos del documento y se
  generan de cero. Un indexado incremental (que trozo cambio) es mas rapido pero
  puede dejar fragmentos huerfanos afirmando cosas que el documento ya no dice, y
  eso es peor que gastar unos segundos.
- **Indexar nunca hace fallar lo que lo llamo.** Si el proveedor de embeddings no
  esta, la subida del archivo tiene que terminar bien igual: el documento queda
  sin indexar y se recupera despues con el comando. Por eso todos los enganches
  usan `indexar_documento_sin_ruido`.
"""
import logging

from services.chunking import trocear
from services.embeddings import EmbeddingsNoDisponibles, embed_documentos, modelo_activo

logger = logging.getLogger(__name__)


def indexar_documento(doc) -> int:
    """Trocea y vectoriza un documento. Devuelve cuantos fragmentos quedaron.

    Levanta `EmbeddingsNoDisponibles` si no se puede vectorizar — el llamador
    decide si eso importa. Los fragmentos viejos se borran solo cuando los nuevos
    ya estan listos, asi un fallo a mitad de camino no deja al documento peor de
    como estaba.
    """
    from apps.sources.models import Fragmento

    texto = (getattr(doc, 'extracted_text', '') or '').strip()
    if not texto:
        Fragmento.objects.filter(document=doc).delete()
        return 0

    trozos = trocear(texto)
    if not trozos:
        Fragmento.objects.filter(document=doc).delete()
        return 0

    vectores = embed_documentos(trozos, [doc.title or ''] * len(trozos))
    modelo = modelo_activo()

    Fragmento.objects.filter(document=doc).delete()
    Fragmento.objects.bulk_create([
        Fragmento(
            organization_id=doc.organization_id,
            document=doc,
            orden=i,
            texto=trozo,
            embedding=vector,
            modelo=modelo,
        )
        for i, (trozo, vector) in enumerate(zip(trozos, vectores))
    ])
    return len(trozos)


def indexar_documento_sin_ruido(doc) -> int:
    """`indexar_documento` que se traga sus errores.

    Es la version que usan los enganches (subida de archivo, sync de Drive): el
    usuario no tiene por que ver fallar una subida porque el servicio de
    embeddings esta caido.
    """
    try:
        return indexar_documento(doc)
    except EmbeddingsNoDisponibles as e:
        logger.warning('Documento %s sin indexar (embeddings no disponibles): %s', doc.pk, e)
    except Exception:
        logger.exception('Fallo el indexado del documento %s', doc.pk)
    return 0


def documentos_sin_indexar(org=None):
    """Documentos con texto pero sin fragmentos del modelo activo.

    Cubre los dos casos que hay que reindexar: el que nunca se indexo y el que se
    indexo con otro modelo (cuyos vectores ya no son comparables).
    """
    from apps.organizations.models import CompanyDocument

    qs = CompanyDocument.objects.exclude(extracted_text='')
    if org is not None:
        qs = qs.filter(organization=org)
    return qs.exclude(fragmentos__modelo=modelo_activo()).distinct()

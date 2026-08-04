"""
Recuperacion: pregunta -> los fragmentos que hablan de eso.

Es la mitad que el usuario nota de la busqueda semantica. Dos cosas que no se
pueden relajar aca:

1. **El alcance del Espacio manda.** `allowed_doc_ids` viaja hasta la consulta SQL
   igual que en `agent_tools._documentos`. Un fragmento de un documento que el
   agente no alcanza no puede volver NUNCA, ni siquiera con la mejor similitud:
   seria una fuga de datos entre Espacios por la puerta de atras.
2. **Sin embeddings no hay error, hay lista vacia.** Quien llame a esto tiene que
   poder seguir con el camino de antes (volcar los documentos al prompt).
"""
import logging

logger = logging.getLogger(__name__)

# Coseno en pgvector va de 0 (identico) a 2 (opuesto). Por encima de este corte
# los fragmentos ya no hablan del tema: entra ruido que el modelo despues cita
# como si fuera una fuente.
#
# El numero sale de medir, no de estimar. Sobre un reglamento interno en español
# vectorizado con embeddinggemma, seis preguntas que el documento SI responde
# quedaron entre 0.56 y 0.71, y cinco que no responde entre 0.83 y 0.97. 0.80 cae
# en ese hueco, con el margen mas ancho del lado de no perder un fragmento bueno.
#
# El primer valor que puse fue 0.85 y dejaba pasar "cuanto vendimos en enero"
# (0.83) contra un reglamento de personal: una pregunta de datos que se responde
# con SQL, contestada con ruido de un documento que no tiene nada que ver.
#
# OJO: la escala es propia de cada modelo de embeddings. Si se cambia
# EMBEDDINGS_MODEL, este corte hay que volver a medirlo.
DISTANCIA_MAXIMA = 0.80


def buscar(org, consulta: str, allowed_doc_ids=None, k: int = 8, distancia_maxima: float = DISTANCIA_MAXIMA):
    """Los `k` fragmentos mas parecidos a `consulta` dentro del alcance dado.

    `allowed_doc_ids` sigue la misma convencion que en todo el resto: `None` es sin
    restriccion y una lista VACIA no devuelve nada (un agente encerrado en un
    Espacio sin documentos no busca en los del resto de la empresa).

    Devuelve una lista de dicts con `documento_id`, `titulo`, `texto` y
    `distancia`, ordenada de mas parecido a menos. Lista vacia si no hay
    embeddings disponibles o no hay nada suficientemente cerca.
    """
    from pgvector.django import CosineDistance

    from apps.sources.models import Fragmento
    from services.embeddings import EmbeddingsNoDisponibles, disponible, embed_consulta, modelo_activo

    consulta = (consulta or '').strip()
    if not consulta or not disponible():
        return []
    if allowed_doc_ids is not None and not allowed_doc_ids:
        return []

    try:
        vector = embed_consulta(consulta)
    except EmbeddingsNoDisponibles as e:
        logger.warning('Busqueda semantica omitida: %s', e)
        return []

    qs = Fragmento.objects.filter(organization=org, modelo=modelo_activo())
    if allowed_doc_ids is not None:
        qs = qs.filter(document_id__in=allowed_doc_ids)

    filas = (
        qs.annotate(distancia=CosineDistance('embedding', vector))
        .filter(distancia__lte=distancia_maxima)
        .order_by('distancia')
        .select_related('document')[:k]
    )
    return [
        {
            'documento_id': f.document_id,
            'titulo': f.document.title,
            'texto': f.texto,
            'orden': f.orden,
            'distancia': float(f.distancia),
        }
        for f in filas
    ]


def hay_indice(org, allowed_doc_ids=None) -> bool:
    """¿Esta empresa tiene algo indexado y utilizable con el modelo activo?

    Sirve para decidir entre los dos caminos: si no hay indice, volcar los
    documentos al prompt sigue siendo lo correcto.
    """
    from apps.sources.models import Fragmento
    from services.embeddings import modelo_activo

    qs = Fragmento.objects.filter(organization=org, modelo=modelo_activo())
    if allowed_doc_ids is not None:
        if not allowed_doc_ids:
            return False
        qs = qs.filter(document_id__in=allowed_doc_ids)
    return qs.exists()


def como_bloque_de_prompt(resultados) -> str:
    """Los resultados, listos para pegar en el system prompt.

    Cada fragmento se rotula con el titulo de su documento para que el agente
    pueda citar la fuente sin inventarla.
    """
    if not resultados:
        return ''
    piezas = [
        f'### [id={r["documento_id"]}] {r["titulo"]} (fragmento {r["orden"] + 1})\n{r["texto"]}'
        for r in resultados
    ]
    return '\n\n'.join(piezas)

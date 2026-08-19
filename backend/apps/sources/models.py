"""
Fuentes de conocimiento: el corpus troceado y vectorizado de la empresa.

Un `Fragmento` es un pedazo de un documento con su embedding al lado. Es lo que
hace posible el metodo Knowledge > Search: en vez de volcar los documentos
enteros al prompt (que se acaba en cuanto la empresa tiene mas texto del que
cabe), se recuperan solo los pedazos que hablan de lo que pregunto el usuario.

El documento sigue siendo la unidad que el usuario ve y administra
(`CompanyDocument`); los fragmentos son derivados y se pueden borrar y volver a
generar en cualquier momento sin perder nada.
"""
from django.db import models
from pgvector.django import HnswIndex, VectorField

from services.embeddings import DIMENSION


class Fragmento(models.Model):
    """Un pedazo de documento, con su vector.

    Vive colgado del documento (`on_delete=CASCADE`): borrar el documento se
    lleva sus fragmentos, asi no queda conocimiento fantasma respondiendo
    preguntas sobre un archivo que el usuario ya elimino.

    Se guarda tambien la `organization` aunque se pueda deducir del documento:
    toda busqueda filtra por empresa primero, y tenerlo aca ahorra el join en la
    consulta que mas se repite.
    """

    organization = models.ForeignKey(
        'organizations.Organization', on_delete=models.CASCADE, related_name='fragmentos',
    )
    document = models.ForeignKey(
        'organizations.CompanyDocument', on_delete=models.CASCADE, related_name='fragmentos',
    )
    orden = models.PositiveIntegerField(
        help_text='Posicion del fragmento dentro del documento, desde 0.',
    )
    texto = models.TextField()
    embedding = VectorField(dimensions=DIMENSION)
    # Con que modelo se vectorizo. Si se cambia el modelo, los vectores viejos no
    # son comparables con los nuevos: este campo permite detectarlo y reindexar en
    # vez de devolver resultados sin sentido.
    modelo = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['document_id', 'orden']
        constraints = [
            models.UniqueConstraint(
                fields=['document', 'orden'], name='fragmento_unico_por_documento',
            ),
        ]
        indexes = [
            models.Index(fields=['organization'], name='fragmento_org_idx'),
            # HNSW con distancia coseno: es la que usa `retrieval.buscar`.
            HnswIndex(
                name='fragmento_embedding_hnsw',
                fields=['embedding'],
                m=16,
                ef_construction=64,
                opclasses=['vector_cosine_ops'],
            ),
        ]

    def __str__(self):
        return f'{self.document_id}#{self.orden}'

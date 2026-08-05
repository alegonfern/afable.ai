"""Archivos de la Sesión.

Son `CompanyDocument` con `sesion` apuntando acá, no un modelo propio: así el archivo
que alguien deja en una Sesión pasa por la misma extracción de texto y el mismo
indexado semántico que un documento de la empresa, y los agentes lo alcanzan sin que
haya que construir un segundo camino.

Lo que esta vista agrega sobre el repositorio de la empresa es el recorte por Sesión, y
que subir acá lo etiqueta solo.
"""
import logging

from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organizations.models import CompanyDocument

from .tareas import resolver

logger = logging.getLogger(__name__)

MAX_ARCHIVO_MB = 10
ORDENES = {
    'reciente': '-created_at',
    'nombre': 'title',
}


def serializar(doc, request=None):
    return {
        'id': doc.id,
        'title': doc.title,
        'category': doc.category,
        'content_type': doc.content_type,
        'summary': doc.summary,
        'processing_error': doc.processing_error,
        'source': doc.source,
        'author': (
            (doc.uploaded_by.get_full_name() or doc.uploaded_by.email)
            if doc.uploaded_by else None
        ),
        'url': request.build_absolute_uri(doc.file.url) if (request and doc.file) else None,
        'created_at': doc.created_at,
    }


class ArchivoListCreateView(APIView):
    """GET y POST /api/v1/sesiones/<sesion_slug>/archivos/?workspace=<slug>"""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request, sesion_slug):
        sesion, error = resolver(request, sesion_slug)
        if error:
            return error

        docs = CompanyDocument.objects.filter(sesion=sesion).select_related('uploaded_by')
        q = (request.query_params.get('q') or '').strip()
        if q:
            docs = docs.filter(title__icontains=q)
        orden = ORDENES.get(request.query_params.get('orden'), ORDENES['reciente'])
        docs = docs.order_by(orden)

        return Response({
            'count': docs.count(),
            'results': [serializar(d, request) for d in docs],
        })

    def post(self, request, sesion_slug):
        sesion, error = resolver(request, sesion_slug)
        if error:
            return error

        archivo = request.data.get('file')
        if not archivo:
            return Response(
                {'detail': 'No llegó ningún archivo.'}, status=status.HTTP_400_BAD_REQUEST,
            )
        if archivo.size > MAX_ARCHIVO_MB * 1024 * 1024:
            return Response(
                {'detail': f'El archivo pasa los {MAX_ARCHIVO_MB}MB.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        organization = sesion.workspace.organization
        if organization is None:
            return Response(
                {'detail': 'Este Workspace todavía no está enlazado a una empresa.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from services.documentos import es_editable

        content_type = getattr(archivo, 'content_type', '') or ''
        doc = CompanyDocument.objects.create(
            organization=organization, sesion=sesion, uploaded_by=request.user,
            title=(request.data.get('title') or archivo.name)[:255],
            category=request.data.get('category') or 'otro',
            file=archivo,
            content_type=content_type,
            # Visible para el equipo de la Sesión: quien entra a la Sesión lo ve.
            is_public=True,
            editable=es_editable(archivo.name, content_type),
        )

        from services.document_processing import process_document

        resultado = process_document(doc.file, doc.content_type)
        doc.extracted_text = resultado['extracted_text']
        doc.summary = resultado['summary']
        doc.processing_error = resultado['error']
        doc.save(update_fields=['extracted_text', 'summary', 'processing_error'])

        # Mismo enganche que la subida al repositorio de la empresa: si el proveedor de
        # embeddings no está, el archivo queda sin indexar y la subida termina bien.
        from services.indexing import indexar_documento_sin_ruido

        indexar_documento_sin_ruido(doc)

        from services.documentos import asegurar_version_inicial

        asegurar_version_inicial(doc, autor=request.user)

        return Response(serializar(doc, request), status=status.HTTP_201_CREATED)


class ArchivoDetailView(APIView):
    """DELETE de un archivo de la Sesión."""

    permission_classes = [IsAuthenticated]

    def delete(self, request, sesion_slug, pk):
        sesion, error = resolver(request, sesion_slug)
        if error:
            return error
        doc = CompanyDocument.objects.filter(sesion=sesion, pk=pk).first()
        if doc is None:
            return Response(
                {'detail': 'Archivo no encontrado.'}, status=status.HTTP_404_NOT_FOUND,
            )
        doc.file.delete(save=False)
        doc.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

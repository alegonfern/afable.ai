"""El explorador de archivos: carpetas, contenido, edición e historial.

Permiso: por ahora el del Workspace. Quien es miembro ve y edita los archivos de su
empresa. Los permisos por archivo y por carpeta (compartir con alguien, lectura contra
edición) son el bloque siguiente — hasta que existan, esto NO es un lugar para guardar
algo que no pueda ver el resto del equipo, y la pantalla lo dice.
"""
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organizations.models import CompanyDocument
from apps.workspaces.permissions import require_membership

from .models import Carpeta, Version


def _org(request):
    """La empresa del Workspace que viene en el pedido. Devuelve (org, error)."""
    slug = request.query_params.get('workspace') or request.data.get('workspace')
    if not slug:
        return None, Response(
            {'detail': 'Falta el Workspace.'}, status=status.HTTP_400_BAD_REQUEST,
        )
    membership = require_membership(request.user, slug)
    org = membership.workspace.organization
    if org is None:
        return None, Response(
            {'detail': 'Este Workspace todavía no está enlazado a una empresa.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return org, None


def serializar_carpeta(carpeta):
    return {
        'id': carpeta.id,
        'name': carpeta.name,
        'parent': carpeta.parent_id,
        'documentos': carpeta.documentos.count(),
        'hijas': carpeta.hijas.count(),
        'updated_at': carpeta.updated_at,
    }


def serializar_documento(doc, request=None):
    ultima = doc.versiones.first()   # ordering = ['-numero']
    return {
        'id': doc.id,
        'title': doc.title,
        'carpeta': doc.carpeta_id,
        'editable': doc.editable,
        'content_type': doc.content_type,
        'sesion': doc.sesion_id,
        'source': doc.source,
        'summary': doc.summary,
        'processing_error': doc.processing_error,
        'versiones': doc.versiones.count(),
        'ultima_version': (
            {'numero': ultima.numero, 'quien': ultima.quien, 'cuando': ultima.created_at,
             'mensaje': ultima.mensaje}
            if ultima else None
        ),
        'url': request.build_absolute_uri(doc.file.url) if (request and doc.file) else None,
        'created_at': doc.created_at,
    }


class ExploradorView(APIView):
    """GET /api/v1/archivos/?workspace=<slug>&carpeta=<id>

    Sin `carpeta` devuelve la raíz. Trae el árbol completo (para el panel izquierdo) más
    el contenido de la carpeta abierta: un solo viaje, que es como se usa la pantalla.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        org, error = _org(request)
        if error:
            return error

        todas = list(
            Carpeta.objects.filter(organization=org)
            .select_related('parent').prefetch_related('documentos', 'hijas')
        )

        actual = None
        pedida = request.query_params.get('carpeta')
        if pedida and pedida != 'raiz':
            actual = next((c for c in todas if str(c.pk) == str(pedida)), None)
            if actual is None:
                return Response(
                    {'detail': 'Carpeta no encontrada.'}, status=status.HTTP_404_NOT_FOUND,
                )

        docs = CompanyDocument.objects.filter(
            organization=org, carpeta=actual,
        ).prefetch_related('versiones').order_by('title')

        q = (request.query_params.get('q') or '').strip()
        if q:
            # Buscar mira TODA la empresa, no solo la carpeta abierta: quien busca un
            # archivo no sabe dónde está — si lo supiera, navegaría hasta él.
            docs = CompanyDocument.objects.filter(
                organization=org, title__icontains=q,
            ).prefetch_related('versiones').order_by('title')

        return Response({
            'arbol': [serializar_carpeta(c) for c in todas],
            'carpeta': serializar_carpeta(actual) if actual else None,
            'migas': [{'id': c.id, 'name': c.name} for c in (actual.ancestros() if actual else [])],
            'subcarpetas': [
                serializar_carpeta(c) for c in todas
                if c.parent_id == (actual.pk if actual else None)
            ],
            'documentos': [serializar_documento(d, request) for d in docs],
            'buscando': bool(q),
        })


class CarpetaListCreateView(APIView):
    """POST /api/v1/archivos/carpetas/ — crear una carpeta."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        org, error = _org(request)
        if error:
            return error

        name = (request.data.get('name') or '').strip()[:120]
        if not name:
            return Response(
                {'detail': 'La carpeta necesita un nombre.'}, status=status.HTTP_400_BAD_REQUEST,
            )

        padre = None
        if request.data.get('parent'):
            padre = Carpeta.objects.filter(
                organization=org, pk=request.data['parent'],
            ).first()
            if padre is None:
                return Response(
                    {'detail': 'La carpeta donde quieres crearla no existe.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if Carpeta.objects.filter(organization=org, parent=padre, name=name).exists():
            return Response(
                {'detail': f'Ya hay una carpeta «{name}» acá.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        carpeta = Carpeta.objects.create(
            organization=org, parent=padre, name=name, created_by=request.user,
        )
        return Response(serializar_carpeta(carpeta), status=status.HTTP_201_CREATED)


class CarpetaDetailView(APIView):
    """PATCH y DELETE de una carpeta."""

    permission_classes = [IsAuthenticated]

    def _carpeta(self, request, pk):
        org, error = _org(request)
        if error:
            return None, None, error
        carpeta = Carpeta.objects.filter(organization=org, pk=pk).first()
        if carpeta is None:
            return None, None, Response(
                {'detail': 'Carpeta no encontrada.'}, status=status.HTTP_404_NOT_FOUND,
            )
        return carpeta, org, None

    def patch(self, request, pk):
        carpeta, org, error = self._carpeta(request, pk)
        if error:
            return error

        if 'name' in request.data:
            name = (request.data.get('name') or '').strip()[:120]
            if not name:
                return Response(
                    {'detail': 'La carpeta necesita un nombre.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            carpeta.name = name

        if 'parent' in request.data:
            destino = None
            if request.data.get('parent'):
                destino = Carpeta.objects.filter(
                    organization=org, pk=request.data['parent'],
                ).first()
                if destino is None:
                    return Response(
                        {'detail': 'La carpeta de destino no existe.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                # Meter una carpeta dentro de sí misma o de una de sus hijas deja un
                # ciclo, y con él una rama que desaparece del árbol.
                if destino.pk == carpeta.pk or destino.es_descendiente_de(carpeta):
                    return Response(
                        {'detail': 'No se puede mover una carpeta dentro de sí misma.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            carpeta.parent = destino

        choca = Carpeta.objects.filter(
            organization=org, parent=carpeta.parent, name=carpeta.name,
        ).exclude(pk=carpeta.pk).exists()
        if choca:
            return Response(
                {'detail': f'Ya hay una carpeta «{carpeta.name}» en ese lugar.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        carpeta.save()
        return Response(serializar_carpeta(carpeta))

    def delete(self, request, pk):
        """Borra la carpeta. Sus documentos NO se borran: suben a la raíz.

        Es `SET_NULL` en el modelo, y es deliberado: borrar una carpeta no puede llevarse
        el trabajo que hay dentro sin que nadie lo haya pedido.
        """
        carpeta, _, error = self._carpeta(request, pk)
        if error:
            return error
        carpeta.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DocumentoDetailView(APIView):
    """PATCH de un documento: renombrarlo o moverlo de carpeta."""

    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        org, error = _org(request)
        if error:
            return error
        doc = CompanyDocument.objects.filter(organization=org, pk=pk).first()
        if doc is None:
            return Response(
                {'detail': 'Documento no encontrado.'}, status=status.HTTP_404_NOT_FOUND,
            )

        if 'title' in request.data:
            title = (request.data.get('title') or '').strip()[:255]
            if not title:
                return Response(
                    {'detail': 'El documento necesita un nombre.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            doc.title = title

        if 'carpeta' in request.data:
            destino = None
            if request.data.get('carpeta'):
                destino = Carpeta.objects.filter(
                    organization=org, pk=request.data['carpeta'],
                ).first()
                if destino is None:
                    return Response(
                        {'detail': 'La carpeta de destino no existe.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            doc.carpeta = destino

        doc.save()
        return Response(serializar_documento(doc, request))


class ContenidoView(APIView):
    """GET y PUT del texto de un documento."""

    permission_classes = [IsAuthenticated]

    def _doc(self, request, pk):
        org, error = _org(request)
        if error:
            return None, error
        doc = CompanyDocument.objects.filter(organization=org, pk=pk).first()
        if doc is None:
            return None, Response(
                {'detail': 'Documento no encontrado.'}, status=status.HTTP_404_NOT_FOUND,
            )
        return doc, None

    def get(self, request, pk):
        doc, error = self._doc(request, pk)
        if error:
            return error
        from services.documentos import asegurar_version_inicial

        asegurar_version_inicial(doc)
        return Response({
            **serializar_documento(doc, request),
            'contenido': doc.extracted_text or '',
        })

    def put(self, request, pk):
        doc, error = self._doc(request, pk)
        if error:
            return error

        from services.documentos import NoEditable, asegurar_version_inicial, escribir

        if not doc.editable:
            return Response(
                {'detail': f'«{doc.title}» no es un documento de texto editable. Se puede '
                           f'leer, pero para cambiarlo hay que crear uno nuevo.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # La versión 1 es el estado con el que entró: sin esto, el primer cambio dejaría
        # el original sin registro y "volver al original" sería imposible.
        asegurar_version_inicial(doc)

        try:
            version = escribir(
                doc, request.data.get('contenido') or '',
                autor=request.user, mensaje=request.data.get('mensaje') or '',
            )
        except NoEditable as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            **serializar_documento(doc, request),
            'contenido': doc.extracted_text or '',
            'version': {'numero': version.numero, 'quien': version.quien},
        })


class VersionesView(APIView):
    """GET del historial de un documento."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        org, error = _org(request)
        if error:
            return error
        doc = CompanyDocument.objects.filter(organization=org, pk=pk).first()
        if doc is None:
            return Response(
                {'detail': 'Documento no encontrado.'}, status=status.HTTP_404_NOT_FOUND,
            )
        from services.documentos import asegurar_version_inicial

        asegurar_version_inicial(doc)
        versiones = doc.versiones.select_related('autor', 'agente')
        return Response({
            'count': versiones.count(),
            'results': [
                {
                    'numero': v.numero,
                    'quien': v.quien,
                    'origen': v.origen,
                    'mensaje': v.mensaje,
                    'largo': len(v.contenido or ''),
                    'created_at': v.created_at,
                }
                for v in versiones
            ],
        })


class VersionDetailView(APIView):
    """GET el contenido de una versión, y POST para restaurarla."""

    permission_classes = [IsAuthenticated]

    def _version(self, request, pk, numero):
        org, error = _org(request)
        if error:
            return None, None, error
        doc = CompanyDocument.objects.filter(organization=org, pk=pk).first()
        if doc is None:
            return None, None, Response(
                {'detail': 'Documento no encontrado.'}, status=status.HTTP_404_NOT_FOUND,
            )
        version = Version.objects.filter(document=doc, numero=numero).first()
        if version is None:
            return None, None, Response(
                {'detail': 'Esa versión no existe.'}, status=status.HTTP_404_NOT_FOUND,
            )
        return doc, version, None

    def get(self, request, pk, numero):
        _, version, error = self._version(request, pk, numero)
        if error:
            return error
        return Response({
            'numero': version.numero,
            'quien': version.quien,
            'mensaje': version.mensaje,
            'contenido': version.contenido,
            'created_at': version.created_at,
        })

    def post(self, request, pk, numero):
        doc, version, error = self._version(request, pk, numero)
        if error:
            return error
        if not doc.editable:
            return Response(
                {'detail': 'Este documento no se puede editar, así que tampoco restaurar.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from services.documentos import restaurar

        nueva = restaurar(doc, version, autor=request.user)
        return Response({
            **serializar_documento(doc, request),
            'contenido': doc.extracted_text or '',
            'version': {'numero': nueva.numero, 'quien': nueva.quien},
        })

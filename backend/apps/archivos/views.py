"""El explorador de archivos: carpetas, contenido, edición e historial.

Permiso: por ahora el del Workspace. Quien es miembro ve y edita los archivos de su
empresa. Los permisos por archivo y por carpeta (compartir con alguien, lectura contra
edición) son el bloque siguiente — hasta que existan, esto NO es un lugar para guardar
algo que no pueda ver el resto del equipo, y la pantalla lo dice.
"""
import logging
import re

from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organizations.models import CompanyDocument
from apps.workspaces.permissions import require_membership

from .models import Carpeta, Version

logger = logging.getLogger(__name__)


def _org(request):
    """La empresa del Workspace del pedido. Devuelve (org, error).

    Deja el `membership` en `request.membership` para que las vistas resuelvan permisos
    sin volver a consultarlo — los permisos de archivos necesitan el rol.
    """
    slug = request.query_params.get('workspace') or request.data.get('workspace')
    if not slug:
        return None, Response(
            {'detail': 'Falta el Workspace.'}, status=status.HTTP_400_BAD_REQUEST,
        )
    membership = require_membership(request.user, slug)
    request.membership = membership
    org = membership.organization
    if org is None:
        return None, Response(
            {'detail': 'Este Workspace todavía no está enlazado a una empresa.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return org, None


def serializar_carpeta(carpeta, nivel=None):
    return {
        'id': carpeta.id,
        'name': carpeta.name,
        'parent': carpeta.parent_id,
        'documentos': carpeta.documentos.count(),
        'hijas': carpeta.hijas.count(),
        'restringida': carpeta.restringida,
        'compartida_con': carpeta.permisos.count(),
        'mi_nivel': nivel,
        'updated_at': carpeta.updated_at,
    }


def serializar_documento(doc, request=None, nivel=None):
    ultima = doc.versiones.first()   # ordering = ['-numero']
    return {
        'restringido': doc.restringido,
        'compartido_con': doc.permisos.count(),
        'mi_nivel': nivel,
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
        # ⚠️ La ruta de la API, NO `doc.file.url`. Esa entregaba el archivo sin sesión a
        # cualquiera que tuviera la dirección.
        'url': (
            request.build_absolute_uri(f'/api/v1/archivos/documentos/{doc.pk}/archivo/')
            if (request and doc.file) else None
        ),
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

        from .permisos import carpetas_visibles, documentos_visibles, nivel_sobre_carpeta

        membership = request.membership
        # Solo lo que esta persona ve: una carpeta restringida ajena no aparece ni en el
        # árbol. Que no exista para quien no entra es más simple que un "sin acceso".
        todas = carpetas_visibles(request.user, org, membership)

        actual = None
        pedida = request.query_params.get('carpeta')
        if pedida and pedida != 'raiz':
            actual = next((c for c in todas if str(c.pk) == str(pedida)), None)
            if actual is None:
                return Response(
                    {'detail': 'Carpeta no encontrada.'}, status=status.HTTP_404_NOT_FOUND,
                )

        # Los documentos también salen del filtro de permisos, no de la tabla entera.
        alcanzables = documentos_visibles(request.user, org, membership)
        # Y el Workspace elegido arriba los acota: es lo que hace que el conmutador
        # signifique algo también acá. Un documento que no está en ningún Workspace
        # pertenece a la empresa entera, así que se ve siempre — si desapareciera al
        # elegir un área, cargar un archivo sin asignarlo lo volvería invisible.
        espacio = (request.query_params.get('espacio') or '').strip()
        # Lo que el filtro deja fuera se CUENTA antes de aplicarlo. Filtrar en silencio es
        # lo que hace creer que un archivo se perdió: la pantalla tiene que poder decir
        # "mostrando 3 de 11" y ofrecer la salida.
        sin_filtrar = alcanzables
        if espacio:
            from django.db.models import Q
            alcanzables = alcanzables.filter(
                Q(workspaces__slug=espacio) | Q(workspaces__isnull=True)
            ).distinct()
        docs = alcanzables.filter(carpeta=actual).prefetch_related(
            'versiones', 'permisos',
        ).order_by('title')

        q = (request.query_params.get('q') or '').strip()
        if q:
            # Buscar mira TODA la empresa, no solo la carpeta abierta: quien busca un
            # archivo no sabe dónde está — si lo supiera, navegaría hasta él. Pero solo
            # entre los que puede ver.
            docs = alcanzables.filter(title__icontains=q).prefetch_related(
                'versiones', 'permisos',
            ).order_by('title')

        def nivel_de(doc):
            from .permisos import nivel_sobre_documento
            return nivel_sobre_documento(request.user, doc, membership)

        ocultos = 0
        if espacio:
            mismos = sin_filtrar.filter(title__icontains=q) if q else sin_filtrar.filter(carpeta=actual)
            ocultos = max(0, mismos.count() - docs.count())

        return Response({
            # Cuántos dejó fuera el Workspace elegido. Cero significa que el filtro no
            # está escondiendo nada, y entonces la pantalla no dice nada: un aviso que
            # aparece siempre se deja de leer.
            'ocultos_por_espacio': ocultos,
            'arbol': [
                serializar_carpeta(c, nivel_sobre_carpeta(request.user, c, membership))
                for c in todas
            ],
            'carpeta': (
                serializar_carpeta(actual, nivel_sobre_carpeta(request.user, actual, membership))
                if actual else None
            ),
            'migas': [{'id': c.id, 'name': c.name} for c in (actual.ancestros() if actual else [])],
            'subcarpetas': [
                serializar_carpeta(c, nivel_sobre_carpeta(request.user, c, membership))
                for c in todas
                if c.parent_id == (actual.pk if actual else None)
            ],
            'documentos': [serializar_documento(d, request, nivel_de(d)) for d in docs],
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

        from .permisos import puede_editar, puede_ver

        if not puede_ver(request.user, doc, request.membership):
            return Response(
                {'detail': 'Documento no encontrado.'}, status=status.HTTP_404_NOT_FOUND,
            )
        if not puede_editar(request.user, doc, request.membership):
            return Response(
                {'detail': 'Puede ver este archivo, pero no renombrarlo ni moverlo.'},
                status=status.HTTP_403_FORBIDDEN,
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


class ExportarPdfView(APIView):
    """Descargar un documento como PDF con formato, listo para mandar.

    Existe porque hasta acá todo lo que Afable producía se quedaba adentro: no había nada
    que se le pudiera pasar a un cliente. Un informe o una propuesta que sale prolija en
    PDF es lo que convierte el trabajo del agente en algo entregable.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        from django.http import HttpResponse

        from services.exportar_pdf import desde_documento

        doc, error = ContenidoView()._doc(request, pk)
        if error:
            return error

        pdf = desde_documento(doc)
        respuesta = HttpResponse(pdf, content_type='application/pdf')
        nombre = (doc.title or 'documento').replace('"', "'")
        respuesta['Content-Disposition'] = f'attachment; filename="{nombre}.pdf"'
        return respuesta


class VistaView(APIView):
    """Cómo se muestra este archivo: planilla, documento con formato, PDF o texto.

    Va aparte de `ContenidoView` —que es el texto editable— porque son dos preguntas
    distintas: qué se puede EDITAR y cómo se VE. Una planilla se ve como tabla aunque su
    edición siga siendo por celdas.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        from services.vista_de_documento import vista_de

        doc, error = ContenidoView()._doc(request, pk)
        if error:
            return error
        return Response({'titulo': doc.title, **vista_de(doc)})


class ContenidoView(APIView):
    """GET y PUT del texto de un documento."""

    permission_classes = [IsAuthenticated]

    def _doc(self, request, pk, para_editar=False):
        org, error = _org(request)
        if error:
            return None, error
        doc = CompanyDocument.objects.filter(organization=org, pk=pk).first()
        if doc is None:
            return None, Response(
                {'detail': 'Documento no encontrado.'}, status=status.HTTP_404_NOT_FOUND,
            )
        from .permisos import puede_editar, puede_ver

        # No verlo devuelve 404 y no 403: para quien no entra, el archivo no existe. Un
        # 403 confirmaría que existe y filtraría su id.
        if not puede_ver(request.user, doc, request.membership):
            return None, Response(
                {'detail': 'Documento no encontrado.'}, status=status.HTTP_404_NOT_FOUND,
            )
        # Verlo pero no poder editarlo SÍ es un 403: la diferencia importa.
        if para_editar and not puede_editar(request.user, doc, request.membership):
            return None, Response(
                {'detail': 'Puede ver este archivo, pero no editarlo.'},
                status=status.HTTP_403_FORBIDDEN,
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
        doc, error = self._doc(request, pk, para_editar=True)
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
        from .permisos import puede_ver

        if doc is None or not puede_ver(request.user, doc, request.membership):
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
        from .permisos import puede_ver

        if doc is None or not puede_ver(request.user, doc, request.membership):
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
        from .permisos import puede_editar

        if not puede_editar(request.user, doc, request.membership):
            return Response(
                {'detail': 'Puede ver este archivo, pero no restaurar una versión.'},
                status=status.HTTP_403_FORBIDDEN,
            )
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


class CambiosDeVersionView(APIView):
    """Qué cambió EXACTAMENTE en una versión, comparada con la anterior.

    ⭐ El historial ya decía *que* alguien cambió algo y *cuándo*. Eso alcanza para
    auditar después, pero no para decidir: quien recibe "el agente editó el contrato" no
    tiene forma de saber si lo que hizo está bien sin leer el documento entero y
    acordarse de cómo estaba antes. Nadie hace eso, así que en la práctica se acepta a
    ciegas.

    Se devuelven las líneas agregadas y quitadas, no un texto para leer: la pantalla las
    pinta, y así el cambio se mira en dos segundos.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, pk, numero):
        import difflib

        doc, version, error = VersionDetailView()._version(request, pk, numero)
        if error:
            return error

        anterior = (
            Version.objects.filter(document=doc, numero__lt=numero)
            .order_by('-numero').first()
        )
        antes = (anterior.contenido if anterior else '').splitlines()
        despues = (version.contenido or '').splitlines()

        lineas = []
        for linea in difflib.unified_diff(antes, despues, lineterm='', n=1):
            # Las tres primeras marcas de `unified_diff` son encabezados del formato, no
            # contenido: mostrarlas sería filtrar la herramienta a la pantalla.
            if linea.startswith(('---', '+++')):
                continue
            if linea.startswith('@@'):
                lineas.append({'tipo': 'salto', 'texto': ''})
            elif linea.startswith('+'):
                lineas.append({'tipo': 'mas', 'texto': linea[1:]})
            elif linea.startswith('-'):
                lineas.append({'tipo': 'menos', 'texto': linea[1:]})
            else:
                lineas.append({'tipo': 'igual', 'texto': linea[1:] if linea else ''})

        return Response({
            'numero': version.numero,
            'quien': version.quien,
            'mensaje': version.mensaje,
            'primera': anterior is None,
            'lineas': lineas,
            # ⚠️ Se dice de frente si "deshacer" alcanza al archivo o solo al texto: en un
            # binario la versión guarda el TEXTO extraído, así que restaurar NO devuelve
            # el .xlsx anterior. Ofrecer un botón que promete más de lo que hace sería
            # peor que no ofrecerlo.
            'reversible': bool(doc.editable),
        })


class ArchivoView(APIView):
    """El archivo mismo, servido CON PERMISO.

    ⭐ **Por qué existe.** Los documentos vivían en `/media/…` y Django los entregaba a
    cualquiera que tuviera la dirección: sin sesión, sin ser de la empresa, sin ser
    miembro. Se comprobó con un `curl` sin token — 200 y el contenido completo. El nombre
    del archivo lleva un sufijo al azar, pero eso es dificultad para adivinar, no control
    de acceso: la dirección viaja en cada respuesta de la API.

    Para una empresa que sube su contrato o su lista de precios, eso es exactamente lo que
    vino a evitar cuando eligió una herramienta en vez de un Drive compartido.

    Pasa por el mismo embudo que leer el contenido (`ContenidoView._doc`): quien no ve el
    documento, tampoco baja el archivo.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        from django.http import FileResponse

        doc, error = ContenidoView()._doc(request, pk)
        if error:
            return error
        if not doc.file:
            return Response(
                {'detail': 'Este documento no tiene archivo.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            archivo = doc.file.open('rb')
        except FileNotFoundError:
            # El registro existe y el archivo no: pasa con documentos de ejemplo y con
            # respaldos restaurados a medias. Decirlo es mejor que un 500 sin explicación.
            return Response(
                {'detail': 'El archivo no está disponible.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        return FileResponse(
            archivo,
            content_type=doc.content_type or 'application/octet-stream',
            # `inline`: un PDF se mira en el visor sin bajarlo. Bajar es una acción aparte.
            as_attachment=False,
            filename=re.sub(r'[/\\?%*:|"<>]', '-', doc.title)[:80],
        )


MAX_ARCHIVO_MB = 10


class SubirView(APIView):
    """POST /api/v1/archivos/subir/ — sube un archivo a una carpeta.

    Endpoint propio y no el del repositorio de la empresa: ese pide el id de la
    Organization en la URL y no sabe de carpetas, así que subir desde el explorador
    habría sido "subir y después mover", dos viajes y un estado intermedio raro si el
    segundo falla.
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        org, error = _org(request)
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

        carpeta = None
        if request.data.get('carpeta'):
            carpeta = Carpeta.objects.filter(
                organization=org, pk=request.data['carpeta'],
            ).first()
            if carpeta is None:
                return Response(
                    {'detail': 'La carpeta no existe.'}, status=status.HTTP_400_BAD_REQUEST,
                )

        from services.documentos import asegurar_version_inicial, es_editable

        content_type = getattr(archivo, 'content_type', '') or ''
        doc = CompanyDocument.objects.create(
            organization=org, uploaded_by=request.user, carpeta=carpeta,
            title=(request.data.get('title') or archivo.name)[:255],
            category='otro', file=archivo, content_type=content_type,
            is_public=True, editable=es_editable(archivo.name, content_type),
        )

        from services.document_processing import process_document

        resultado = process_document(doc.file, doc.content_type, doc.organization)
        doc.extracted_text = resultado['extracted_text']
        doc.summary = resultado['summary']
        doc.processing_error = resultado['error']
        doc.save(update_fields=['extracted_text', 'summary', 'processing_error'])

        from services.indexing import indexar_documento_sin_ruido

        indexar_documento_sin_ruido(doc)
        asegurar_version_inicial(doc, autor=request.user)

        return Response(serializar_documento(doc, request), status=status.HTTP_201_CREATED)


class CompartirView(APIView):
    """GET, POST y DELETE de con quién está compartida una carpeta o un archivo.

    `POST /archivos/compartir/` con `carpeta` o `documento`, y:
      - `restringido`: prende o apaga la restricción.
      - `ids` + `nivel`: le da permiso a esas personas (varias en un solo pedido).
      - `workspace_nivel`: el nivel para **todo el Workspace**, o `null` para quitarlo.

    `workspace_nivel` existe porque el caso más común de una empresa es "que lo vea todo el
    equipo, pero que solo estos dos lo editen", y eso eran tantos permisos como personas.

    `DELETE` con `ids` les saca el permiso; con `todo_el_workspace: true` saca el del
    Workspace (no `workspace`: esa clave ya es el slug del Workspace del pedido).

    Solo quien puede EDITAR el ítem cambia con quién está compartido: dejar que alguien
    con permiso de lectura reparta accesos vaciaría de sentido el nivel.
    """

    permission_classes = [IsAuthenticated]

    def _item(self, request):
        """La carpeta o el documento del pedido, ya comprobado. Devuelve (carpeta, doc, error)."""
        org, error = _org(request)
        if error:
            return None, None, error

        from .permisos import nivel_sobre_carpeta, puede_editar
        from .models import NIVEL_EDICION

        carpeta_id = request.data.get('carpeta') or request.query_params.get('carpeta')
        doc_id = request.data.get('documento') or request.query_params.get('documento')

        if carpeta_id:
            carpeta = Carpeta.objects.filter(organization=org, pk=carpeta_id).first()
            nivel = nivel_sobre_carpeta(request.user, carpeta, request.membership) if carpeta else None
            if carpeta is None or nivel is None:
                return None, None, Response(
                    {'detail': 'Carpeta no encontrada.'}, status=status.HTTP_404_NOT_FOUND,
                )
            if nivel != NIVEL_EDICION:
                return None, None, Response(
                    {'detail': 'Puede ver esta carpeta, pero no cambiar con quién está compartida.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
            return carpeta, None, None

        if doc_id:
            doc = CompanyDocument.objects.filter(organization=org, pk=doc_id).first()
            from .permisos import puede_ver

            if doc is None or not puede_ver(request.user, doc, request.membership):
                return None, None, Response(
                    {'detail': 'Documento no encontrado.'}, status=status.HTTP_404_NOT_FOUND,
                )
            if not puede_editar(request.user, doc, request.membership):
                return None, None, Response(
                    {'detail': 'Puede ver este archivo, pero no cambiar con quién está compartido.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
            return None, doc, None

        return None, None, Response(
            {'detail': 'Falta decir de qué carpeta o documento.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def get(self, request):
        carpeta, doc, error = self._item(request)
        if error:
            return error
        from .permisos import nivel_del_workspace, serializar_permisos
        from apps.workspaces.models import Membership

        # A quién se le puede dar permiso: la gente del Workspace que todavía no lo tiene.
        ya = {p['user'] for p in serializar_permisos(carpeta=carpeta, document=doc)}
        del_workspace = Membership.objects.filter(
            organization=request.membership.organization,
        ).exclude(user_id__in=ya).select_related('user')

        return Response({
            'restringido': carpeta.restringida if carpeta else doc.restringido,
            'nombre': carpeta.name if carpeta else doc.title,
            'workspace_nivel': nivel_del_workspace(carpeta=carpeta, document=doc),
            'workspace_nombre': request.membership.organization.name,
            'miembros': Membership.objects.filter(
                organization=request.membership.organization,
            ).count(),
            'compartido_con': serializar_permisos(carpeta=carpeta, document=doc),
            'disponibles': [
                {
                    'id': m.user_id,
                    'name': m.user.get_full_name() or m.user.email,
                    'email': m.user.email,
                }
                for m in del_workspace
            ],
        })

    def post(self, request):
        carpeta, doc, error = self._item(request)
        if error:
            return error

        from .models import NIVEL_EDICION, NIVELES, Permiso

        if 'restringido' in request.data:
            valor = bool(request.data.get('restringido'))
            if carpeta:
                carpeta.restringida = valor
                carpeta.save(update_fields=['restringida'])
            else:
                doc.restringido = valor
                doc.save(update_fields=['restringido'])

            # Quien restringe NO se queda afuera de lo que acaba de restringir.
            #
            # Sin esto, un miembro común que restringía una carpeta que no había creado se
            # cerraba la puerta en el mismo clic: la respuesta salía 404 porque al releer
            # el ítem ya no lo veía, y la carpeta le desaparecía de la pantalla. Solo hace
            # falta cuando pasaría de verdad — al administrador y a quien lo creó ya les
            # alcanza su propia regla, y agregarles un permiso ensuciaría la lista.
            if valor:
                from .permisos import nivel_sobre_carpeta, nivel_sobre_documento

                nivel_ahora = (
                    nivel_sobre_carpeta(request.user, carpeta, request.membership) if carpeta
                    else nivel_sobre_documento(request.user, doc, request.membership)
                )
                if nivel_ahora != NIVEL_EDICION:
                    Permiso.objects.update_or_create(
                        carpeta=carpeta, document=doc, user=request.user,
                        defaults={'nivel': NIVEL_EDICION, 'otorgado_por': request.user},
                    )

        # El de todo el Workspace: `null` explícito lo quita, un nivel lo pone.
        if 'workspace_nivel' in request.data:
            valor = request.data.get('workspace_nivel')
            if valor in (None, '', False):
                Permiso.objects.filter(
                    carpeta=carpeta, document=doc, user__isnull=True,
                ).delete()
            elif valor not in dict(NIVELES):
                return Response(
                    {'detail': f'Nivel desconocido: {valor}.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            else:
                Permiso.objects.update_or_create(
                    carpeta=carpeta, document=doc, user=None,
                    defaults={'nivel': valor, 'otorgado_por': request.user},
                )

        ids = request.data.get('ids')
        if ids:
            nivel = request.data.get('nivel') or 'lectura'
            if nivel not in dict(NIVELES):
                return Response(
                    {'detail': f'Nivel desconocido: {nivel}.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            from apps.workspaces.models import Membership

            # Solo gente del Workspace: compartir un archivo con alguien de afuera es
            # invitarlo a la empresa, y eso se hace desde Admin > Personas.
            del_workspace = Membership.objects.filter(
                organization=request.membership.organization, user_id__in=_ids(ids),
            ).select_related('user')
            if not del_workspace.exists():
                return Response(
                    {'detail': 'Esas personas no son parte de este Workspace.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            for m in del_workspace:
                Permiso.objects.update_or_create(
                    carpeta=carpeta, document=doc, user=m.user,
                    defaults={'nivel': nivel, 'otorgado_por': request.user},
                )

        return self.get(request)

    def delete(self, request):
        carpeta, doc, error = self._item(request)
        if error:
            return error
        from .models import Permiso

        if request.data.get('todo_el_workspace'):
            Permiso.objects.filter(carpeta=carpeta, document=doc, user__isnull=True).delete()
        else:
            Permiso.objects.filter(
                carpeta=carpeta, document=doc, user_id__in=_ids(request.data.get('ids')),
            ).delete()
        return self.get(request)


def _ids(valor):
    if not isinstance(valor, (list, tuple)):
        return []
    limpios = []
    for v in valor:
        try:
            limpios.append(int(v))
        except (TypeError, ValueError):
            continue
    return limpios

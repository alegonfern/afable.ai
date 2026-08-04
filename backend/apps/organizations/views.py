from urllib.parse import urlencode
import requests
import logging

from django.conf import settings
from django.core import signing
from django.shortcuts import get_object_or_404, redirect
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

from .models import (
    Organization, IntegrationScan, ActiveIntegration, SystemConnection,
    OrganizationContext, CompanyDocument, ContextCubicle,
)
from .serializers import (
    OrganizationSerializer, OdooIntegrationSerializer, IntegrationScanSerializer,
    ActiveIntegrationSerializer, SystemConnectionSerializer,
    OrganizationContextSerializer, CompanyDocumentSerializer, ContextCubicleSerializer,
)
from services.odoo_client import OdooClient, OdooConnectionError

MAX_COMPANY_DOCUMENTS = 20
MAX_DOCUMENT_SIZE_MB = 10


logger = logging.getLogger(__name__)


class RequestIntegrationView(APIView):
    """El cliente pide una integración que no está en el catálogo — le llega un
    correo al equipo de Afable con el detalle para registrarlo."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        description = (request.data.get('description') or '').strip()
        if not description:
            return Response({'detail': 'Falta describir qué querés integrar.'},
                             status=status.HTTP_400_BAD_REQUEST)
        from django.conf import settings
        from django.core.mail import send_mail
        send_mail(
            subject=f'[Afable] Solicitud de integración — {request.user.email}',
            message=(
                f'Usuario: {request.user.email}\n\n'
                f'Pidió integrar:\n{description}'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.AFABLE_TEAM_EMAIL],
            fail_silently=False,
        )
        return Response({'ok': True}, status=status.HTTP_201_CREATED)


class OrganizationListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        orgs = Organization.objects.filter(owner=request.user)
        serializer = OrganizationSerializer(orgs, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request):
        serializer = OrganizationSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class OrganizationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_org(self, pk, user):
        return get_object_or_404(Organization, pk=pk, owner=user)

    def get(self, request, pk):
        org = self._get_org(pk, request.user)
        return Response(OrganizationSerializer(org, context={'request': request}).data)

    def put(self, request, pk):
        org = self._get_org(pk, request.user)
        serializer = OrganizationSerializer(org, data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        from services.context_compiler import write_context_markdown_file
        write_context_markdown_file(org)
        return Response(serializer.data)

    def patch(self, request, pk):
        org = self._get_org(pk, request.user)
        serializer = OrganizationSerializer(
            org, data=request.data, partial=True, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        from services.context_compiler import write_context_markdown_file
        write_context_markdown_file(org)
        return Response(serializer.data)

    def delete(self, request, pk):
        org = self._get_org(pk, request.user)
        org.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class IntegrationScanListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_ids = Organization.objects.filter(owner=request.user).values_list('id', flat=True)
        scans = IntegrationScan.objects.filter(organization_id__in=org_ids)
        return Response(IntegrationScanSerializer(scans, many=True).data)


class OdooIntegrationView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        org = get_object_or_404(Organization, pk=pk, owner=request.user)
        serializer = OdooIntegrationSerializer(org, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(OrganizationSerializer(org, context={'request': request}).data)


class OdooTestConnectionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        org = get_object_or_404(Organization, pk=pk, owner=request.user)
        if not all([org.odoo_url, org.odoo_db, org.odoo_username, org.odoo_api_key]):
            return Response(
                {'detail': 'Faltan credenciales de Odoo.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            client = OdooClient(org.odoo_url, org.odoo_db, org.odoo_username, org.odoo_api_key)
            uid = client.authenticate()
            org.odoo_connected = True
            org.save(update_fields=['odoo_connected'])
            return Response({'detail': 'Conexión exitosa.', 'uid': uid})
        except OdooConnectionError as e:
            org.odoo_connected = False
            org.save(update_fields=['odoo_connected'])
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ActiveIntegrationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        integrations = ActiveIntegration.objects.filter(user=request.user, is_active=True)
        return Response(ActiveIntegrationSerializer(integrations, many=True).data)


class ConnectIntegrationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        integration_type = request.data.get('integration_type')
        if not integration_type:
            return Response({'detail': 'integration_type requerido'}, status=status.HTTP_400_BAD_REQUEST)

        obj, _ = ActiveIntegration.objects.get_or_create(
            user=request.user,
            integration_type=integration_type,
            defaults={'is_active': True},
        )
        obj.is_active = True
        obj.save(update_fields=['is_active'])
        return Response(ActiveIntegrationSerializer(obj).data, status=status.HTTP_200_OK)


class DisconnectIntegrationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        integration_type = request.data.get('integration_type')
        if not integration_type:
            return Response({'detail': 'integration_type requerido'}, status=status.HTTP_400_BAD_REQUEST)

        ActiveIntegration.objects.filter(
            user=request.user, integration_type=integration_type
        ).update(is_active=False)
        return Response({'detail': 'Integración desconectada'})


# ── SystemConnection ───────────────────────────────────────────────────────────

class SystemConnectionListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_ids = Organization.objects.filter(owner=request.user).values_list('id', flat=True)
        connections = SystemConnection.objects.filter(organization_id__in=org_ids)
        return Response(SystemConnectionSerializer(connections, many=True).data)

    def post(self, request):
        org_id = request.data.get('organization')
        org = get_object_or_404(Organization, pk=org_id, owner=request.user)
        config = request.data.get('config', {})
        name = request.data.get('name', '')
        connector_type = request.data.get('connector_type', '')
        if not all([name, connector_type]):
            return Response({'detail': 'name y connector_type son requeridos.'}, status=status.HTTP_400_BAD_REQUEST)
        category = request.data.get('category', 'otro')
        if category not in dict(SystemConnection.CATEGORIES):
            category = 'otro'
        conn = SystemConnection(organization=org, name=name, connector_type=connector_type, category=category)
        conn.config = config
        conn.save()
        return Response(SystemConnectionSerializer(conn).data, status=status.HTTP_201_CREATED)


_DRIVE_SCOPE = 'https://www.googleapis.com/auth/drive.file'


def _drive_redirect_uri():
    return f'{settings.BACKEND_URL}/api/v1/organizations/connections/google-drive/callback/'


class GoogleDriveConnectStartView(APIView):
    """Paso 1: arma la URL de consentimiento de Google para el scope drive.file
    (el usuario elige la carpeta después, con el Picker — ver GoogleDriveFolderView).
    access_type=offline + prompt=consent para asegurar que Google entregue refresh_token."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org = Organization.objects.filter(owner=request.user).exclude(name='Personal').first()
        if not org:
            return Response({'detail': 'Primero crea tu empresa.'}, status=status.HTTP_400_BAD_REQUEST)
        state = signing.dumps({'org_id': org.id, 'user_id': request.user.id})
        params = {
            'client_id': settings.GOOGLE_CLIENT_ID,
            'redirect_uri': _drive_redirect_uri(),
            'response_type': 'code',
            'scope': _DRIVE_SCOPE,
            'access_type': 'offline',
            'prompt': 'consent',
            'state': state,
        }
        return Response({'auth_url': f'https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}'})


class GoogleDriveConnectCallbackView(APIView):
    """Paso 2: Google redirige acá con el code. Guarda el refresh_token cifrado en
    un SystemConnection (sin carpeta todavía) y manda al frontend a elegir la carpeta."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        code = request.GET.get('code')
        state = request.GET.get('state')
        if not code or not state:
            return redirect(f'{settings.FRONTEND_URL}/app/contexto?drive_error=denied')

        try:
            data = signing.loads(state, max_age=600)
        except signing.BadSignature:
            return redirect(f'{settings.FRONTEND_URL}/app/contexto?drive_error=invalid_state')

        org = get_object_or_404(Organization, pk=data['org_id'], owner_id=data['user_id'])

        token_resp = requests.post('https://oauth2.googleapis.com/token', data={
            'code': code,
            'client_id': settings.GOOGLE_CLIENT_ID,
            'client_secret': settings.GOOGLE_CLIENT_SECRET,
            'redirect_uri': _drive_redirect_uri(),
            'grant_type': 'authorization_code',
        })
        if token_resp.status_code != 200:
            return redirect(f'{settings.FRONTEND_URL}/app/contexto?drive_error=token')
        tokens = token_resp.json()
        refresh_token = tokens.get('refresh_token')
        if not refresh_token:
            # Pasa si el usuario ya había autorizado antes sin 'prompt=consent' efectivo.
            return redirect(f'{settings.FRONTEND_URL}/app/contexto?drive_error=no_refresh_token')

        conn = SystemConnection.objects.create(
            organization=org, name='Google Drive', connector_type='google_drive',
            category='otro', is_active=False,  # se activa al elegir la carpeta (ver GoogleDriveFolderView)
        )
        conn.config = {'refresh_token': refresh_token}
        conn.save()

        return redirect(f'{settings.FRONTEND_URL}/app/contexto?drive_connection_id={conn.id}')


class GoogleDriveAccessTokenView(APIView):
    """El frontend la llama para obtener un access_token de corta duración con el
    que abrir el Google Picker (elegir la carpeta) sin exponer el refresh_token."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        org_ids = Organization.objects.filter(owner=request.user).values_list('id', flat=True)
        conn = get_object_or_404(SystemConnection, pk=pk, organization_id__in=org_ids, connector_type='google_drive')
        refresh_token = conn.config.get('refresh_token')
        if not refresh_token:
            return Response({'detail': 'Esta conexión no tiene refresh_token.'}, status=status.HTTP_400_BAD_REQUEST)

        resp = requests.post('https://oauth2.googleapis.com/token', data={
            'client_id': settings.GOOGLE_CLIENT_ID,
            'client_secret': settings.GOOGLE_CLIENT_SECRET,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token',
        })
        if resp.status_code != 200:
            return Response({'detail': 'No se pudo renovar el acceso a Google Drive.'}, status=status.HTTP_400_BAD_REQUEST)
        # `app_id` es el numero del proyecto de Google Cloud (el prefijo del
        # client_id). El Picker lo necesita en setAppId: sin el, los archivos que el
        # usuario elige NO quedan autorizados para esta app y la API responde 404
        # aunque el usuario los haya elegido. Es la pieza que faltaba para que
        # `drive.file` sirva de algo.
        return Response({
            'access_token': resp.json()['access_token'],
            'app_id': (settings.GOOGLE_CLIENT_ID or '').split('-')[0],
        })


class GoogleDriveFilesView(APIView):
    """Guarda los archivos elegidos en el Picker y los sincroniza en el acto.

    Es la via que funciona con el scope `drive.file`: Google da permiso sobre cada
    archivo que el usuario elige, no sobre el contenido de una carpeta. Elegir una
    carpeta (GoogleDriveFolderView) necesita `drive.readonly`, que es scope
    restringido y exige verificacion de Google.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        org_ids = Organization.objects.filter(owner=request.user).values_list('id', flat=True)
        conn = get_object_or_404(
            SystemConnection, pk=pk, organization_id__in=org_ids, connector_type='google_drive',
        )
        archivos = request.data.get('files') or []
        if not archivos:
            return Response({'detail': 'No se eligió ningún archivo.'}, status=status.HTTP_400_BAD_REQUEST)

        limpios = [
            {'id': a.get('id'), 'name': a.get('name', '')}
            for a in archivos if a.get('id')
        ]
        cfg = conn.config
        cfg['file_ids'] = limpios
        cfg.pop('folder_id', None)      # se elige una cosa o la otra, no las dos
        cfg.pop('folder_name', None)
        conn.config = cfg
        conn.name = (
            f'Google Drive — {limpios[0]["name"]}' if len(limpios) == 1
            else f'Google Drive — {len(limpios)} archivos'
        )
        conn.is_active = True
        conn.save()

        from apps.organizations.models import CompanyDocument
        from services.drive_sync import _sync_connection
        sincronizado, error = True, None
        try:
            _sync_connection(conn)
            conn.refresh_from_db()
        except Exception as e:
            logger.exception('Fallo el sync de archivos de la conexion Drive #%s', conn.id)
            sincronizado, error = False, str(e)

        datos = SystemConnectionSerializer(conn).data
        datos['sincronizado'] = sincronizado
        datos['error_sync'] = error
        datos['documentos'] = CompanyDocument.objects.filter(
            organization=conn.organization, source='drive_sync',
        ).count()
        return Response(datos)


class GoogleDriveFolderView(APIView):
    """Paso 3: el frontend manda la carpeta elegida en el Picker. Recién acá la
    conexión queda activa (antes de esto no hay nada que sincronizar)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        org_ids = Organization.objects.filter(owner=request.user).values_list('id', flat=True)
        conn = get_object_or_404(SystemConnection, pk=pk, organization_id__in=org_ids, connector_type='google_drive')
        folder_id = (request.data.get('folder_id') or '').strip()
        folder_name = (request.data.get('folder_name') or '').strip()
        if not folder_id:
            return Response({'detail': 'folder_id es requerido.'}, status=status.HTTP_400_BAD_REQUEST)

        cfg = conn.config
        cfg['folder_id'] = folder_id
        cfg['folder_name'] = folder_name
        conn.config = cfg
        conn.name = f'Google Drive — {folder_name}' if folder_name else 'Google Drive'
        conn.is_active = True
        conn.save()

        # Sincroniza AL TIRO, no en la proxima pasada de un corredor. Antes esto
        # quedaba "esperando primer sync (cada 15 min)" para siempre, porque el
        # servicio que hacia esa pasada esta apagado desde la reconstruccion v1.
        from apps.organizations.models import CompanyDocument
        from services.drive_sync import _sync_connection
        sincronizado, error = True, None
        try:
            _sync_connection(conn)
            conn.refresh_from_db()
        except Exception as e:  # el enlace ya quedo guardado; el sync se puede reintentar
            logger.exception('Fallo el primer sync de la conexion Drive #%s', conn.id)
            sincronizado, error = False, str(e)

        datos = SystemConnectionSerializer(conn).data
        datos['sincronizado'] = sincronizado
        datos['error_sync'] = error
        datos['documentos'] = CompanyDocument.objects.filter(
            organization=conn.organization, source='drive_sync',
        ).count()
        return Response(datos)


class SystemConnectionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_conn(self, pk, user):
        org_ids = Organization.objects.filter(owner=user).values_list('id', flat=True)
        return get_object_or_404(SystemConnection, pk=pk, organization_id__in=org_ids)

    def get(self, request, pk):
        conn = self._get_conn(pk, request.user)
        return Response(SystemConnectionSerializer(conn).data)

    def patch(self, request, pk):
        conn = self._get_conn(pk, request.user)
        if 'name' in request.data:
            conn.name = request.data['name']
        if 'config' in request.data:
            # Merge, no reemplazo: el form de edición solo manda los campos que el
            # usuario tocó (los que dejó en blanco no viajan) — si reemplazáramos
            # el dict entero se borrarían credenciales que no se querían tocar.
            merged = conn.get_config()
            merged.update({k: v for k, v in request.data['config'].items() if v not in (None, '')})
            conn.config = merged
        if 'is_active' in request.data:
            conn.is_active = request.data['is_active']
        conn.save()
        return Response(SystemConnectionSerializer(conn).data)

    def delete(self, request, pk):
        conn = self._get_conn(pk, request.user)
        conn.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SystemConnectionTestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        org_ids = Organization.objects.filter(owner=request.user).values_list('id', flat=True)
        conn = get_object_or_404(SystemConnection, pk=pk, organization_id__in=org_ids)
        from services.connector_registry import test_connection
        result = test_connection(conn)
        if result.get('success'):
            conn.is_active = True
            conn.save(update_fields=['is_active'])
        return Response(result)


class SystemConnectionSyncView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        org_ids = Organization.objects.filter(owner=request.user).values_list('id', flat=True)
        conn = get_object_or_404(SystemConnection, pk=pk, organization_id__in=org_ids)

        # Drive no tiene "esquema": sincronizar significa bajar los archivos de la
        # carpeta elegida. Antes esta vista llamaba igual a sync_schema y no traia nada.
        if conn.connector_type == 'google_drive':
            from services.drive_sync import _sync_connection
            _sync_connection(conn)
            conn.refresh_from_db()
            from apps.organizations.models import CompanyDocument
            return Response({
                'documentos': CompanyDocument.objects.filter(
                    organization=conn.organization, source='drive_sync',
                ).count(),
                'last_synced_at': conn.last_synced_at,
            })

        from services.connector_registry import sync_schema
        schema = sync_schema(conn)
        return Response({'schema': schema, 'last_synced_at': conn.last_synced_at})


class OrganizationDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from services.connector_registry import get_dashboard_kpis
        org = Organization.objects.filter(owner=request.user).exclude(name='Personal').first()
        if not org:
            return Response({'connections': [], 'org_name': None})
        data = get_dashboard_kpis(org)
        return Response({'connections': data, 'org_name': org.name})


class BusinessModelView(APIView):
    """Grafo del 'modelo vivo' (entidades + relaciones) desde el esquema sincronizado."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from services.connector_registry import get_business_model
        org = Organization.objects.filter(owner=request.user).exclude(name='Personal').first()
        if not org:
            return Response({'sources': [], 'entities': [], 'edges': [], 'synced': False, 'org_name': None})
        data = get_business_model(org)
        data['org_name'] = org.name
        return Response(data)


def _can_edit_org(org, user) -> bool:
    """La capa de empresa la edita el dueño de la org o un administrador.
    Los usuarios invitados la ven en modo lectura.

    `User.org_admin` ya no existe: el rol vive en `Membership` (Etapa 1). Mientras
    esta pantalla no se rehaga contra un Workspace concreto, se usa el puente
    `is_admin_anywhere`."""
    from apps.workspaces.permissions import is_admin_anywhere
    return org.owner_id == user.id or is_admin_anywhere(user)


class OrganizationContextView(APIView):
    """Formulario de contexto de empresa: se inyecta siempre en el system prompt de los agentes."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        org = get_object_or_404(Organization, pk=pk)
        ctx, _ = OrganizationContext.objects.get_or_create(organization=org)
        data = OrganizationContextSerializer(ctx).data
        data['can_edit'] = _can_edit_org(org, request.user)
        return Response(data)

    def patch(self, request, pk):
        org = get_object_or_404(Organization, pk=pk)
        if not _can_edit_org(org, request.user):
            return Response({'detail': 'Solo el administrador puede editar el contexto de la empresa.'},
                            status=status.HTTP_403_FORBIDDEN)
        ctx, _ = OrganizationContext.objects.get_or_create(organization=org)
        serializer = OrganizationContextSerializer(ctx, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        data = dict(serializer.data)
        data['can_edit'] = True
        return Response(data)


MAX_USER_STORAGE_MB = 100


def _user_storage_used_bytes(user) -> int:
    total = 0
    for doc in CompanyDocument.objects.filter(uploaded_by=user).only('file'):
        try:
            total += doc.file.size
        except (ValueError, OSError):
            pass
    return total


class CompanyDocumentListCreateView(APIView):
    """Repositorio de archivos de contexto de la empresa.

    ?scope=mine    -> solo los que subió el usuario actual (privados incluidos)
    ?scope=company -> los que cualquier miembro marcó públicos
    (sin scope)    -> comportamiento histórico: todos los de la organización
                      (lo sigue usando Mi Contexto tal cual estaba).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        org = get_object_or_404(Organization, pk=pk)
        docs = CompanyDocument.objects.filter(organization=org)
        scope = request.query_params.get('scope')
        if scope == 'mine':
            docs = docs.filter(uploaded_by=request.user)
        elif scope == 'company':
            docs = docs.filter(is_public=True)
        return Response(CompanyDocumentSerializer(docs, many=True, context={'request': request}).data)

    def post(self, request, pk):
        org = get_object_or_404(Organization, pk=pk)
        if not _can_edit_org(org, request.user):
            return Response({'detail': 'Solo el administrador puede subir archivos de la empresa.'},
                            status=status.HTTP_403_FORBIDDEN)
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'detail': 'Falta el archivo.'}, status=status.HTTP_400_BAD_REQUEST)
        if file_obj.size > MAX_DOCUMENT_SIZE_MB * 1024 * 1024:
            return Response({'detail': f'El archivo supera el máximo de {MAX_DOCUMENT_SIZE_MB}MB.'},
                             status=status.HTTP_400_BAD_REQUEST)
        if CompanyDocument.objects.filter(organization=org).count() >= MAX_COMPANY_DOCUMENTS:
            return Response({'detail': f'Llegaste al máximo de {MAX_COMPANY_DOCUMENTS} archivos.'},
                             status=status.HTTP_400_BAD_REQUEST)
        used = _user_storage_used_bytes(request.user)
        if used + file_obj.size > MAX_USER_STORAGE_MB * 1024 * 1024:
            return Response(
                {'detail': f'Llegaste a tu cuota de {MAX_USER_STORAGE_MB}MB de almacenamiento.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        title = request.data.get('title') or file_obj.name
        category = request.data.get('category') or 'otro'
        content_type = file_obj.content_type or ''
        is_public = str(request.data.get('is_public', '')).lower() in ('true', '1', 'on')

        doc = CompanyDocument.objects.create(
            organization=org, uploaded_by=request.user, title=title,
            category=category, file=file_obj, content_type=content_type, is_public=is_public,
        )

        from services.document_processing import process_document
        result = process_document(doc.file, content_type)
        doc.extracted_text = result['extracted_text']
        doc.summary = result['summary']
        doc.processing_error = result['error']
        doc.save(update_fields=['extracted_text', 'summary', 'processing_error'])

        # Busqueda semantica: se trocea y vectoriza recien subido. Si el proveedor
        # de embeddings no esta, el documento queda sin indexar y la subida termina
        # bien igual — se recupera con `manage.py indexar_conocimiento`.
        from services.indexing import indexar_documento_sin_ruido
        indexar_documento_sin_ruido(doc)

        return Response(CompanyDocumentSerializer(doc, context={'request': request}).data, status=status.HTTP_201_CREATED)


class CompanyDocumentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk, doc_id):
        doc = get_object_or_404(CompanyDocument, pk=doc_id, organization_id=pk)
        if not _can_edit_org(doc.organization, request.user):
            return Response({'detail': 'Solo el administrador puede eliminar archivos de la empresa.'},
                            status=status.HTTP_403_FORBIDDEN)
        doc.file.delete(save=False)
        doc.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ContextCubicleListCreateView(APIView):
    """Cubículos de contexto: bloques libres que se compilan en contexto.md."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        org = get_object_or_404(Organization, pk=pk)
        cubicles = ContextCubicle.objects.filter(organization=org)
        return Response(ContextCubicleSerializer(cubicles, many=True).data)

    def post(self, request, pk):
        org = get_object_or_404(Organization, pk=pk)
        if not _can_edit_org(org, request.user):
            return Response({'detail': 'Solo el administrador puede editar el contexto de la empresa.'},
                            status=status.HTTP_403_FORBIDDEN)
        serializer = ContextCubicleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(organization=org)
        from services.context_compiler import write_context_markdown_file
        write_context_markdown_file(org)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ContextCubicleDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk, cubicle_id):
        org = get_object_or_404(Organization, pk=pk)
        if not _can_edit_org(org, request.user):
            return Response({'detail': 'Solo el administrador puede editar el contexto de la empresa.'},
                            status=status.HTTP_403_FORBIDDEN)
        cubicle = get_object_or_404(ContextCubicle, pk=cubicle_id, organization=org)
        serializer = ContextCubicleSerializer(cubicle, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        from services.context_compiler import write_context_markdown_file
        write_context_markdown_file(org)
        return Response(serializer.data)

    def delete(self, request, pk, cubicle_id):
        org = get_object_or_404(Organization, pk=pk)
        if not _can_edit_org(org, request.user):
            return Response({'detail': 'Solo el administrador puede editar el contexto de la empresa.'},
                            status=status.HTTP_403_FORBIDDEN)
        cubicle = get_object_or_404(ContextCubicle, pk=cubicle_id, organization=org)
        cubicle.delete()
        from services.context_compiler import write_context_markdown_file
        write_context_markdown_file(org)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ContextMarkdownView(APIView):
    """Sirve (y regenera) el archivo contexto.md compilado de la organización."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        org = get_object_or_404(Organization, pk=pk)
        from services.context_compiler import compile_context_markdown, write_context_markdown_file
        write_context_markdown_file(org)
        return Response({'markdown': compile_context_markdown(org)})

"""
Sincronización de una carpeta de Google Drive hacia CompanyDocument (Contexto).

Se llama desde run_automations._tick() (mismo corredor que ya vigila Automations/
Routines) — cada conexión Drive solo sincroniza de verdad si pasaron
SYNC_INTERVAL_MINUTES desde la última vez, así que no hace falta un proceso aparte.

Archivos nativos de Google (Doc/Sheet/Slide) se exportan a texto/CSV/PDF antes de
pasar por el mismo pipeline de extracción que usa la subida manual
(services/document_processing.py). Si un archivo desaparece de la carpeta, se
borra el CompanyDocument correspondiente.
"""
import logging
import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

logger = logging.getLogger(__name__)

SYNC_INTERVAL_MINUTES = 15
_MAX_FILE_MB = 20

# Google Docs/Sheets/Slides no tienen binario propio: hay que pedirle a Drive
# que los exporte a un formato con el que sepa lidiar process_document().
_GOOGLE_DOC_EXPORTS = {
    'application/vnd.google-apps.document': ('text/plain', '.txt'),
    'application/vnd.google-apps.spreadsheet': ('text/csv', '.csv'),
    'application/vnd.google-apps.presentation': ('application/pdf', '.pdf'),
}


class _BytesWrapper:
    """process_document espera un file-like con .seek/.read, como un FileField."""

    def __init__(self, data: bytes):
        self._data = data

    def seek(self, pos):
        pass

    def read(self):
        return self._data


def _refresh_access_token(refresh_token: str):
    resp = requests.post('https://oauth2.googleapis.com/token', data={
        'client_id': settings.GOOGLE_CLIENT_ID,
        'client_secret': settings.GOOGLE_CLIENT_SECRET,
        'refresh_token': refresh_token,
        'grant_type': 'refresh_token',
    })
    if resp.status_code != 200:
        return None
    return resp.json()['access_token']


def sync_due_connections():
    """Recorre las conexiones Drive activas con carpeta elegida y sincroniza
    las que ya cumplieron su intervalo. Pensada para llamarse seguido (cada
    CHECK_SECONDS del corredor) — es barata cuando no hay nada que hacer."""
    from apps.organizations.models import SystemConnection

    now = timezone.now()
    for conn in SystemConnection.objects.filter(connector_type='google_drive', is_active=True):
        if not conn.config.get('folder_id') and not conn.config.get('file_ids'):
            continue
        if conn.last_synced_at and (now - conn.last_synced_at).total_seconds() < SYNC_INTERVAL_MINUTES * 60:
            continue
        try:
            _sync_connection(conn)
        except Exception:
            logger.exception('Fallo sincronizando Drive connection #%s', conn.id)


def _list_folder_files(folder_id: str, headers: dict) -> list:
    files = []
    page_token = None
    while True:
        params = {
            'q': f"'{folder_id}' in parents and trashed = false",
            'fields': 'nextPageToken, files(id, name, mimeType, modifiedTime, size)',
            'pageSize': 100,
        }
        if page_token:
            params['pageToken'] = page_token
        resp = requests.get('https://www.googleapis.com/drive/v3/files', headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
        files.extend(data.get('files', []))
        page_token = data.get('nextPageToken')
        if not page_token:
            break
    return files


def _get_files_by_id(file_ids: list, headers: dict) -> list:
    """Metadatos de archivos elegidos uno por uno en el Picker.

    Con el scope `drive.file` esta es la unica via que funciona: Google concede
    permiso sobre cada archivo que el usuario elige, no sobre el contenido de una
    carpeta. Un archivo que ya no exista o al que perdimos acceso se salta.
    """
    files = []
    for fid in file_ids:
        resp = requests.get(
            f'https://www.googleapis.com/drive/v3/files/{fid}',
            headers=headers,
            params={'fields': 'id, name, mimeType, modifiedTime, size'},
        )
        if resp.status_code == 200:
            files.append(resp.json())
        else:
            logger.warning('Drive no entrega el archivo %s (%s)', fid, resp.status_code)
    return files


def _sync_connection(conn):
    from apps.organizations.models import CompanyDocument

    access_token = _refresh_access_token(conn.config.get('refresh_token', ''))
    if not access_token:
        logger.warning('No se pudo renovar el access_token de la conexión Drive #%s', conn.id)
        return
    headers = {'Authorization': f'Bearer {access_token}'}

    elegidos = conn.config.get('file_ids') or []
    if elegidos:
        files = _get_files_by_id([f['id'] if isinstance(f, dict) else f for f in elegidos], headers)
    else:
        files = _list_folder_files(conn.config['folder_id'], headers)
    seen_ids = {f['id'] for f in files}
    known = (conn.schema_cache or {}).get('files', {})  # {file_id: modifiedTime}
    org = conn.organization

    # Se borraron o movieron fuera de la carpeta desde el último sync.
    stale_ids = set(known) - seen_ids
    if stale_ids:
        CompanyDocument.objects.filter(organization=org, source='drive_sync', external_id__in=stale_ids).delete()

    new_known = {}
    for f in files:
        new_known[f['id']] = f['modifiedTime']
        if known.get(f['id']) == f['modifiedTime']:
            continue  # sin cambios desde el último sync

        if int(f.get('size') or 0) > _MAX_FILE_MB * 1024 * 1024:
            continue

        mime = f['mimeType']
        if mime in _GOOGLE_DOC_EXPORTS:
            export_mime, ext = _GOOGLE_DOC_EXPORTS[mime]
            dl = requests.get(f"https://www.googleapis.com/drive/v3/files/{f['id']}/export",
                              headers=headers, params={'mimeType': export_mime})
            content_type, filename = export_mime, f['name'] + ext
        elif mime.startswith('application/vnd.google-apps.'):
            continue  # Forms/Sites/Apps Script: sin exportación de texto razonable
        else:
            dl = requests.get(f"https://www.googleapis.com/drive/v3/files/{f['id']}",
                              headers=headers, params={'alt': 'media'})
            content_type, filename = mime, f['name']

        if dl.status_code != 200:
            continue

        from services.document_processing import process_document
        result = process_document(_BytesWrapper(dl.content), content_type)

        # El texto que habia antes, para saber si hay que reindexar. Abrir o
        # renombrar un documento de Google le mueve el `modifiedTime` sin cambiarle
        # una letra, y vectorizar de nuevo un archivo identico es puro gasto de CPU
        # en cada vuelta del corredor.
        texto_anterior = CompanyDocument.objects.filter(
            organization=org, external_id=f['id'],
        ).values_list('extracted_text', flat=True).first()

        doc, _ = CompanyDocument.objects.update_or_create(
            organization=org, external_id=f['id'],
            defaults={
                'title': filename, 'category': 'otro', 'is_public': True,
                'content_type': content_type, 'source': 'drive_sync',
                'extracted_text': result['extracted_text'], 'summary': result['summary'],
                'processing_error': result['error'],
            },
        )
        doc.file.save(filename, ContentFile(dl.content), save=True)

        if (result['extracted_text'] or '') != (texto_anterior or ''):
            from services.indexing import indexar_documento_sin_ruido
            indexar_documento_sin_ruido(doc)

    conn.schema_cache = {'files': new_known}
    conn.last_synced_at = timezone.now()
    conn.save(update_fields=['schema_cache', 'last_synced_at'])

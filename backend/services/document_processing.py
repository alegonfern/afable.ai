"""
Extracción de texto + resumen corto para CompanyDocument, ejecutado UNA VEZ al
subir el archivo (no en cada request de chat). El resumen es lo que se inyecta
siempre en el system prompt; el texto completo solo se entrega si el agente
llama a la tool `read_company_document`.
"""
import io
import logging

logger = logging.getLogger(__name__)

_MAX_EXTRACTED_CHARS = 20000  # tope defensivo: evita que un PDF gigante infle el prompt

_IMAGE_TYPES = {'image/png', 'image/jpeg', 'image/jpg', 'image/webp', 'image/gif'}
_PDF_TYPES = {'application/pdf'}
_DOCX_TYPES = {'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}
_TEXT_TYPES = {'text/plain', 'text/csv', 'text/markdown'}
_XLSX_TYPES = {
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-excel',
}


def _extract_xlsx(data: bytes) -> str:
    import pandas as pd
    sheets = pd.read_excel(io.BytesIO(data), sheet_name=None)
    parts = []
    for name, df in sheets.items():
        parts.append(f"### Hoja: {name}\n{df.to_csv(index=False)}")
    return '\n\n'.join(parts)


def _extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    return '\n'.join(page.extract_text() or '' for page in reader.pages)


def _extract_docx(data: bytes) -> str:
    from docx import Document
    doc = Document(io.BytesIO(data))
    return '\n'.join(p.text for p in doc.paragraphs)


def _extract_text_plain(data: bytes) -> str:
    return data.decode('utf-8', errors='replace')


def process_document(file_field, content_type: str) -> dict:
    """Devuelve {'extracted_text', 'summary', 'error'}. Nunca lanza excepción:
    un archivo que no se puede procesar igual se guarda, solo sin texto/resumen."""
    file_field.seek(0)
    data = file_field.read()

    if content_type in _IMAGE_TYPES:
        return _process_image(data, content_type)

    try:
        if content_type in _PDF_TYPES:
            text = _extract_pdf(data)
        elif content_type in _DOCX_TYPES:
            text = _extract_docx(data)
        elif content_type in _XLSX_TYPES:
            text = _extract_xlsx(data)
        elif content_type in _TEXT_TYPES or content_type.startswith('text/'):
            text = _extract_text_plain(data)
        else:
            return {'extracted_text': '', 'summary': '',
                    'error': f'Tipo de archivo no soportado para extracción de texto: {content_type or "desconocido"}.'}
    except Exception:
        logger.exception('Fallo extrayendo texto de documento')
        return {'extracted_text': '', 'summary': '', 'error': 'No se pudo extraer el texto del archivo.'}

    text = text.strip()[:_MAX_EXTRACTED_CHARS]
    if not text:
        return {'extracted_text': '', 'summary': '', 'error': 'El archivo no tiene texto extraíble.'}

    summary = _summarize_text(text)
    return {'extracted_text': text, 'summary': summary, 'error': ''}


def _process_image(data: bytes, content_type: str) -> dict:
    """Para imágenes no hay 'texto' propio: se le pide a Claude una descripción
    (sirve de OCR + resumen a la vez) y se usa como extracted_text Y summary."""
    import base64
    from .agent_service import _get_anthropic_client

    try:
        b64 = base64.b64encode(data).decode('ascii')
        client = _get_anthropic_client()
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": content_type, "data": b64}},
                    {"type": "text", "text": (
                        "Describe el contenido de esta imagen en español, en un párrafo breve (máx 150 palabras). "
                        "Si contiene texto (tabla, lista de precios, documento escaneado), transcríbelo. "
                        "Esto se usará como contexto de negocio para un asistente de IA."
                    )},
                ],
            }],
        )
        text = "\n".join(b.text for b in response.content if getattr(b, 'type', None) == 'text').strip()
        if not text:
            return {'extracted_text': '', 'summary': '', 'error': 'No se pudo describir la imagen.'}
        return {'extracted_text': text, 'summary': text, 'error': ''}
    except Exception:
        logger.exception('Fallo describiendo imagen')
        return {'extracted_text': '', 'summary': '', 'error': 'No se pudo describir la imagen (revisa ANTHROPIC_API_KEY).'}


def _summarize_text(text: str) -> str:
    from .agent_service import _get_anthropic_client

    try:
        client = _get_anthropic_client()
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": (
                    "Resume el siguiente documento en español, en máximo 3 frases, enfocándote en qué información "
                    "de negocio contiene (para que un asistente de IA sepa cuándo consultarlo). "
                    "Documento:\n\n" + text[:8000]
                ),
            }],
        )
        return "\n".join(b.text for b in response.content if getattr(b, 'type', None) == 'text').strip()
    except Exception:
        logger.exception('Fallo generando resumen de documento')
        return text[:280] + ('…' if len(text) > 280 else '')

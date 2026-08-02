import json
import logging
import re
import time
import requests
import anthropic
from django.conf import settings

logger = logging.getLogger(__name__)

# Mensaje para el usuario cuando el modelo falla tras reintentos — sin URLs internas.
_MODEL_DOWN_MSG = ("El modelo de IA tuvo un problema temporal y no respondió. "
                   "Vuelve a intentarlo en unos segundos.")

from .odoo_client import OdooClient, OdooConnectionError
from .odoo_tools import ODOO_TOOLS, execute_tool

_anthropic_client = None


def _get_anthropic_client() -> anthropic.Anthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _anthropic_client


def _is_ollama(provider: str) -> bool:
    return provider in ('ollama', 'ollama_cloud')


def _ollama_config(model_override: str = None) -> tuple[str, str, dict]:
    """(base_url, model, headers) del target Ollama activo: local o cloud.

    En cloud, la API es la misma (/api/chat) pero apunta a ollama.com y manda
    la key como Bearer. La key se lee de settings (OLLAMA_API_KEY, vía .env).
    `model_override` (si viene del selector de la app) tiene prioridad sobre el default."""
    api_key = getattr(settings, 'OLLAMA_API_KEY', '')
    if getattr(settings, 'AI_PROVIDER', 'ollama') == 'ollama_cloud':
        base_url = getattr(settings, 'OLLAMA_CLOUD_BASE_URL', 'https://ollama.com')
        model = model_override or getattr(settings, 'OLLAMA_CLOUD_MODEL', 'gpt-oss:120b')
        headers = {'Authorization': f'Bearer {api_key}'} if api_key else {}
        return base_url, model, headers
    base_url = getattr(settings, 'OLLAMA_BASE_URL', 'http://localhost:11434')
    model = model_override or getattr(settings, 'OLLAMA_MODEL', 'qwen2.5:7b')
    # Un modelo cloud (sufijo -cloud) seleccionado desde la app requiere la key Bearer
    # aunque pase por el Ollama local como proxy.
    headers = {'Authorization': f'Bearer {api_key}'} if (api_key and model and model.endswith('-cloud')) else {}
    return base_url, model, headers


def _post_chat(base_url: str, payload: dict, headers: dict, timeout: int = 300, stream: bool = False):
    """POST a /api/chat con reintentos: Ollama cloud devuelve 500 esporádicos
    (visto 2 veces en producción local). 3 intentos con backoff 1s/3s; los
    errores de conexión se propagan de inmediato (los maneja cada caller)."""
    last = None
    for attempt in range(3):
        if attempt:
            time.sleep(attempt * 2 - 1)
        resp = requests.post(f"{base_url}/api/chat", json=payload, headers=headers,
                             timeout=timeout, stream=stream)
        if resp.status_code >= 500 or resp.status_code == 429:
            logger.warning("Ollama devolvió %s (intento %d/3)", resp.status_code, attempt + 1)
            last = resp
            continue
        resp.raise_for_status()
        return resp
    last.raise_for_status()


def resolve_model(model: str = None) -> tuple[str, str]:
    """Devuelve (provider, model_id) que realmente se va a usar, sin llamar a ninguna
    API — permite saber de antemano (y mostrarle al usuario) qué modelo respondió.
    Misma lógica de inferencia que usa el agente con datos en vivo (_provider_for_model),
    para que el chat directo y el chat con sistemas conectados queden consistentes."""
    provider = _provider_for_model(model) if model else getattr(settings, 'AI_PROVIDER', 'ollama')
    if provider == 'anthropic':
        return provider, model or 'claude-sonnet-4-6'
    if provider == 'deepseek':
        return provider, model or getattr(settings, 'DEEPSEEK_MODEL', 'deepseek-chat')
    _, resolved, _ = _ollama_config(model)
    return provider, resolved


def chunk_text(text: str, size: int = 28):
    """Trocea texto para simular streaming cuando el proveedor no soporta streaming real."""
    buf = ''
    for word in (text or '').split(' '):
        buf += word + ' '
        if len(buf) >= size:
            yield buf
            buf = ''
    if buf:
        yield buf


def chat_direct(history: list[dict], system_prompt: str = "", model: str = None) -> str:
    provider, resolved = resolve_model(model)
    if provider == 'anthropic':
        return _chat_anthropic_simple(history, system_prompt, resolved)
    if provider == 'deepseek':
        return _chat_deepseek_simple(history, system_prompt, resolved)
    return _chat_ollama(history, system_prompt, resolved)


def stream_direct(history: list[dict], system_prompt: str = "", model: str = None):
    """Generator que entrega el texto en trozos. Ollama transmite token a token; Anthropic
    y DeepSeek no soportan streaming en este endpoint, así que se pide la respuesta completa
    y se trocea igual (misma técnica que usa el modo con sistemas conectados) para mantener
    el efecto typing."""
    provider, resolved = resolve_model(model)
    if provider == 'anthropic':
        yield from chunk_text(_chat_anthropic_simple(history, system_prompt, resolved))
    elif provider == 'deepseek':
        yield from chunk_text(_chat_deepseek_simple(history, system_prompt, resolved))
    else:
        yield from _stream_ollama(history, system_prompt, resolved)


def _stream_ollama(history: list[dict], system_prompt: str, model: str):
    base_url, model, headers = _ollama_config(model)

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    for msg in history:
        if msg.get('role') in ('user', 'assistant') and msg.get('content'):
            messages.append({"role": msg['role'], "content": msg['content']})

    try:
        resp = _post_chat(base_url, {"model": model, "messages": messages, "stream": True},
                          headers, timeout=120, stream=True)
        for line in resp.iter_lines():
            if line:
                import json as _json
                data = _json.loads(line)
                chunk = data.get('message', {}).get('content', '')
                if chunk:
                    yield chunk
                if data.get('done'):
                    break
    except Exception:
        logger.exception("stream_direct falló")
        yield f"\n{_MODEL_DOWN_MSG}"


def run_agent(history: list[dict], organization) -> str:
    provider = getattr(settings, 'AI_PROVIDER', 'ollama')

    system_prompt = f"""Eres Afable, un agente de análisis empresarial para {organization.name}.
Responde siempre en el mismo idioma que usa el usuario.
Empresa: {organization.name}
Sector: {organization.sector or 'No especificado'}
"""

    if _is_ollama(provider):
        return _chat_ollama(history, system_prompt)

    odoo_client = OdooClient(
        url=organization.odoo_url,
        db=organization.odoo_db,
        username=organization.odoo_username,
        api_key=organization.odoo_api_key,
    )
    return _run_anthropic_agent(history, system_prompt, odoo_client)


# ── Ollama ────────────────────────────────────────────────────────────

def _chat_ollama(history: list[dict], system_prompt: str = "", model: str = None) -> str:
    base_url, model, headers = _ollama_config(model)

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    for msg in history:
        if msg.get('role') in ('user', 'assistant') and msg.get('content'):
            messages.append({"role": msg['role'], "content": msg['content']})

    try:
        resp = _post_chat(base_url, {"model": model, "messages": messages, "stream": False},
                          headers, timeout=120)
        return resp.json()['message']['content']
    except requests.exceptions.ConnectionError:
        return "No se pudo conectar con el modelo. Si usas Ollama local, asegúrate de que esté corriendo; si usas Ollama Cloud, revisa OLLAMA_API_KEY y la conexión."
    except Exception:
        logger.exception("_chat_ollama falló")
        return _MODEL_DOWN_MSG


# ── Anthropic ─────────────────────────────────────────────────────────

def _chat_anthropic_simple(history: list[dict], system_prompt: str = "", model: str = None) -> str:
    messages = _build_api_messages(history)
    response = _get_anthropic_client().messages.create(
        model=model or "claude-sonnet-4-6",
        max_tokens=4096,
        system=system_prompt,
        messages=messages,
    )
    return _extract_text(response)


def _chat_deepseek_simple(history: list[dict], system_prompt: str = "", model: str = None) -> str:
    model = model or getattr(settings, 'DEEPSEEK_MODEL', 'deepseek-chat')
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.extend(_build_api_messages(history))
    headers = {
        "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        resp = requests.post(
            "https://api.deepseek.com/chat/completions",
            json={"model": model, "messages": messages, "stream": False},
            headers=headers, timeout=120,
        )
        resp.raise_for_status()
        return resp.json()['choices'][0]['message']['content']
    except Exception:
        logger.exception("_chat_deepseek_simple falló")
        return _MODEL_DOWN_MSG


def _run_anthropic_agent(history: list[dict], system_prompt: str, odoo_client: OdooClient) -> str:
    messages = _build_api_messages(history)

    for _ in range(10):
        response = _get_anthropic_client().messages.create(
            model="claude-opus-4-8",
            max_tokens=8096,
            thinking={"type": "adaptive"},
            system=system_prompt,
            tools=ODOO_TOOLS,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            return _extract_text(response)

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = _run_tool_calls(response.content, odoo_client)
            messages.append({"role": "user", "content": tool_results})
            continue

        return _extract_text(response) or "No pude procesar tu consulta."

    return "Superé el límite de iteraciones. Intenta con una pregunta más específica."


def _build_api_messages(history: list[dict]) -> list[dict]:
    return [
        {"role": msg['role'], "content": _strip_inline_images(msg['content'])}
        for msg in history
        if msg.get('role') in ('user', 'assistant') and msg.get('content')
    ]


def _rescatar_llamada_suelta(content, nombres_validos):
    """Convierte en llamada real una herramienta que el modelo escribio como texto.

    Algunos modelos (visto con gpt-oss via Ollama) devuelven la invocacion dentro
    del contenido en vez del campo `tool_calls`, y a veces con la clave equivocada:
    `{"type": "actualizar_documentos", "id": 2}` en lugar de
    `{"name": ..., "arguments": {...}}`. Sin esto, el usuario ve ese JSON crudo como
    si fuera la respuesta — parece que el agente no estuviera conectado a nada.

    Devuelve (nombre, argumentos) o (None, None) si no hay nada que rescatar.
    """
    if not content:
        return None, None
    # El JSON puede venir suelto, dentro de un bloque de codigo, o incrustado en
    # medio de una frase ("We need to call tool.ACTION{...}"), asi que se buscan
    # todos los objetos balanceados del texto y se prueba uno por uno.
    texto = content.strip().replace('```json', '```')
    candidatos = []
    for inicio, caracter in enumerate(texto):
        if caracter != '{':
            continue
        profundidad = 0
        for fin in range(inicio, len(texto)):
            if texto[fin] == '{':
                profundidad += 1
            elif texto[fin] == '}':
                profundidad -= 1
                if profundidad == 0:
                    candidatos.append(texto[inicio:fin + 1])
                    break
        if len(candidatos) >= 5:
            break

    datos = None
    for bruto in candidatos:
        try:
            posible = json.loads(bruto)
        except (TypeError, ValueError):
            continue
        if isinstance(posible, dict):
            datos = posible
            break
    if datos is None:
        return None, None

    nombre = None
    for clave in ('name', 'tool', 'function', 'tool_name', 'type', 'action', 'tool_call'):
        valor = datos.get(clave)
        if isinstance(valor, dict):
            valor = valor.get('name')
        if isinstance(valor, str) and valor in nombres_validos:
            nombre = valor
            break
    if not nombre:
        return None, None

    args = datos.get('arguments') or datos.get('parameters') or datos.get('args')
    if not isinstance(args, dict):
        args = {k: v for k, v in datos.items()
                if k not in ('name', 'tool', 'function', 'tool_name', 'type', 'action', 'tool_call')}
    return nombre, args


def _run_tool_calls(content_blocks, odoo_client: OdooClient) -> list[dict]:
    results = []
    for block in content_blocks:
        if block.type == "tool_use":
            result = execute_tool(block.name, block.input, odoo_client)
            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result, ensure_ascii=False, default=str),
            })
    return results


def _extract_text(response) -> str:
    return "\n".join(
        block.text for block in response.content
        if hasattr(block, 'type') and block.type == "text"
    )


# ── Agente con datos en vivo (proveedor-agnóstico) ────────────────────

_MAX_ITERS = 8
_MAX_TOOL_RESULT_CHARS = 6000  # tope defensivo: mismo orden que MAX_STDOUT en python_sandbox.py


def _tool_result_json(result: dict) -> str:
    """Serializa el resultado de una tool para el historial, con tope de tamaño.

    El array `messages` completo se reenvía ENTERO al modelo en cada una de las
    _MAX_ITERS vueltas del loop de agente — sin este tope, una sola tool (ej.
    run_sql/query_odoo sin `fields` acotados) puede meter miles de tokens que
    después se repiten en cada vuelta siguiente y multiplican el costo total
    de la respuesta (causa raíz del consumo excesivo de tokens reportado).
    """
    text = json.dumps(result, ensure_ascii=False, default=str)
    if len(text) > _MAX_TOOL_RESULT_CHARS:
        text = (text[:_MAX_TOOL_RESULT_CHARS] +
                '\n… (resultado truncado por tamaño — pide menos filas/campos o refina el filtro)')
    return text


def _tool_status(name: str, args: dict) -> str:
    """Mensaje de progreso legible para el usuario según la herramienta en curso."""
    a = args or {}
    system = a.get('system') or ''
    if name == 'list_systems':
        return 'Revisando los sistemas conectados…'
    if name == 'list_tables':
        return f'Explorando las tablas de {system}…' if system else 'Explorando las tablas disponibles…'
    if name == 'describe_table':
        table = a.get('table') or ''
        return f'Revisando la estructura de {table}…' if table else 'Revisando la estructura de los datos…'
    if name == 'run_sql':
        from services import agent_tools
        tbls = agent_tools._tables_in_sql(a.get('sql', '')) if a.get('sql') else None
        if tbls:
            return f'Consultando {", ".join(tbls)}…'
        return f'Consultando {system}…' if system else 'Ejecutando la consulta…'
    if name == 'query_odoo':
        model = a.get('model') or ''
        return f'Consultando {model} en {system}…' if model else f'Consultando {system}…'
    if name == 'run_python':
        n = len(a.get('datasets') or [])
        if n:
            return f'Analizando con Python ({n} dataset{"s" if n > 1 else ""})…'
        return 'Ejecutando análisis en Python…'
    if name == 'read_company_document':
        return 'Revisando un documento de la empresa…'
    return 'Procesando…'


def _parse_ollama_args(raw) -> dict:
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return {}
    return raw or {}


def _provider_for_model(model: str) -> str:
    """Infiere el proveedor a partir del modelo elegido en el selector del front
    (prioridad sobre AI_PROVIDER — ver AvailableModelsView, que solo ofrece modelos
    de proveedores con API key configurada)."""
    if model.startswith('claude-'):
        return 'anthropic'
    if model.startswith('deepseek-'):
        return 'deepseek'
    return 'ollama'


def run_agent_live_events(history: list[dict], organization, system_prompt: str, model: str = None, allowed_ids=None, allowed_doc_ids=None):
    """
    Generador del agente con datos en vivo. Va emitiendo dicts de progreso
    {'status': '...'} mientras consulta los sistemas conectados vía tool-use, y al
    final {'final': '<texto con cita real>'}. Proveedor-agnóstico (ollama / anthropic /
    deepseek). `allowed_ids` limita los sistemas accesibles (cuando el chat usa un
    agente con scope).
    """
    provider = _provider_for_model(model) if model else getattr(settings, 'AI_PROVIDER', 'ollama')
    if provider == 'anthropic':
        yield from _run_anthropic_agent_live_events(history, system_prompt, organization, model, allowed_ids, allowed_doc_ids)
    elif provider == 'deepseek':
        yield from _run_deepseek_agent_events(history, system_prompt, organization, model, allowed_ids, allowed_doc_ids)
    else:
        yield from _run_ollama_agent_events(history, system_prompt, organization, model, allowed_ids, allowed_doc_ids)


def run_agent_live(history: list[dict], organization, system_prompt: str, model: str = None, allowed_ids=None, allowed_doc_ids=None) -> str:
    """Versión no-streaming: drena el generador y devuelve solo el texto final."""
    final = ''
    for event in run_agent_live_events(history, organization, system_prompt, model, allowed_ids, allowed_doc_ids):
        if 'final' in event:
            final = event['final']
    return final


def _run_ollama_agent_events(history, system_prompt, organization, model=None, allowed_ids=None, allowed_doc_ids=None):
    from services import agent_tools

    base_url, model, headers = _ollama_config(model)
    tools = agent_tools.tools_for_ollama(organization, allowed_ids)
    provenance: list = []
    artifacts: dict = {}
    seen_calls: set = set()

    messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        if msg.get('role') in ('user', 'assistant') and msg.get('content'):
            messages.append({"role": msg['role'], "content": _strip_inline_images(msg['content'])})

    try:
        for _ in range(_MAX_ITERS):
            resp = _post_chat(base_url, {"model": model, "messages": messages,
                                         "tools": tools, "stream": False}, headers)
            msg = resp.json().get('message', {})
            tool_calls = msg.get('tool_calls') or []

            if not tool_calls:
                nombre_suelto, args_sueltos = _rescatar_llamada_suelta(
                    msg.get('content'), {t['function']['name'] for t in tools},
                )
                if nombre_suelto:
                    tool_calls = [{
                        'id': f'rescate-{nombre_suelto}',
                        'function': {'name': nombre_suelto,
                                     'arguments': json.dumps(args_sueltos or {})},
                    }]
                else:
                    yield {'final': _finalize((msg.get('content') or '').strip(), provenance, artifacts)}
                    return

            messages.append({
                "role": "assistant",
                "content": msg.get('content', ''),
                "tool_calls": tool_calls,
            })
            for tc in tool_calls:
                fn = tc.get('function', {})
                name = fn.get('name')
                args = _parse_ollama_args(fn.get('arguments'))
                sig = f"{name}:{json.dumps(args, sort_keys=True, default=str)}"
                if sig in seen_calls:
                    # Evita el bucle: no re-ejecuta la misma consulta, empuja a responder.
                    messages.append({"role": "tool", "content": json.dumps(
                        {"note": "Ya ejecutaste esta misma consulta. Responde ahora con los resultados que ya tienes; no repitas herramientas."},
                        ensure_ascii=False)})
                    continue
                seen_calls.add(sig)
                yield {'status': _tool_status(name, args)}
                result = agent_tools.execute_tool(name, args, organization, provenance, allowed_ids, artifacts, allowed_doc_ids)
                messages.append({"role": "tool", "content": _tool_result_json(result)})

        yield {'final': _finalize(
            "Consulté los sistemas pero no logré cerrar la respuesta. Reformula la pregunta de forma más específica.",
            provenance, artifacts)}
    except requests.exceptions.ConnectionError:
        yield {'final': "No se pudo conectar con el modelo. Si usas Ollama local, asegúrate de que esté corriendo; si usas Ollama Cloud, revisa OLLAMA_API_KEY y la conexión."}
    except requests.exceptions.HTTPError:
        logger.exception("Ollama agent loop falló tras reintentos")
        yield {'final': _MODEL_DOWN_MSG}
    except Exception as e:
        logger.exception("Ollama agent loop falló")
        yield {'final': f"Error al consultar los sistemas: {str(e)}"}


def _run_deepseek_agent_events(history, system_prompt, organization, model=None, allowed_ids=None, allowed_doc_ids=None):
    """
    API de DeepSeek — compatible con el formato de chat completions de OpenAI.
    Reusa `tools_for_ollama` porque el esquema de herramientas es idéntico
    ({"type": "function", "function": {...}}). A diferencia de Ollama, cada
    tool_call trae un `id` propio y la respuesta debe ir en un mensaje "tool"
    separado por cada uno (no un solo mensaje combinado).
    """
    from services import agent_tools

    model = model or settings.DEEPSEEK_MODEL
    tools = agent_tools.tools_for_ollama(organization, allowed_ids)
    provenance: list = []
    artifacts: dict = {}
    seen_calls: set = set()

    messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        if msg.get('role') in ('user', 'assistant') and msg.get('content'):
            messages.append({"role": msg['role'], "content": _strip_inline_images(msg['content'])})

    headers = {
        "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        for _ in range(_MAX_ITERS):
            resp = requests.post(
                "https://api.deepseek.com/chat/completions",
                json={"model": model, "messages": messages, "tools": tools, "stream": False},
                headers=headers, timeout=300,
            )
            if resp.status_code != 200:
                try:
                    detail = resp.json().get('error', {}).get('message', resp.text)
                except Exception:
                    detail = resp.text
                yield {'final': f"DeepSeek respondió con un error: {detail}"}
                return

            msg = resp.json()['choices'][0]['message']
            tool_calls = msg.get('tool_calls') or []

            if not tool_calls:
                nombre_suelto, args_sueltos = _rescatar_llamada_suelta(
                    msg.get('content'), {t['function']['name'] for t in tools},
                )
                if nombre_suelto:
                    tool_calls = [{
                        'id': f'rescate-{nombre_suelto}',
                        'function': {'name': nombre_suelto,
                                     'arguments': json.dumps(args_sueltos or {})},
                    }]
                else:
                    yield {'final': _finalize((msg.get('content') or '').strip(), provenance, artifacts)}
                    return

            messages.append({
                "role": "assistant",
                "content": msg.get('content'),
                "tool_calls": tool_calls,
            })
            for tc in tool_calls:
                fn = tc.get('function', {})
                name = fn.get('name')
                try:
                    args = json.loads(fn.get('arguments') or '{}')
                except (TypeError, ValueError):
                    args = {}
                sig = f"{name}:{json.dumps(args, sort_keys=True, default=str)}"
                if sig in seen_calls:
                    messages.append({"role": "tool", "tool_call_id": tc.get('id'), "content": json.dumps(
                        {"note": "Ya ejecutaste esta misma consulta. Responde ahora con los resultados que ya tienes; no repitas herramientas."},
                        ensure_ascii=False)})
                    continue
                seen_calls.add(sig)
                yield {'status': _tool_status(name, args)}
                result = agent_tools.execute_tool(name, args, organization, provenance, allowed_ids, artifacts, allowed_doc_ids)
                messages.append({
                    "role": "tool", "tool_call_id": tc.get('id'),
                    "content": _tool_result_json(result),
                })

        yield {'final': _finalize(
            "Consulté los sistemas pero no logré cerrar la respuesta. Reformula la pregunta de forma más específica.",
            provenance, artifacts)}
    except requests.exceptions.ConnectionError:
        yield {'final': "No se pudo conectar con la API de DeepSeek. Revisa la conexión."}
    except requests.exceptions.HTTPError:
        logger.exception("DeepSeek agent loop falló tras reintentos")
        yield {'final': _MODEL_DOWN_MSG}
    except Exception as e:
        logger.exception("DeepSeek agent loop falló")
        yield {'final': f"Error al consultar los sistemas: {str(e)}"}


def _run_anthropic_agent_live_events(history, system_prompt, organization, model=None, allowed_ids=None, allowed_doc_ids=None):
    from services import agent_tools

    tools = agent_tools.tools_for_anthropic(organization, allowed_ids)
    provenance: list = []
    artifacts: dict = {}
    messages = _build_api_messages(history)
    client = _get_anthropic_client()

    try:
        for _ in range(_MAX_ITERS):
            response = client.messages.create(
                model=model or "claude-sonnet-4-6",
                max_tokens=4096,
                system=system_prompt,
                tools=tools,
                messages=messages,
            )
            if response.stop_reason != "tool_use":
                yield {'final': _finalize(_extract_text(response), provenance, artifacts)}
                return

            messages.append({"role": "assistant", "content": response.content})
            results = []
            for block in response.content:
                if getattr(block, 'type', None) == "tool_use":
                    yield {'status': _tool_status(block.name, block.input)}
                    result = agent_tools.execute_tool(block.name, block.input, organization, provenance, allowed_ids, artifacts, allowed_doc_ids)
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": _tool_result_json(result),
                    })
            messages.append({"role": "user", "content": results})

        yield {'final': _finalize("Superé el límite de iteraciones. Intenta una pregunta más específica.", provenance, artifacts)}
    except Exception as e:
        yield {'final': f"Error al consultar los sistemas: {str(e)}"}


_INLINE_IMG_RE = re.compile(r'!\[([^\]]*)\]\(data:image/[^)]+\)')
_FIG_MARKER_RE = re.compile(r'\[\[FIGURA_\d+\]\]')


def _strip_inline_images(content: str) -> str:
    """Reemplaza imágenes base64 embebidas por un placeholder al armar el
    historial para el modelo — un gráfico previo pesa cientos de KB de contexto."""
    if not content or 'data:image/' not in content:
        return content
    return _INLINE_IMG_RE.sub(r'[gráfico: \1]', content)


def _embed_figures(text: str, artifacts: dict) -> str:
    """Sustituye los marcadores [[FIGURA_n]] por la imagen markdown real."""
    if not artifacts:
        return _FIG_MARKER_RE.sub('', text)
    for marker, png_b64 in artifacts.items():
        uri = f'data:image/png;base64,{png_b64}'
        # A veces el modelo envuelve el marcador en su propia sintaxis de imagen
        # (![alt]([[FIGURA_n]])): ahí el marcador es la URL, no el bloque entero.
        wrapped = re.compile(r'!\[([^\]]*)\]\(\s*' + re.escape(marker) + r'\s*\)')
        if wrapped.search(text):
            text = wrapped.sub(lambda m: f'![{m.group(1)}]({uri})', text)
        elif marker in text:
            text = text.replace(marker, f'![Gráfico generado por el análisis]({uri})')
        else:
            # El modelo olvidó el marcador: adjunta la figura al final igual.
            text = f'{text}\n\n![Gráfico generado por el análisis]({uri})'
    return _FIG_MARKER_RE.sub('', text)


_CLAVES_DE_LLAMADA = ('name', 'tool', 'function', 'tool_name', 'type', 'action', 'tool_call')


def _quitar_llamadas_visibles(texto: str) -> str:
    """Saca del texto los JSON de llamada a herramienta que el modelo deja escritos.

    Algunos modelos anteponen la invocacion a su propia respuesta
    (`{"tool":"buscar_en_fuentes",...}He encontrado que...`). El usuario no tiene por
    que ver eso: la herramienta ya se ejecuto, es ruido de implementacion.
    """
    if not texto or '{' not in texto:
        return texto
    salida, i = [], 0
    while i < len(texto):
        if texto[i] != '{':
            salida.append(texto[i])
            i += 1
            continue
        profundidad, fin = 0, None
        for j in range(i, len(texto)):
            if texto[j] == '{':
                profundidad += 1
            elif texto[j] == '}':
                profundidad -= 1
                if profundidad == 0:
                    fin = j
                    break
        if fin is None:
            salida.append(texto[i])
            i += 1
            continue
        bruto = texto[i:fin + 1]
        try:
            datos = json.loads(bruto)
        except (TypeError, ValueError):
            datos = None
        if isinstance(datos, dict) and any(k in datos for k in _CLAVES_DE_LLAMADA):
            i = fin + 1          # se descarta: era una llamada, no texto
            continue
        salida.append(bruto)
        i = fin + 1
    return ''.join(salida).strip()


def _finalize(text: str, provenance: list, artifacts: dict = None) -> str:
    from services import agent_tools
    text = _quitar_llamadas_visibles((text or '').strip())
    text = _embed_figures(text, artifacts or {})
    if '[Fuente' in text:  # el modelo ya citó: no dupliques
        return text
    return text + agent_tools.build_citation(provenance)

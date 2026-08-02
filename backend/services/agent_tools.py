"""
Tool layer genérico del agente.

Expone los sistemas conectados de una organización como herramientas que el LLM
puede invocar para consultar los datos REALES en vivo (listar tablas, describir,
ejecutar SELECT) y registra la procedencia de cada consulta para poder citar la
fuente. Funciona con conectores SQL (PostgreSQL / MSSQL / SAP B1). Proveedor-
agnóstico: hay convertidores para el formato de Ollama y de Anthropic.
"""
import re
from datetime import datetime

from apps.organizations.models import SystemConnection

SQL_TYPES = ('mssql', 'postgresql')

# Prefijo de la cita según categoría del sistema ("ERP·Odoo Chile·facturas").
# 'otro' no lleva prefijo para no ensuciar la cita.
_CATEGORY_PREFIX = {'erp': 'ERP', 'crm': 'CRM', 'db': 'BD'}

# Palabras que indican escritura/DDL — prohibidas (el agente es de solo lectura)
_FORBIDDEN = re.compile(
    r'\b(insert|update|delete|drop|alter|truncate|create|grant|revoke|merge|exec|execute|call|into)\b',
    re.IGNORECASE,
)


# ── Conexiones ────────────────────────────────────────────────────────────────

def _active_connections(org, allowed_ids=None):
    qs = SystemConnection.objects.filter(organization=org, is_active=True)
    if allowed_ids is not None:
        qs = qs.filter(id__in=allowed_ids)
    return list(qs)


def _find(org, system_name, allowed_ids=None):
    for c in _active_connections(org, allowed_ids):
        if c.name == system_name:
            return c
    return None


def _sql_client(conn):
    from services.sql_client import SQLClient
    return SQLClient(conn.connector_type, conn.get_config())


def _odoo_client(conn):
    from services.odoo_client import OdooClient
    cfg = conn.get_config()
    return OdooClient(cfg['url'], cfg['db'], cfg['username'], cfg['api_key'])


# ── Definición neutral de herramientas ────────────────────────────────────────

def _tools_spec(org, allowed_ids=None):
    conns = _active_connections(org, allowed_ids)
    systems = ', '.join(f'"{c.name}" ({c.connector_type})' for c in conns) or 'ninguno'
    return [
        {
            "name": "list_systems",
            "description": "Lista los sistemas conectados de la empresa y su tipo. Úsalo si no sabes qué hay disponible.",
            "parameters": {"type": "object", "properties": {}},
        },
        {
            "name": "list_tables",
            "description": f"Lista las tablas disponibles de un sistema. Sistemas conectados: {systems}.",
            "parameters": {
                "type": "object",
                "properties": {"system": {"type": "string", "description": "Nombre exacto del sistema conectado"}},
                "required": ["system"],
            },
        },
        {
            "name": "describe_table",
            "description": "Devuelve las columnas (nombre y tipo) de una tabla, para saber qué se puede consultar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "system": {"type": "string"},
                    "table": {"type": "string"},
                },
                "required": ["system", "table"],
            },
        },
        {
            "name": "run_sql",
            "description": (
                "Ejecuta una consulta SQL de SOLO LECTURA (SELECT) sobre un sistema y devuelve las filas reales. "
                "Es la forma de obtener el dato que responde la pregunta. Una sola sentencia SELECT. "
                "NUNCA inventes un dato: si no ejecutaste una consulta que lo respalde, dilo."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "system": {"type": "string", "description": "Nombre del sistema SQL"},
                    "sql": {"type": "string", "description": "Consulta SELECT (sintaxis Postgres o MSSQL según el sistema)"},
                },
                "required": ["system", "sql"],
            },
        },
        {
            "name": "query_odoo",
            "description": (
                "Consulta registros REALES de un sistema Odoo (solo lectura). Usa describe_table "
                "primero para ver los campos disponibles de un modelo (ej: res.partner, sale.order, "
                "account.move, product.template, purchase.order, stock.quant). El dominio sigue la "
                "sintaxis de Odoo: lista de tripletas [campo, operador, valor], ej: "
                '[["customer_rank", ">", 0], ["name", "ilike", "Alexis"]]. '
                "NUNCA inventes un dato: si no ejecutaste esta consulta, dilo."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "system": {"type": "string", "description": "Nombre del sistema Odoo conectado"},
                    "model": {"type": "string", "description": "Nombre técnico del modelo Odoo, ej: res.partner"},
                    "domain": {
                        "type": "array",
                        "description": "Filtro estilo Odoo: lista de [campo, operador, valor]. Vacío = sin filtro.",
                        "items": {"type": "array"},
                    },
                    "fields": {
                        "type": "array",
                        "description": "Campos a traer (nombres técnicos). Recomendado especificar, no traer todos.",
                        "items": {"type": "string"},
                    },
                    "limit": {"type": "integer", "description": "Máximo de registros (default 50, tope 200)."},
                    "order": {"type": "string", "description": "Orden, ej: 'create_date desc'."},
                },
                "required": ["system", "model"],
            },
        },
        {
            "name": "run_python",
            "description": (
                "Análisis avanzado con Python (pandas, numpy, matplotlib). Declara en `datasets` las consultas "
                "SELECT que necesitas; cada una queda disponible en tu código como un DataFrame pandas con ese "
                "nombre de variable. Usa print() para resultados numéricos y matplotlib (plt) para gráficos — "
                "cada figura que crees se mostrará al usuario como imagen. NO uses plt.show() ni plt.savefig(). "
                "El resultado incluye marcadores [[FIGURA_n]]: cópialos tal cual en tu respuesta donde quieras "
                "que aparezca cada gráfico. Úsalo para tendencias, correlaciones, proyecciones, rankings o "
                "cualquier análisis que una consulta SQL sola no resuelve bien."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "datasets": {
                        "type": "array",
                        "description": "Datos a cargar antes de ejecutar el código",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "description": "Nombre de variable del DataFrame (ej: ventas)"},
                                "system": {"type": "string", "description": "Sistema SQL conectado de donde leer"},
                                "sql": {"type": "string", "description": "Consulta SELECT que llena el DataFrame"},
                            },
                            "required": ["name", "system", "sql"],
                        },
                    },
                    "code": {"type": "string", "description": "Código Python. Los DataFrames de datasets ya existen como variables."},
                },
                "required": ["code"],
            },
        },
        {
            "name": "read_company_document",
            "description": (
                "Devuelve el contenido completo de un documento de la empresa (política, manual, catálogo, "
                "etc.) a partir de su id. Los documentos disponibles (con su id y un resumen) ya están en tu "
                "contexto — úsala cuando el resumen no alcance para responder con el detalle que pide el usuario."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "description": "id del documento (viene en el índice del contexto)"},
                },
                "required": ["id"],
            },
        },
        {
            "name": "buscar_en_fuentes",
            "description": (
                "Busca en TODO lo que la empresa tiene conectado: los documentos y archivos de "
                "Drive, y los sistemas y tablas conectados. Úsala cuando el usuario pregunte si "
                "existe algo ('¿tengo algún reporte de contabilidad?', 'busca en mis archivos...') "
                "en vez de responder que no puedes ver sus archivos. Devuelve dónde está cada "
                "coincidencia y un fragmento del texto."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "consulta": {
                        "type": "string",
                        "description": "Palabra o frase a buscar, por ejemplo 'reporte de contabilidad'",
                    },
                },
                "required": ["consulta"],
            },
        },
        {
            "name": "actualizar_documentos",
            "description": (
                "Vuelve a bajar desde Google Drive los archivos conectados y devuelve el contenido "
                "ACTUALIZADO. Úsala SIEMPRE que el usuario diga que editó, actualizó o cambió un "
                "archivo — nunca le pidas que te pegue el contenido: puedes leerlo tú. Si pasa un "
                "id, devuelve solo ese documento; si no, devuelve todos."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "description": "id del documento a releer (opcional)"},
                },
                "required": [],
            },
        },
    ]


def tools_for_ollama(org, allowed_ids=None):
    return [{"type": "function", "function": s} for s in _tools_spec(org, allowed_ids)]


def tools_for_anthropic(org, allowed_ids=None):
    return [
        {"name": s["name"], "description": s["description"], "input_schema": s["parameters"]}
        for s in _tools_spec(org, allowed_ids)
    ]


# ── Ejecución ─────────────────────────────────────────────────────────────────

def _check_readonly(sql: str):
    if not sql:
        return False, "SQL vacío."
    cleaned = sql.strip().rstrip(';').strip()
    if ';' in cleaned:
        return False, "Solo se permite una sentencia."
    if not re.match(r'^\s*(select|with)\b', cleaned, re.IGNORECASE):
        return False, "Solo se permiten consultas SELECT de lectura."
    if _FORBIDDEN.search(cleaned):
        return False, "Operación de escritura/DDL no permitida (el agente es de solo lectura)."
    return True, cleaned


def _tables_in_sql(sql: str):
    found = re.findall(r'(?:from|join)\s+["\[]?([a-zA-Z_][\w.]*)', sql, re.IGNORECASE)
    return list(dict.fromkeys(found)) or None


# Los modelos inventan nombres de parametro (`query` por `consulta`, `document_id`
# por `id`). Antes de ejecutar se traducen: el usuario no tiene por que ver un
# error solo porque el modelo eligio otro sinonimo.
_ALIAS_ARGS = {
    'buscar_en_fuentes': {'consulta': ('query', 'q', 'busqueda', 'search', 'texto', 'termino')},
    'actualizar_documentos': {'id': ('document_id', 'doc_id', 'documento_id')},
    'read_company_document': {'id': ('document_id', 'doc_id', 'documento_id')},
}


def _normalizar_args(name, args):
    args = dict(args or {})
    for esperado, sinonimos in (_ALIAS_ARGS.get(name) or {}).items():
        if esperado in args:
            continue
        for s in sinonimos:
            if s in args:
                args[esperado] = args.pop(s)
                break
    return args


def execute_tool(name: str, args: dict, org, provenance: list, allowed_ids=None, artifacts: dict = None) -> dict:
    """Ejecuta una herramienta y registra procedencia en `provenance`.
    `allowed_ids` (si viene) limita a qué sistemas conectados puede acceder el agente.
    `artifacts` (si viene) acumula figuras generadas: marcador → PNG base64."""
    args = _normalizar_args(name, args)
    now = datetime.now().strftime('%H:%M')
    try:
        if name == 'list_systems':
            return {"systems": [{"name": c.name, "type": c.connector_type} for c in _active_connections(org, allowed_ids)]}

        if name == 'run_python':
            return _run_python_tool(args or {}, org, provenance, allowed_ids, artifacts, now)

        if name == 'buscar_en_fuentes':
            from apps.organizations.models import CompanyDocument, SystemConnection

            consulta = ((args or {}).get('consulta') or '').strip()
            if not consulta:
                return {"error": "Falta qué buscar."}

            hallazgos = []

            # Documentos y archivos (Drive, subidas manuales): titulo y contenido.
            for doc in CompanyDocument.objects.filter(organization=org):
                texto = doc.extracted_text or ''
                en_titulo = consulta.lower() in (doc.title or '').lower()
                pos = texto.lower().find(consulta.lower())
                if not en_titulo and pos < 0:
                    continue
                fragmento = ''
                if pos >= 0:
                    desde = max(0, pos - 120)
                    fragmento = texto[desde:pos + 240].replace('\n', ' ')
                hallazgos.append({
                    "donde": f'Documento «{doc.title}»',
                    "id": doc.id,
                    "coincide_en": 'el título' if en_titulo else 'el contenido',
                    "fragmento": fragmento,
                    "como_leerlo": f'read_company_document({doc.id})',
                })

            # Sistemas conectados: nombre de la conexion y de sus tablas o modulos.
            for conn in SystemConnection.objects.filter(organization=org, is_active=True):
                nombres = []
                cache = conn.schema_cache or {}
                for clave in ('tables', 'models'):
                    valor = cache.get(clave)
                    if isinstance(valor, dict):
                        nombres.extend(valor.keys())
                    elif isinstance(valor, list):
                        nombres.extend([v if isinstance(v, str) else str(v) for v in valor])
                coincidencias = [n for n in nombres if consulta.lower() in str(n).lower()]
                if consulta.lower() in conn.name.lower() or coincidencias:
                    hallazgos.append({
                        "donde": f'Sistema «{conn.name}»',
                        "id": conn.id,
                        "coincide_en": 'el nombre del sistema' if not coincidencias else 'sus tablas',
                        "tablas": coincidencias[:20] or None,
                    })

            provenance.append({
                "system": 'Búsqueda en las fuentes', "category": "otro",
                "tables": None, "rows": len(hallazgos), "at": now,
            })
            if not hallazgos:
                inventario = list(
                    CompanyDocument.objects.filter(organization=org).values_list('title', flat=True)
                )
                return {
                    "encontrado": False,
                    "consulta": consulta,
                    "nota": 'No hay ninguna coincidencia. Esto es TODO lo que hay conectado hoy.',
                    "documentos_disponibles": inventario,
                }
            return {"encontrado": True, "consulta": consulta, "resultados": hallazgos}

        if name == 'actualizar_documentos':
            from apps.organizations.models import CompanyDocument, SystemConnection
            from services.drive_sync import _sync_connection

            errores = []
            for conn in SystemConnection.objects.filter(
                organization=org, connector_type='google_drive', is_active=True,
            ):
                try:
                    _sync_connection(conn)
                except Exception as e:
                    errores.append(f'{conn.name}: {e}')

            doc_id = (args or {}).get('id')
            docs = CompanyDocument.objects.filter(organization=org)
            if doc_id:
                docs = docs.filter(id=doc_id)
            docs = list(docs)
            if not docs:
                return {"error": "No hay documentos conectados para actualizar."}

            provenance.append({
                "system": 'Google Drive (relectura)', "category": "otro",
                "tables": None, "rows": len(docs), "at": now,
            })
            return {
                "documentos": [
                    {"id": d.id, "title": d.title, "content": d.extracted_text or ''}
                    for d in docs
                ],
                "errores": errores or None,
            }

        if name == 'read_company_document':
            from apps.organizations.models import CompanyDocument
            doc_id = (args or {}).get('id')
            doc = CompanyDocument.objects.filter(organization=org, id=doc_id).first()
            if not doc:
                return {"error": f"No existe un documento de la empresa con id={doc_id}."}
            if not doc.extracted_text:
                return {"error": f"El documento «{doc.title}» no tiene contenido extraído."}
            provenance.append({"system": f"Documento «{doc.title}»", "category": "otro", "tables": None, "rows": None, "at": now})
            return {"title": doc.title, "category": doc.category, "content": doc.extracted_text}

        system = (args or {}).get('system')
        conn = _find(org, system, allowed_ids)
        if not conn:
            return {"error": f"Sistema '{system}' no encontrado. Usa list_systems para ver los disponibles."}

        if name == 'list_tables':
            if conn.connector_type in SQL_TYPES:
                with _sql_client(conn) as c:
                    return {"system": system, "tables": c.list_tables()}
            sc = conn.schema_cache or {}
            return {"system": system, "tables": [m.get('model') for m in sc.get('models', [])]}

        if name == 'describe_table':
            table = args.get('table')
            if conn.connector_type in SQL_TYPES:
                with _sql_client(conn) as c:
                    return {"system": system, "table": table, "columns": c.describe_table(table)}
            if conn.connector_type == 'odoo':
                client = _odoo_client(conn)
                fields_info = client.execute(table, 'fields_get', [], {'attributes': ['string', 'type']})
                columns = [
                    {"column": k, "type": v.get('type'), "label": v.get('string')}
                    for k, v in fields_info.items() if v.get('type') != 'one2many'
                ]
                return {"system": system, "table": table, "columns": columns[:100]}
            return {"system": system, "table": table, "columns": []}

        if name == 'query_odoo':
            if conn.connector_type != 'odoo':
                return {"error": f"query_odoo solo soporta sistemas Odoo; '{system}' es {conn.connector_type}."}
            model = args.get('model')
            if not model:
                return {"error": "Falta el modelo Odoo (ej: res.partner)."}
            domain = args.get('domain') or []
            fields = args.get('fields') or []
            limit = min(int(args.get('limit') or 50), 200)
            order = args.get('order')
            client = _odoo_client(conn)
            rows = client.search_read(model, domain=domain, fields=fields, limit=limit, order=order)
            provenance.append({"system": system, "category": conn.category,
                               "tables": [model], "rows": len(rows), "at": now})
            return {"system": system, "model": model, "row_count": len(rows), "rows": rows}

        if name == 'run_sql':
            if conn.connector_type not in SQL_TYPES:
                return {"error": f"run_sql solo soporta sistemas SQL; '{system}' es {conn.connector_type}."}
            ok, cleaned_or_err = _check_readonly(args.get('sql', ''))
            if not ok:
                return {"error": cleaned_or_err}
            with _sql_client(conn) as c:
                rows = c.query_as_dict(cleaned_or_err)
            provenance.append({"system": system, "category": conn.category,
                               "tables": _tables_in_sql(cleaned_or_err), "rows": len(rows), "at": now})
            return {"system": system, "row_count": len(rows), "rows": rows}

        return {"error": f"Herramienta desconocida: {name}"}
    except Exception as e:
        return {"error": str(e)}


def _run_python_tool(args: dict, org, provenance: list, allowed_ids, artifacts: dict, now: str) -> dict:
    """Ejecuta run_python: consulta los datasets (solo lectura) y corre el código en el sandbox."""
    from services.python_sandbox import run_python

    code = args.get('code') or ''
    if not code.strip():
        return {"error": "Falta el código Python."}

    datasets = {}
    for ds in args.get('datasets') or []:
        name, system, sql = ds.get('name'), ds.get('system'), ds.get('sql', '')
        if not name or not str(name).isidentifier():
            return {"error": f"Nombre de dataset inválido: '{name}'. Usa un identificador Python (ej: ventas)."}
        conn = _find(org, system, allowed_ids)
        if not conn:
            return {"error": f"Sistema '{system}' no encontrado. Usa list_systems para ver los disponibles."}
        if conn.connector_type not in SQL_TYPES:
            return {"error": f"run_python solo carga datasets de sistemas SQL; '{system}' es {conn.connector_type}."}
        ok, cleaned_or_err = _check_readonly(sql)
        if not ok:
            return {"error": f"Dataset '{name}': {cleaned_or_err}"}
        with _sql_client(conn) as c:
            rows = c.query_as_dict(cleaned_or_err)
        datasets[name] = rows
        provenance.append({"system": system, "category": conn.category,
                           "tables": _tables_in_sql(cleaned_or_err), "rows": len(rows), "at": now})

    result = run_python(code, datasets)
    if result.get('error'):
        return {k: v for k, v in result.items() if v}

    out = {"stdout": result.get('stdout') or '(sin salida de texto)'}
    markers = []
    for png_b64 in result.get('figures') or []:
        if artifacts is None:
            continue
        marker = f"[[FIGURA_{len(artifacts) + 1}]]"
        artifacts[marker] = png_b64
        markers.append(marker)
    if markers:
        out["figuras"] = markers
        out["nota"] = ("Copia cada marcador tal cual (ej: " + markers[0] +
                       ") en tu respuesta final, en su propia línea, donde quieras mostrar ese gráfico.")
    return out


def build_citation(provenance: list) -> str:
    """Construye la línea de cita a partir de las consultas realmente ejecutadas."""
    if not provenance:
        return ""
    parts, seen = [], set()
    for p in provenance:
        prefix = _CATEGORY_PREFIX.get(p.get('category'))
        for t in (p.get('tables') or [p.get('system')]):
            key = (p['system'], t)
            if key in seen:
                continue
            seen.add(key)
            label = f"{p['system']}·{t}"
            parts.append(f"{prefix}·{label}" if prefix else label)
    when = provenance[-1].get('at')
    return f"\n\n_[Fuente: {', '.join(parts)} · consultado {when}]_"

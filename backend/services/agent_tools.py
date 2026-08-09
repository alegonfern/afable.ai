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

# Las que solo sirven si hay un sistema conectado que consultar. Sin conexiones se
# retiran: ofrecerle a un modelo una herramienta que no puede usar hace que gaste el
# turno intentando invocarla — se vio pasar exactamente eso con el prompt.
SOLO_CON_CONEXIONES = (
    'list_systems', 'list_tables', 'describe_table', 'run_sql', 'query_odoo', 'run_python',
)

# Las que solo tienen sentido dentro de una Sesión: sin Sesión no hay dónde anotar la
# tarea, y ofrecerla igual haría que el modelo la invoque y reciba un error.
SOLO_EN_SESION = ('crear_tarea',)


def _tools_spec(org, allowed_ids=None, sesion=None):
    conns = _active_connections(org, allowed_ids)
    systems = ', '.join(f'"{c.name}" ({c.connector_type})' for c in conns) or 'ninguno'
    todas = [
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
                "Drive, y los sistemas y tablas conectados. Busca por SIGNIFICADO, no solo por "
                "palabra exacta: puedes pasarle la pregunta del usuario tal como la hizo y te "
                "devuelve los fragmentos de documento que la responden. Úsala cuando el usuario "
                "pregunte si existe algo ('¿tengo algún reporte de contabilidad?', 'busca en mis "
                "archivos...') y también cuando pregunte por el CONTENIDO de las políticas, "
                "manuales o contratos de la empresa y no tengas ese texto a la vista. Nunca "
                "respondas que no puedes ver sus archivos. Devuelve dónde está cada coincidencia "
                "y los fragmentos de texto relevantes."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "consulta": {
                        "type": "string",
                        "description": (
                            "Qué buscar, en lenguaje natural. Puede ser la pregunta completa del "
                            "usuario, por ejemplo '¿cuántos días de vacaciones me corresponden?'"
                        ),
                    },
                },
                "required": ["consulta"],
            },
        },
        {
            "name": "crear_documento",
            "description": (
                "Crea un documento de texto NUEVO en los archivos de la empresa y lo guarda. "
                "Úsala cuando el usuario pida escribir, redactar o preparar algo que quiera "
                "conservar: un informe, una propuesta, un procedimiento, una minuta. Devuelve "
                "el id, con el que después puedes editarlo. NO la uses para responder en el "
                "chat: solo cuando el usuario quiera que quede guardado."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "titulo": {"type": "string", "description": "Nombre del documento"},
                    "contenido": {"type": "string", "description": "El texto completo, en markdown"},
                },
                "required": ["titulo", "contenido"],
            },
        },
        {
            "name": "ver_planilla",
            "description": (
                "Qué hojas y columnas tiene una planilla de Excel. Úsalo SIEMPRE antes de "
                "escribir en ella: sin esto adivinas los nombres de las columnas, y una "
                "fórmula sobre la columna equivocada es peor que no hacer nada, porque "
                "queda escrita y con cara de correcta."
            ),
            "parameters": {
                "type": "object",
                "properties": {"id": {"type": "integer", "description": "id del documento"}},
                "required": ["id"],
            },
        },
        {
            "name": "escribir_en_planilla",
            "description": (
                "Cambia UNA celda de una planilla de Excel: por ejemplo marcar 'Vencido' en "
                "C4. El resto del archivo queda intacto y el cambio se registra con tu "
                "nombre. Usa `ver_planilla` primero para saber dónde estás escribiendo."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "description": "id del documento"},
                    "celda": {"type": "string", "description": "Por ejemplo C4"},
                    "valor": {"type": "string", "description": "Lo que va en la celda"},
                    "hoja": {"type": "string", "description": "Nombre de la hoja (opcional)"},
                },
                "required": ["id", "celda", "valor"],
            },
        },
        {
            "name": "agregar_columna_a_planilla",
            "description": (
                "Agrega una columna al final de una planilla, con una fórmula por fila o con "
                "valores. En la fórmula, escribe {fila} donde va el número de fila: "
                "'=B{fila}*0.19' pone el IVA de cada fila. Es la forma de hacer 'agrégale el "
                "margen' sin enumerar 300 celdas ni equivocarte en la 217."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "description": "id del documento"},
                    "titulo": {"type": "string", "description": "Encabezado de la columna"},
                    "formula": {
                        "type": "string",
                        "description": "Fórmula con {fila}, por ejemplo '=B{fila}*0.19'",
                    },
                    "valores": {
                        "type": "array", "items": {"type": "string"},
                        "description": "Alternativa a la fórmula: un valor por fila",
                    },
                    "hoja": {"type": "string", "description": "Nombre de la hoja (opcional)"},
                },
                "required": ["id", "titulo"],
            },
        },
        {
            "name": "editar_documento_word",
            "description": (
                "Cambia un fragmento EXACTO dentro de un documento de Word (.docx), sin "
                "tocar el resto ni crear una copia. Lee el documento primero y copia el "
                "fragmento tal como está. Si el párrafo tenía negritas o cursivas mezcladas, "
                "puede quedar con formato parejo — se te avisa en la respuesta y conviene "
                "que se lo digas a la persona. El original queda siempre en la versión 1."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "description": "id del documento"},
                    "viejo": {"type": "string", "description": "El fragmento tal como está hoy"},
                    "nuevo": {"type": "string", "description": "Con qué reemplazarlo"},
                    "mensaje": {"type": "string", "description": "Qué cambiaste, en una línea"},
                },
                "required": ["id", "viejo", "nuevo"],
            },
        },
        {
            "name": "editar_documento",
            "description": (
                "Cambia un fragmento EXACTO del texto de un documento por otro, sin tocar el "
                "resto. Primero lee el documento con read_company_document para copiar el "
                "fragmento tal como está, con sus espacios y saltos de línea. El fragmento "
                "tiene que aparecer UNA sola vez: si aparece más, incluye más texto alrededor "
                "para que sea único. Cada edición queda registrada con tu nombre y se puede "
                "revertir, así que no tengas miedo de equivocarte — pero nunca cambies algo "
                "que el usuario no pidió cambiar."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "description": "id del documento"},
                    "viejo": {"type": "string", "description": "El fragmento tal como está hoy"},
                    "nuevo": {"type": "string", "description": "Con qué reemplazarlo"},
                    "mensaje": {
                        "type": "string",
                        "description": "Qué cambiaste y por qué, en una línea",
                    },
                },
                "required": ["id", "viejo", "nuevo"],
            },
        },
        {
            "name": "reescribir_documento",
            "description": (
                "Reemplaza TODO el texto de un documento. Úsala solo cuando el documento se "
                "reescribe de punta a punta; para un cambio puntual usa editar_documento, que "
                "no puede perder por accidente lo que no tocaste."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "description": "id del documento"},
                    "contenido": {"type": "string", "description": "El texto completo nuevo"},
                    "mensaje": {"type": "string", "description": "Qué cambiaste, en una línea"},
                },
                "required": ["id", "contenido"],
            },
        },
        {
            "name": "crear_tarea",
            "description": (
                "Anota un pendiente en esta Sesión, para que el equipo lo vea. Úsala cuando de "
                "la conversación salga algo que HAY QUE HACER y que no se resuelve leyendo la "
                "respuesta: un pago que falta, un dato que hay que pedirle a alguien, un "
                "documento por revisar. No la uses para dejar constancia de lo que acabas de "
                "explicar — eso ya quedó en la conversación."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "titulo": {
                        "type": "string",
                        "description": "Qué hay que hacer, en una línea y en imperativo",
                    },
                    "detalle": {
                        "type": "string",
                        "description": "El contexto que necesita quien la tome (opcional)",
                    },
                    "para_mi": {
                        "type": "boolean",
                        "description": (
                            "true si la puedes hacer tú mismo cuando te lo pidan: queda "
                            "asignada a ti y con el botón para ejecutarla"
                        ),
                    },
                },
                "required": ["titulo"],
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
    if not sesion:
        todas = [t for t in todas if t['name'] not in SOLO_EN_SESION]
    if conns:
        return todas
    # Sin conexiones queda el juego de documentos, que es lo que hace falta para leer,
    # crear y editar archivos — y es todo lo que una empresa que solo subió documentos
    # necesita del agente.
    return [t for t in todas if t['name'] not in SOLO_CON_CONEXIONES]


def tools_for_ollama(org, allowed_ids=None, sesion=None):
    return [{"type": "function", "function": s} for s in _tools_spec(org, allowed_ids, sesion)]


def tools_for_anthropic(org, allowed_ids=None, sesion=None):
    return [
        {"name": s["name"], "description": s["description"], "input_schema": s["parameters"]}
        for s in _tools_spec(org, allowed_ids, sesion)
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
    'crear_documento': {
        'titulo': ('title', 'nombre', 'name'),
        'contenido': ('content', 'texto', 'body'),
    },
    'editar_documento': {
        'id': ('document_id', 'doc_id', 'documento_id'),
        'viejo': ('old', 'old_string', 'anterior', 'buscar', 'original'),
        'nuevo': ('new', 'new_string', 'reemplazo', 'replace'),
        'mensaje': ('message', 'motivo', 'descripcion'),
    },
    'reescribir_documento': {
        'id': ('document_id', 'doc_id', 'documento_id'),
        'contenido': ('content', 'texto', 'body'),
        'mensaje': ('message', 'motivo', 'descripcion'),
    },
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


def _documentos(org, allowed_doc_ids=None):
    """Los documentos que este agente alcanza.

    `allowed_doc_ids=None` es sin restricción. Una lista limita a esos documentos,
    y una lista VACÍA no devuelve ninguno: un agente encerrado en un Espacio sin
    documentos no tiene que poder leer los del resto de la empresa. Toda consulta a
    `CompanyDocument` dentro de las herramientas pasa por acá — si alguna se saltea
    esta función, el Espacio deja de valer para esa herramienta.
    """
    from apps.organizations.models import CompanyDocument

    qs = CompanyDocument.objects.filter(organization=org)
    if allowed_doc_ids is not None:
        qs = qs.filter(id__in=allowed_doc_ids)
    return qs


def _crear_tarea(args, sesion, agente, provenance, now):
    """El agente anota un pendiente en la Sesión.

    La otra mitad de "todo lo que un humano puede hacer, un agente también": el agente ya
    podía EJECUTAR una tarea que alguien le asignaba; con esto también la crea. Lo que sale
    de una conversación y hay que hacer deja de depender de que un humano se acuerde de
    anotarlo.

    Queda firmada por el agente (`created_by` vacío, `agent` puesto) para que en la lista se
    vea de dónde salió. Con `para_mi`, además queda asignada a él y con el botón para
    ejecutarla: el agente se compromete a hacerla, no solo la señala.
    """
    from apps.sesiones.models import Task

    if sesion is None:
        return {"error": "Esta conversación no está en una Sesión, así que no hay dónde anotar la tarea."}

    titulo = (args.get('titulo') or '').strip()
    if not titulo:
        return {"error": "Falta el título de la tarea."}

    tarea = Task.objects.create(
        sesion=sesion,
        title=titulo[:255],
        description=(args.get('detalle') or '').strip(),
        agent=agente if args.get('para_mi') else None,
    )
    provenance.append({
        'tipo': 'tarea', 'detalle': f'Anotó la tarea «{titulo}» en {sesion.name}', 'hora': now,
    })
    return {
        'ok': True, 'id': tarea.id, 'titulo': tarea.title,
        'mensaje': f'Quedó anotada en las Tareas de {sesion.name}.',
    }


# Las herramientas que DEJAN ALGO ESCRITO. Se anotan aparte de `provenance` porque no son
# lo mismo: `provenance` dice en qué se apoyó la respuesta, y esto dice qué quedó hecho.
# Lo que quedó hecho tiene que poder abrirse desde el chat mismo — si no, el agente
# trabaja y la persona se entera solo por una frase.
ESCRIBEN_DOCUMENTO = {
    'crear_documento': 'creado',
    'editar_documento': 'editado',
    'reescribir_documento': 'reescrito',
    'editar_documento_word': 'editado',
    'escribir_en_planilla': 'editado',
    'agregar_columna_a_planilla': 'editado',
}


def execute_tool(name: str, args: dict, org, provenance: list, allowed_ids=None, artifacts: dict = None, allowed_doc_ids=None, agente=None, sesion=None) -> dict:
    """Ejecuta la herramienta y, si dejó algo escrito, lo anota en `artifacts`.

    El envoltorio existe para que anotar el documento tocado no dependa de acordarse en
    cada rama: hay seis herramientas que escriben y van a ser más.
    """
    resultado = _ejecutar(
        name, args, org, provenance, allowed_ids, artifacts, allowed_doc_ids, agente, sesion,
    )

    accion = ESCRIBEN_DOCUMENTO.get(name)
    if accion and artifacts is not None and isinstance(resultado, dict) and resultado.get('id'):
        tocados = artifacts.setdefault('documentos', [])
        # Si el agente toca el mismo documento tres veces, es UNA tarjeta, no tres: lo que
        # a la persona le importa es el documento, no cuántas herramientas usó.
        for ya in tocados:
            if ya['id'] == resultado['id']:
                ya['accion'] = 'creado' if ya['accion'] == 'creado' else accion
                break
        else:
            tocados.append({
                'id': resultado['id'],
                'titulo': resultado.get('titulo') or '',
                'accion': accion,
            })
    return resultado


def _ejecutar(name: str, args: dict, org, provenance: list, allowed_ids=None, artifacts: dict = None, allowed_doc_ids=None, agente=None, sesion=None) -> dict:
    """Ejecuta una herramienta y registra procedencia en `provenance`.
    `allowed_ids` (si viene) limita a qué sistemas conectados puede acceder el agente.
    `allowed_doc_ids` hace lo mismo con los documentos: los dos salen del Espacio
    del agente (ver `apps/workspaces/permissions.alcance_de_agente`).
    `artifacts` (si viene) acumula figuras generadas: marcador → PNG base64.
    `agente` es quien está ejecutando: se usa para FIRMAR las versiones que escriba, así
    el historial de un documento dice qué agente lo tocó y no solo que "lo tocó la IA".
    `sesion` es la Sesión de la conversación, si la hay: habilita anotar tareas ahí."""
    args = _normalizar_args(name, args)
    now = datetime.now().strftime('%H:%M')
    try:
        if name == 'list_systems':
            return {"systems": [{"name": c.name, "type": c.connector_type} for c in _active_connections(org, allowed_ids)]}

        if name == 'run_python':
            return _run_python_tool(args or {}, org, provenance, allowed_ids, artifacts, now)

        if name == 'crear_tarea':
            return _crear_tarea(args or {}, sesion, agente, provenance, now)

        if name == 'buscar_en_fuentes':
            from apps.organizations.models import CompanyDocument, SystemConnection

            consulta = ((args or {}).get('consulta') or '').strip()
            if not consulta:
                return {"error": "Falta qué buscar."}

            # Los documentos se buscan de dos formas que se complementan, y por eso
            # conviven en la misma herramienta en vez de en dos:
            #
            # - Semantica (fragmentos vectorizados): encuentra por significado, o sea
            #   responde "¿cuantos dias de vacaciones tengo?" con el parrafo del
            #   reglamento que habla de feriado legal sin que la palabra "vacaciones"
            #   aparezca. Es el camino principal, pero necesita el indice armado.
            # - Literal (subcadena en titulo y texto): no necesita indice, y para
            #   "¿tengo un archivo que se llame X?" es mas preciso que cualquier
            #   vector, porque ahi el usuario quiere la coincidencia exacta.
            por_documento = {}

            from services.retrieval import buscar as buscar_semantico
            for r in buscar_semantico(org, consulta, allowed_doc_ids, k=8):
                h = por_documento.get(r['documento_id'])
                if h is None:
                    por_documento[r['documento_id']] = {
                        "donde": f'Documento «{r["titulo"]}»',
                        "id": r['documento_id'],
                        "coincide_en": 'el sentido del contenido',
                        "fragmentos": [r['texto']],
                        "como_leerlo": f'read_company_document({r["documento_id"]})',
                    }
                elif len(h['fragmentos']) < 3:
                    h['fragmentos'].append(r['texto'])

            for doc in _documentos(org, allowed_doc_ids):
                texto = doc.extracted_text or ''
                en_titulo = consulta.lower() in (doc.title or '').lower()
                pos = texto.lower().find(consulta.lower())
                if not en_titulo and pos < 0:
                    continue
                h = por_documento.get(doc.id)
                if h is not None:
                    # Ya lo trajo la busqueda semantica: solo se precisa por que mas
                    # coincide, sin duplicar el documento en los resultados.
                    h['coincide_en'] += ' y en el título' if en_titulo else ' y textualmente'
                    continue
                fragmento = ''
                if pos >= 0:
                    desde = max(0, pos - 120)
                    fragmento = texto[desde:pos + 240].replace('\n', ' ')
                por_documento[doc.id] = {
                    "donde": f'Documento «{doc.title}»',
                    "id": doc.id,
                    "coincide_en": 'el título' if en_titulo else 'el contenido',
                    "fragmentos": [fragmento] if fragmento else [],
                    "como_leerlo": f'read_company_document({doc.id})',
                }

            hallazgos = list(por_documento.values())

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
                    _documentos(org, allowed_doc_ids).values_list('title', flat=True)
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
            docs = _documentos(org, allowed_doc_ids)
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

        if name == 'editar_documento_word':
            from services.documentos_word import ErrorDeWord, reemplazar

            doc = _documentos(org, allowed_doc_ids).filter(id=(args or {}).get('id')).first()
            if doc is None:
                return {"error": f"No existe un documento con id={(args or {}).get('id')} a tu alcance."}
            try:
                mensaje = reemplazar(
                    doc, (args or {}).get('viejo'), (args or {}).get('nuevo'),
                    agente=agente, mensaje=(args or {}).get('mensaje', ''),
                )
                return {"ok": True, "mensaje": mensaje, "id": doc.id, "titulo": doc.title}
            except ErrorDeWord as e:
                return {"error": str(e)}
            except Exception as e:
                logger.exception('Falló la edición del Word %s', doc.pk)
                return {"error": f'No se pudo escribir en el documento: {e}'}

        if name in ('ver_planilla', 'escribir_en_planilla', 'agregar_columna_a_planilla'):
            return _tocar_planilla(name, args or {}, org, allowed_doc_ids, agente)

        if name in ('crear_documento', 'editar_documento', 'reescribir_documento'):
            return _escribir_documento(name, args or {}, org, provenance, allowed_doc_ids, now, agente)

        if name == 'read_company_document':
            from apps.organizations.models import CompanyDocument
            doc_id = (args or {}).get('id')
            doc = _documentos(org, allowed_doc_ids).filter(id=doc_id).first()
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


# ── Escribir documentos ───────────────────────────────────────────────────────

def _tocar_planilla(name, args, org, allowed_doc_ids, agente=None):
    """Las tres herramientas de planilla, con el mismo embudo de permisos que el resto.

    El documento sale de `_documentos(org, allowed_doc_ids)` — el alcance del agente— así
    que una planilla que él no alcanza no existe para estas herramientas tampoco. Sin eso,
    escribir sería la puerta de atrás de todo lo que los permisos cuidan al leer.
    """
    from services.planillas import (
        ErrorDePlanilla, agregar_columna, escribir_celda, resumen_de,
    )

    doc = _documentos(org, allowed_doc_ids).filter(id=args.get('id')).first()
    if doc is None:
        return {"error": f"No existe una planilla con id={args.get('id')} a tu alcance."}

    try:
        if name == 'ver_planilla':
            return {"planilla": doc.title, "hojas": resumen_de(doc)}

        if name == 'escribir_en_planilla':
            mensaje = escribir_celda(
                doc, args.get('celda'), args.get('valor'),
                hoja=args.get('hoja'), agente=agente,
            )
            return {"ok": True, "mensaje": mensaje, "id": doc.id, "titulo": doc.title}

        valores = args.get('valores')
        mensaje = agregar_columna(
            doc, args.get('titulo'), valores=valores, formula=args.get('formula'),
            hoja=args.get('hoja'), agente=agente,
        )
        return {"ok": True, "mensaje": mensaje, "id": doc.id, "titulo": doc.title}

    except ErrorDePlanilla as e:
        # Es un error que la persona puede corregir ("no hay una hoja Ventas; las que hay
        # son…"), así que se devuelve tal cual para que el agente lo diga.
        return {"error": str(e)}
    except Exception as e:
        logger.exception('Falló una operación sobre la planilla %s', doc.pk)
        return {"error": f'No se pudo escribir en la planilla: {e}'}


def _escribir_documento(name, args, org, provenance, allowed_doc_ids, now, agente=None):
    """Las tres herramientas de escritura: crear, editar por reemplazo y reescribir.

    Todo pasa por `services/documentos.py`, que es lo que garantiza que cada cambio
    quede como una versión firmada. Un camino de escritura que no pase por ahí dejaría
    cambios sin historial, y el historial es justo lo que hace razonable que un agente
    edite documentos de la empresa.
    """
    from apps.organizations.models import CompanyDocument
    from services.documentos import (
        NoEditable, TextoNoEncontrado, asegurar_version_inicial, editar_por_reemplazo,
        escribir, es_editable,
    )

    if name == 'crear_documento':
        titulo = (args.get('titulo') or '').strip()[:255]
        contenido = args.get('contenido') or ''
        if not titulo:
            return {"error": "Falta el título del documento."}
        if not contenido.strip():
            return {"error": "No se crea un documento vacío: escribe su contenido."}

        # Un documento que escribe la IA nace editable y sin archivo adjunto: su
        # contenido ES el texto, no hay un original binario del que extraerlo.
        doc = CompanyDocument.objects.create(
            organization=org, title=titulo, category='otro',
            content_type='text/markdown', editable=True,
            source='manual', is_public=True,
        )
        escribir(doc, contenido, agente=agente, mensaje='Creado por el agente')
        provenance.append({
            "system": f'Documento «{doc.title}» (creado)', "category": "otro",
            "tables": None, "rows": None, "at": now,
        })
        return {
            "ok": True, "id": doc.id, "titulo": doc.title,
            "nota": f'Documento creado con id={doc.id}. Para cambiarlo usa '
                    f'editar_documento con ese id.',
        }

    doc_id = args.get('id')
    doc = _documentos(org, allowed_doc_ids).filter(id=doc_id).first()
    if doc is None:
        return {"error": f"No existe un documento con id={doc_id} al que puedas acceder."}
    if not doc.editable:
        return {
            "error": f'«{doc.title}» no es un documento de texto editable (es '
                     f'{doc.content_type or "un archivo binario"}). Puedes leerlo, y si hay '
                     f'que cambiarlo, crear uno nuevo con crear_documento.',
        }

    # Sin versión 1 no habría a dónde volver despues del primer cambio del agente.
    asegurar_version_inicial(doc)

    try:
        if name == 'editar_documento':
            version = editar_por_reemplazo(
                doc, args.get('viejo') or '', args.get('nuevo') or '',
                agente=agente, mensaje=args.get('mensaje') or '',
            )
        else:
            contenido = args.get('contenido') or ''
            if not contenido.strip():
                return {"error": "No se reescribe un documento a vacío."}
            version = escribir(
                doc, contenido, agente=agente,
                mensaje=args.get('mensaje') or 'Reescrito por el agente',
            )
    except TextoNoEncontrado as e:
        return {"error": str(e)}
    except NoEditable as e:
        return {"error": str(e)}

    provenance.append({
        "system": f'Documento «{doc.title}» (editado)', "category": "otro",
        "tables": None, "rows": None, "at": now,
    })
    return {
        "ok": True, "id": doc.id, "titulo": doc.title, "version": version.numero,
        "nota": f'Guardado como versión {version.numero}. El equipo puede ver qué '
                f'cambiaste y volver atrás.',
    }

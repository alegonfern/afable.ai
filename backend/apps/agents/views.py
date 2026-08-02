import json
import re
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

from .models import (
    AgentConfig, Agent, AgentTemplate, Conversation, Message, Document, Automation,
    Routine, Skill, habilidades_como_contexto,
)
from .serializers import (
    AgentSerializer, AgentTemplateSerializer, ChatRequestSerializer,
    ConversationSerializer, ConversationListSerializer, DocumentSerializer,
    AutomationSerializer, SkillSerializer, SkillWriteSerializer, RoutineSerializer,
)
from apps.organizations.models import Organization
from apps.workspaces.permissions import alcance_de_agente
from services.agent_service import chat_direct, stream_direct, resolve_model


def _conversation_title(agent, message: str) -> str:
    """Título del historial: el agente con que se habló + el tema."""
    if agent is not None and agent.name and agent.name != 'Afable Assistant':
        return f'{agent.name} · {message[:60]}'
    return message[:80]


def _chunk_text(text: str, size: int = 28):
    """Emite el texto en trozos para simular streaming (el agente es no-streaming)."""
    buf = ''
    for word in text.split(' '):
        buf += word + ' '
        if len(buf) >= size:
            yield buf
            buf = ''
    if buf:
        yield buf


AREA_NAMES = {
    'ventas': 'Ventas', 'compras': 'Compras', 'contabilidad': 'Contabilidad',
    'bi': 'Business Intelligence', 'operaciones': 'Operaciones',
    'inventario': 'Inventario', 'rrhh': 'Recursos Humanos',
    'logistica': 'Logística', 'ti': 'Tecnología',
}
ALL_AREAS = list(AREA_NAMES.keys())


def _get_permissions_context(user, is_owner=False):
    """Ya no restringe nada, y es a propósito.

    Antes leía `User.areas` (un whitelist de áreas por usuario) y le pedía al modelo
    que respetara la restricción DENTRO del prompt. Los dos pilares de eso se fueron:
    `User.areas` lo borró la Etapa 1, y la regla nueva es que el permiso se resuelve
    en la consulta, no en el prompt — si el usuario no tiene acceso, el dato no llega
    (ver apps/workspaces/permissions.py). El reemplazo real son las Fuentes con su
    acceso privado/compartido/público.

    Se conserva la función, y no se borra su llamada, para no tocar el armado del
    prompt mientras el chat se rehace.
    """
    return ""


def _get_user_role_context(user):
    parts = []
    name = user.first_name or user.email.split('@')[0]
    if getattr(user, 'role', ''):
        parts.append(f"El usuario se llama {name} y su rol es {user.role}")
        if getattr(user, 'department', ''):
            parts.append(f"del área de {user.department}")
        parts.append(".")
    style_instructions = {
        'ejecutivo': "Responde de forma ejecutiva: bullet points, máximo 5 puntos clave, cifras al inicio. El usuario toma decisiones de alto nivel.",
        'analitico':  "Responde con análisis detallado: tendencias, comparativas, contexto y recomendaciones concretas.",
        'tecnico':    "Incluye terminología técnica, estructuras de datos y detalles de implementación cuando sea relevante.",
    }
    style = getattr(user, 'response_style', 'ejecutivo')
    if style in style_instructions:
        parts.append(style_instructions[style])
    if getattr(user, 'objectives', ''):
        parts.append(f"Sus objetivos con Afable: {user.objectives[:200]}")

    # Capa PERSONAL de "Mi contexto" (formulario que llena cada usuario)
    from apps.authentication.models import UserContext
    ctx = UserContext.objects.filter(user=user).first()
    if ctx and not ctx.is_empty():
        block = ["\nCONTEXTO PERSONAL DEL USUARIO (proporcionado por él mismo, tenlo siempre en cuenta):"]
        if ctx.about_me:
            block.append(f"- Sobre su trabajo: {ctx.about_me}")
        if ctx.priorities:
            block.append(f"- Sus prioridades actuales: {ctx.priorities}")
        if ctx.custom_instructions:
            block.append(f"- Cómo quiere que le respondas: {ctx.custom_instructions}")
        parts.append('\n'.join(block))

    return (' '.join(parts) + '\n\n') if parts else ''


def _get_org_context(org, allowed_doc_ids=None):
    """Contexto de EMPRESA (no del usuario): formulario + índice de documentos
    subidos. Se inyecta siempre, en todos los modos — es lo que no está en
    ninguna tabla conectada (mission, tono, glosario, políticas).

    `allowed_doc_ids` es el alcance del agente según sus Espacios: `None` es sin
    restricción, una lista limita a esos documentos, y una lista vacía deja el
    índice vacío a propósito (un agente encerrado en un Espacio sin documentos
    no tiene que ver los del resto de la empresa)."""
    from apps.organizations.models import OrganizationContext, CompanyDocument, ContextCubicle

    parts = []
    ctx = OrganizationContext.objects.filter(organization=org).first()
    if ctx and not ctx.is_empty():
        block = ["CONTEXTO DE LA EMPRESA (proporcionado por el usuario, tenlo siempre en cuenta):"]
        if ctx.business_description:
            block.append(f"- Qué hace la empresa: {ctx.business_description}")
        if ctx.products_services:
            block.append(f"- Productos/servicios: {ctx.products_services}")
        if ctx.target_customers:
            block.append(f"- Clientes objetivo: {ctx.target_customers}")
        if ctx.glossary:
            block.append(f"- Glosario de negocio (cómo le dicen a las cosas): {ctx.glossary}")
        if ctx.tone_guidelines:
            block.append(f"- Cómo debe hablar el agente: {ctx.tone_guidelines}")
        if ctx.restrictions:
            block.append(f"- RESTRICCIONES — el agente NUNCA debe: {ctx.restrictions}")
        parts.append('\n'.join(block))

    # Los documentos de la empresa: se entrega el TEXTO COMPLETO mientras quepa.
    #
    # Antes se mandaba solo `summary[:200]` de cada uno y el contenido llegaba unicamente
    # si el modelo decidia llamar `read_company_document(id)`. Con eso, una pregunta
    # directa sobre el contenido de un archivo ("¿que es X?") se respondia en generico:
    # el dato estaba cargado pero nunca entraba a la conversacion. Ademas
    # `.exclude(summary='')` dejaba INVISIBLE a todo documento sin resumen.
    #
    # Para una pyme el corpus entero suele caber, asi que la regla se da vuelta: primero
    # el texto integro, y solo cuando se acaba el presupuesto se cae al resumen mas la
    # tool. La busqueda semantica (pgvector) reemplaza este recorte cuando el corpus
    # crezca de verdad.
    PRESUPUESTO_DOCS = 60_000   # caracteres
    TOPE_POR_DOC = 20_000

    doc_qs = CompanyDocument.objects.filter(organization=org)
    if allowed_doc_ids is not None:
        doc_qs = doc_qs.filter(id__in=allowed_doc_ids)
    docs = list(
        doc_qs.order_by('-updated_at' if hasattr(CompanyDocument, 'updated_at') else '-id')
    )
    if docs:
        completos, indice, gastado = [], [], 0
        for d in docs:
            texto = (d.extracted_text or '').strip()
            if texto and gastado + min(len(texto), TOPE_POR_DOC) <= PRESUPUESTO_DOCS:
                recorte = texto[:TOPE_POR_DOC]
                gastado += len(recorte)
                completos.append(
                    f"### [id={d.id}] {d.title}\n{recorte}"
                    + ('\n[…documento recortado, usa read_company_document({}) para el resto]'.format(d.id)
                       if len(texto) > TOPE_POR_DOC else '')
                )
            else:
                resumen = (d.summary or '').strip() or 'sin resumen disponible'
                indice.append(f"- [id={d.id}] «{d.title}»: {resumen[:200]}")

        if completos:
            from django.utils import timezone as _tz
            sello = _tz.localtime().strftime('%d-%m-%Y %H:%M')
            parts.append(
                f'CONTENIDO DE LOS DOCUMENTOS DE LA EMPRESA (version vigente al {sello}). '
                'Responde usando esto como fuente principal y cita el documento por su titulo. '
                'Si el usuario dice que edito o actualizo un archivo, NO le pidas que te pegue el '
                'contenido: llama a la herramienta `actualizar_documentos` y lee la version nueva '
                'tu mismo. Si pregunta si EXISTE algo ("¿tengo un reporte de contabilidad?", "busca '
                'en mis archivos..."), usa `buscar_en_fuentes`: nunca respondas que no puedes ver '
                'sus archivos.\n\n' + '\n\n'.join(completos)
            )
        if indice:
            parts.append(
                'OTROS DOCUMENTOS DISPONIBLES (usa read_company_document(id) para leerlos '
                'completos):\n' + '\n'.join(indice)
            )
    else:
        parts.append(
            'La empresa todavia no tiene documentos ni archivos conectados. Si el usuario pregunta '
            'por alguno, usa `buscar_en_fuentes` para confirmarlo antes de responder.'
        )

    cubicles = list(ContextCubicle.objects.filter(organization=org))
    if cubicles:
        cub_block = ["CUBÍCULOS DE CONTEXTO (definidos libremente por el usuario, tenlos siempre en cuenta):"]
        for c in cubicles:
            cub_block.append(f"### {c.title}\n{c.content}")
        parts.append('\n'.join(cub_block))

    return ('\n\n'.join(parts) + '\n\n') if parts else ''


def _get_dummyjson_context(user):
    from apps.organizations.models import ActiveIntegration
    has = ActiveIntegration.objects.filter(user=user, integration_type='dummyjson', is_active=True).exists()
    if not has:
        return None
    try:
        from services.dummyjson_client import build_context_summary
        return build_context_summary()
    except Exception:
        return None


def _build_onboarding_context(user, agent=None, mention_system_id=None):
    from apps.organizations.models import IntegrationScan

    orgs = Organization.objects.filter(owner=user).exclude(name="Personal")
    has_org = orgs.exists()
    # En este contexto el usuario es dueño de la org (filter owner=user) → acceso total.
    perm_ctx = _get_permissions_context(user, is_owner=has_org)

    if not has_org:
        return {
            'mode': 'no_org',
            'system_prompt': f"""Eres Afable, un asistente empresarial inteligente.
{perm_ctx}
El usuario aún no ha configurado su empresa. Tu objetivo es guiarlo amigablemente:
1. Salúdalo y explica brevemente qué puede hacer Afable (analizar datos de ERP, CRM, generar reportes, etc.)
2. Pregúntale el nombre de su empresa para comenzar
3. Cuando el usuario te confirme el nombre de su empresa, incluye EXACTAMENTE esta línea al final de tu respuesta (reemplaza NOMBRE con el nombre real):
   __ACTION__{{\"type\":\"create_org\",\"name\":\"NOMBRE\"}}__

Sé conversacional, breve y entusiasta.

Acciones adicionales disponibles:
- Cargar datos demo: __ACTION__{{\"type\":\"load_demo\"}}__"""
        }

    org = orgs.first()
    scans = IntegrationScan.objects.filter(organization__owner=user)
    has_scan = scans.exists()

    role_ctx = _get_user_role_context(user)

    # El Espacio decide qué alcanza el agente. `None` en cualquiera de los dos es
    # "sin restricción": un agente que no está en ningún Espacio sigue viendo todo
    # lo de su empresa (ver `alcance_de_agente`).
    espacio_conns, espacio_docs = alcance_de_agente(agent)
    org_ctx = _get_org_context(org, allowed_doc_ids=espacio_docs)

    # Primero intenta SystemConnection (arquitectura nueva)
    from apps.organizations.models import SystemConnection
    from services.connector_registry import get_connections_context
    # google_drive no es un sistema "consultable en vivo" (no tiene run_sql/query_odoo) —
    # su contenido llega vía CompanyDocument (sync) y el tool read_company_document,
    # no por este modo. Si es la única conexión, no debe forzar 'connected_systems'.
    connections = SystemConnection.objects.filter(organization=org, is_active=True).exclude(connector_type='google_drive')
    # El Espacio recorta antes que cualquier otra cosa: lo que no está en el Espacio
    # del agente no existe para ese agente, ni siquiera para nombrarlo en el prompt.
    if espacio_conns is not None:
        connections = connections.filter(id__in=espacio_conns)
    if connections.exists():
        conn_ctx = get_connections_context(org, espacio_conns) or ''

        # Configuración del agente elegido (si trae instrucciones / scope de sistemas / modelo).
        agent_block = ''
        allowed_ids = None
        agent_model = None
        if agent is not None:
            if getattr(agent, 'model', ''):
                agent_model = agent.model
            sys_ids = list(agent.systems.values_list('id', flat=True)) if agent.pk else []
            if espacio_conns is not None:
                # Se intersecta, no se reemplaza: un sistema elegido a mano en la
                # ficha del agente no puede sacarlo del Espacio donde vive.
                sys_ids = [i for i in sys_ids if i in set(espacio_conns)]
            if sys_ids:
                allowed_ids = sys_ids
                allowed_names = ', '.join(
                    connections.filter(id__in=sys_ids).values_list('name', flat=True)
                )
                agent_block += f"\nSOLO puedes consultar estos sistemas: {allowed_names}. No consultes otros.\n"
            if getattr(agent, 'area', ''):
                agent_block += f"\nTu foco es el área de {AREA_NAMES.get(agent.area, agent.area)}.\n"
            if getattr(agent, 'instructions', ''):
                agent_block += f"\nInstrucciones del agente «{agent.name}»:\n{agent.instructions}\n"
            # Lo que la empresa le entrego al cargarlo (Admin > Agentes): sus datos,
            # sus reglas y lo que le conviene saber. Sin esto, la configuracion seria
            # un formulario que no cambia nada.
            config = getattr(agent, 'config', None)
            if config is not None:
                del_workspace = config.como_contexto()
                if del_workspace:
                    agent_block += f"\n{del_workspace}\n"
            # Las Habilidades van al final del bloque, despues de las instrucciones
            # propias: son transversales a la empresa y no tienen que tapar lo que
            # este agente en particular tiene que hacer.
            de_habilidades = habilidades_como_contexto(agent)
            if de_habilidades:
                agent_block += f"\n{de_habilidades}\n"

        # Sin sistemas elegidos a mano, el alcance sigue siendo el del Espacio: si
        # no viajara acá, las herramientas volverían a ver toda la empresa.
        if allowed_ids is None and espacio_conns is not None:
            allowed_ids = list(espacio_conns)

        # @mención en el mensaje: acota ESTE mensaje a un único sistema, por
        # encima del scope del agente (siempre que ese sistema exista y esté conectado).
        if mention_system_id is not None:
            # `connections` ya viene recortado por el Espacio, así que mencionar un
            # sistema de afuera simplemente no encuentra nada.
            mentioned = connections.filter(id=mention_system_id).first()
            if mentioned is not None:
                allowed_ids = [mentioned.id]
                agent_block += f"\nEl usuario mencionó explícitamente el sistema «{mentioned.name}» en este mensaje: consulta SOLO ese sistema.\n"

        return {
            'mode': 'connected_systems',
            'org': org,
            'allowed_ids': allowed_ids,
            'allowed_doc_ids': espacio_docs,
            'agent_model': agent_model,
            'system_prompt': f"""{role_ctx}Eres Afable, el asistente empresarial de {org.name}.
{perm_ctx}{agent_block}
{org_ctx}Tienes estos sistemas conectados (resumen de su esquema):

{conn_ctx}

IMPORTANTE — TIENES HERRAMIENTAS para consultar estos sistemas EN VIVO:
- list_systems: ver los sistemas conectados.
- list_tables / describe_table: explorar tablas/modelos y columnas cuando no conozcas el esquema
  (también funciona sobre sistemas Odoo: describe_table te da los campos reales del modelo).
- run_sql: ejecutar una consulta SELECT (solo lectura) sobre sistemas PostgreSQL/MSSQL.
- query_odoo: consultar registros reales (solo lectura) sobre sistemas Odoo, indicando el modelo
  (ej: res.partner, sale.order, account.move, product.template) y un dominio estilo Odoo
  (lista de [campo, operador, valor]).
- run_python: análisis avanzado con pandas/matplotlib (tendencias, proyecciones, correlaciones,
  gráficos). Declara los SELECT en `datasets` y escribe código sobre esos DataFrames; las figuras
  se muestran al usuario como imagen (incluye los marcadores [[FIGURA_n]] en tu respuesta).

Para CUALQUIER pregunta sobre datos del negocio (ventas, stock, clientes, facturas, etc.),
PRIMERO obtén el dato real: usa run_sql si el sistema es PostgreSQL/MSSQL, o query_odoo si el
sistema es Odoo. Explora con list_tables/describe_table si hace falta. NUNCA inventes un dato: si
una consulta no devuelve resultados o falla, dilo con claridad. NO escribas tú una línea de
fuente — el sistema la añade automáticamente con la tabla y la hora reales.
Responde siempre en español, conciso. Usa markdown para respuestas largas.{ACTIONS_PROMPT}""",
        }

    # Fallback: DummyJSON (demo)
    if not has_scan:
        dj_ctx = _get_dummyjson_context(user)
        if dj_ctx:
            return {
                'mode': 'dummyjson',
                'system_prompt': f"""{role_ctx}Eres Afable, el asistente empresarial de {org.name}.
{perm_ctx}
{org_ctx}Tienes acceso en tiempo real a los datos de la tienda conectada via DummyJSON.

{dj_ctx}

Usa estos datos para responder preguntas sobre ventas, inventario, clientes y métricas.
Responde siempre en español. Usa markdown para estructurar respuestas largas.{ACTIONS_PROMPT}""",
            }
        return {
            'mode': 'no_integration',
            'system_prompt': f"""{role_ctx}Eres Afable, el asistente empresarial de {org.name}.
{perm_ctx}
{org_ctx}La empresa está creada pero aún no hay sistemas conectados.
Si el usuario pide análisis o reportes:
1. Explícale que puede conectar su ERP o base de datos desde "Integraciones"
2. Menciona que soportamos Odoo, SAP Business One (MSSQL) y PostgreSQL
3. Ofrécele explorar con datos demo: "¿Quieres conectar datos demo para ver cómo funciona?"
4. Si acepta los datos demo: __ACTION__{{"type":"connect_integration","integration":"dummyjson"}}__

Responde siempre en español, sé conciso y orientado a la acción.{ACTIONS_PROMPT}"""
        }

    scan = scans.first()
    modules = ', '.join(scan.modules_found[:6]) if scan.modules_found else 'varios módulos'
    dj_ctx = _get_dummyjson_context(user)
    dj_section = f'\n\nADEMÁS tienes acceso a datos en tiempo real de DummyJSON Store:\n{dj_ctx}' if dj_ctx else ''
    ai_ctx = scan.ai_context[:800] if scan.ai_context else 'Sin contexto de escaneo.'
    return {
        'mode': 'full',
        'system_prompt': f"""{role_ctx}Eres Afable, el asistente empresarial de {org.name}.
{perm_ctx}
{org_ctx}Tienes acceso al contexto de datos escaneado de {scan.system_name}:
{ai_ctx}

Módulos disponibles: {modules}{dj_section}

Ayuda al usuario a analizar sus datos, generar reportes e insights empresariales.
Responde siempre en español. Usa markdown para estructurar respuestas largas.
Cuando generes un reporte o análisis formal, usa títulos markdown (#, ##).{ACTIONS_PROMPT}"""
    }


def _get_or_create_default(user):
    org, _ = Organization.objects.get_or_create(
        owner=user,
        name="Personal",
        defaults={"sector": "otro"},
    )
    agent, _ = Agent.objects.get_or_create(
        organization=org,
        name="Afable Assistant",
        defaults={"description": "Agente personal de Afable", "is_active": True},
    )
    return org, agent


def _resolve_agent(request, default_agent):
    """Agente a usar en esta conversación: el indicado por agent_id (validado) o el default."""
    agent_id = request.data.get('agent_id')
    if agent_id:
        org_ids = Organization.objects.filter(owner=request.user).values_list('id', flat=True)
        return get_object_or_404(Agent, pk=agent_id, organization_id__in=org_ids)
    return default_agent


# Una mención al agente: @ventas, @contratos. Se acepta en cualquier parte del
# mensaje, no sólo al principio, porque la gente escribe "consultale a @ventas".
PATRON_MENCION = re.compile(r'(?:^|\s)@([a-z0-9][a-z0-9-]{0,59})\b', re.IGNORECASE)


def _agentes_del_usuario(user):
    org_ids = Organization.objects.filter(owner=user).values_list('id', flat=True)
    return Agent.objects.filter(organization_id__in=org_ids, is_active=True)


def _agente_mencionado(user, texto):
    """El agente al que apunta la primera `@mención` del mensaje, o None.

    Una mención que no corresponde a ningún agente se ignora en silencio y se
    queda escrita en el mensaje: puede ser un correo, un handle de otra cosa, o
    sencillamente un error de tipeo, y cortar la conversación por eso sería peor
    que contestar con el agente que ya venía.
    """
    if not texto:
        return None
    handles = [m.group(1).lower() for m in PATRON_MENCION.finditer(texto)]
    if not handles:
        return None
    encontrados = {a.handle: a for a in _agentes_del_usuario(user).filter(handle__in=handles)}
    for handle in handles:
        if handle in encontrados:
            return encontrados[handle]
    return None


def _agente_de_conversacion(request, conversation):
    """
    Agente que responde en una conversación que ya existe.

    Por defecto es el que la conversación tiene asignado, pero si el usuario
    conmuta de agente en el selector del chat, el frontend manda `agent_id` y
    ese pasa a ser el agente del hilo de ahí en adelante. Antes el `agent_id`
    se ignoraba cuando había conversación, así que la única forma de cambiar de
    agente era abrir otro hilo.
    """
    # La mención manda sobre el selector: si el usuario escribió @ventas, quiere
    # que conteste Ventas aunque en la barra siga marcado otro agente.
    agent = (
        _agente_mencionado(request.user, request.data.get('message', ''))
        or _resolve_agent(request, conversation.agent)
    )
    if agent and agent != conversation.agent:
        conversation.agent = agent
        conversation.save(update_fields=['agent'])
    return agent


ACTIONS_PROMPT = """

---
ACCIONES DISPONIBLES EN LA PLATAFORMA:
Cuando el usuario pida crear, guardar o gestionar recursos, incluye EXACTAMENTE al final de tu respuesta (sin texto después):
__ACTION__{"type":"TIPO",...}__

Acciones y cuándo usarlas:
- Crear empresa: cuando pidan crear/agregar una empresa u organización
  → __ACTION__{"type":"create_org","name":"Nombre empresa"}__

- Crear agente: cuando pidan crear un agente, asistente o bot
  → __ACTION__{"type":"create_agent","name":"Nombre","description":"Para qué sirve"}__

- Guardar documento: cuando el usuario pida o confirme guardar un entregable
  → __ACTION__{"type":"save_document","title":"Título descriptivo","use_last_response":true}__
  use_last_response guarda tu respuesta anterior completa (incluidos sus gráficos) tal cual.
  Solo si el documento es contenido nuevo que no está en la conversación usa:
  → __ACTION__{"type":"save_document","title":"Título","content":"contenido completo en markdown"}__

- Navegar a sección: cuando el usuario quiera ir a una parte de la app
  → __ACTION__{"type":"navigate","path":"/app/documentos"}__
  Rutas válidas: /app, /app/agentes, /app/documentos, /app/integraciones, /app/tablero

- Cargar datos demo: cuando pidan datos de prueba o demo
  → __ACTION__{"type":"load_demo"}__

IMPORTANTE: Solo incluye __ACTION__ cuando el usuario PIDE EXPLÍCITAMENTE hacer algo. Para preguntas o análisis normales, responde sin acción.

REGLA DEL ENTREGABLE: cuando tu respuesta sea un entregable completo — cualquier contenido
que el usuario podría querer conservar: análisis con cifras o gráficos, reporte, informe,
plan, propuesta, comparativa, minuta, resumen ejecutivo, presupuesto, cronograma, tabla de
datos extensa, o cualquier documento redactado a pedido — termina SIEMPRE preguntando en
una línea aparte: "¿Quieres que guarde este [análisis/informe/plan/documento según
corresponda] como documento?" — SIN incluir la acción todavía.
Recién cuando el usuario acepte, responde con una confirmación breve e incluye la acción
save_document con use_last_response.
No apliques la regla a respuestas conversacionales, aclaraciones o respuestas cortas.
"""


def _find_action_json(text):
    """Ubica el JSON del marcador __ACTION__ con llaves balanceadas.
    Tolera que el modelo omita el `__` de cierre (gpt-oss lo hace a veces).
    Devuelve (dict, start, end) donde [start:end) cubre marcador + JSON + cierre opcional,
    o None si no hay acción parseable."""
    m = re.search(r'__ACTION__\s*(?={)', text)
    if not m:
        return None
    brace_start = m.end()
    try:
        data, consumed = json.JSONDecoder().raw_decode(text[brace_start:])
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    end = brace_start + consumed
    end += len(re.match(r'_{0,2}', text[end:]).group(0))
    return data, m.start(), end


def _extract_action(text):
    found = _find_action_json(text)
    return found[0] if found else None


def _strip_action(text):
    found = _find_action_json(text)
    if not found:
        return text.strip()
    _, start, end = found
    return (text[:start].rstrip() + text[end:]).strip()


def _execute_action(action_data, user, conversation=None):
    action_type = action_data.get('type')
    try:
        if action_type == 'create_org':
            org_name = action_data.get('name', 'Mi Empresa')
            org, created = Organization.objects.get_or_create(
                owner=user, name=org_name,
                defaults={'sector': 'otro'}
            )
            return {
                'type': 'create_org', 'success': True,
                'org_id': org.id, 'org_name': org.name,
                'created': created,
                'message': f'Empresa "{org.name}" {"creada" if created else "ya registrada"} ✓'
            }
        elif action_type == 'load_demo':
            from django.core.management import call_command
            call_command('seed_demo', user.email, verbosity=0)
            return {
                'type': 'load_demo', 'success': True,
                'message': 'Datos demo cargados ✓'
            }
        elif action_type == 'create_agent':
            org = Organization.objects.filter(owner=user).first()
            if not org:
                org, _ = Organization.objects.get_or_create(owner=user, name='Personal', defaults={'sector': 'otro'})
            name = action_data.get('name', 'Nuevo Agente')
            description = action_data.get('description', '')
            agent_obj, created = Agent.objects.get_or_create(
                organization=org, name=name,
                defaults={'description': description, 'is_active': True}
            )
            return {
                'type': 'create_agent', 'success': True,
                'agent_id': agent_obj.id, 'agent_name': agent_obj.name,
                'created': created,
                'message': f'Agente "{agent_obj.name}" {"creado" if created else "ya existe"} ✓'
            }
        elif action_type == 'save_document':
            title = action_data.get('title', 'Documento sin título')
            content = action_data.get('content', '')
            if action_data.get('use_last_response') and conversation is not None:
                # Guarda el entregable tal cual quedó en la conversación (con sus
                # gráficos embebidos) — el modelo no puede reproducir el base64.
                last = conversation.messages.filter(role='assistant').order_by('-created_at').first()
                if last:
                    # La oferta de guardado no es parte del entregable (puede no ser
                    # la última línea: a veces la sigue la cita de fuente).
                    offer = re.compile(r'^\s*¿.*guard.*\?\s*$', re.IGNORECASE)
                    lines = [ln for ln in last.content.rstrip().splitlines() if not offer.match(ln)]
                    content = re.sub(r'\n{3,}', '\n\n', '\n'.join(lines)).rstrip()
            doc_count = Document.objects.filter(user=user).count()
            doc = Document.objects.create(
                user=user, title=title, content=content,
                conversation=conversation,
                grid_x=0, grid_y=doc_count * 6, grid_w=8, grid_h=6,
            )
            return {
                'type': 'save_document', 'success': True,
                'document_id': doc.id, 'document_title': doc.title,
                'message': f'Documento "{doc.title}" guardado ✓'
            }
        elif action_type == 'navigate':
            return {
                'type': 'navigate', 'success': True,
                'path': action_data.get('path', '/app'),
                'message': f'Navegando...'
            }
        elif action_type == 'connect_integration':
            from apps.organizations.models import ActiveIntegration
            integration = action_data.get('integration', 'dummyjson')
            obj, created = ActiveIntegration.objects.get_or_create(
                user=user, integration_type=integration,
                defaults={'is_active': True},
            )
            if not created:
                obj.is_active = True
                obj.save(update_fields=['is_active'])
            return {
                'type': 'connect_integration', 'success': True,
                'integration': integration,
                'message': f'Integración {integration} conectada ✓',
            }
    except Exception as e:
        return {'type': action_type, 'success': False, 'message': str(e)}
    return None


class DirectChatView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        message = request.data.get('message', '').strip()
        conversation_id = request.data.get('conversation_id')

        if not message:
            return Response({'detail': 'El campo message es requerido.'}, status=status.HTTP_400_BAD_REQUEST)

        _, default_agent = _get_or_create_default(request.user)

        if conversation_id:
            conversation = get_object_or_404(Conversation, pk=conversation_id, user=request.user)
            agent = _agente_de_conversacion(request, conversation)
        else:
            agent = (
                _agente_mencionado(request.user, message)
                or _resolve_agent(request, default_agent)
            )
            conversation = Conversation.objects.create(
                agent=agent, user=request.user, title=_conversation_title(agent, message))

        mention_system_id = request.data.get('system_id') or None
        context = _build_onboarding_context(request.user, agent, mention_system_id)
        system_prompt = context['system_prompt']

        Message.objects.create(conversation=conversation, role='user', content=message)
        full_history = list(conversation.messages.values('role', 'content').order_by('created_at'))

        model = (request.data.get('model') or '').strip() or context.get('agent_model')
        _, resolved_model = resolve_model(model)

        if context.get('mode') == 'connected_systems':
            from services.agent_service import run_agent_live
            response_text = run_agent_live(
                full_history, context['org'], system_prompt, model,
                context.get('allowed_ids'), context.get('allowed_doc_ids'),
            )
        else:
            response_text = chat_direct(full_history, system_prompt, model)

        clean_response = _strip_action(response_text)
        Message.objects.create(
            conversation=conversation, role='assistant', content=clean_response,
            agent=agent, model_used=resolved_model,
        )
        conversation.save()

        return Response({'conversation_id': conversation.id, 'message': clean_response, 'model': resolved_model})


class ChatAttachmentView(APIView):
    """Extrae texto de un archivo adjuntado al vuelo en el chat (no se guarda como
    Document de Contexto — es efímero, solo vive dentro del mensaje que lo adjunta)."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from services.document_processing import process_document

        f = request.FILES.get('file')
        if not f:
            return Response({'detail': 'El campo file es requerido.'}, status=status.HTTP_400_BAD_REQUEST)

        result = process_document(f, f.content_type or '')
        return Response({
            'filename': f.name,
            'extracted_text': result['extracted_text'],
            'summary': result['summary'],
            'error': result['error'],
        })


class DirectChatStreamView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        message = request.data.get('message', '').strip()
        conversation_id = request.data.get('conversation_id')

        if not message:
            return Response({'detail': 'El campo message es requerido.'}, status=status.HTTP_400_BAD_REQUEST)

        _, default_agent = _get_or_create_default(request.user)

        if conversation_id:
            conversation = get_object_or_404(Conversation, pk=conversation_id, user=request.user)
            agent = _agente_de_conversacion(request, conversation)
        else:
            agent = (
                _agente_mencionado(request.user, message)
                or _resolve_agent(request, default_agent)
            )
            conversation = Conversation.objects.create(
                agent=agent, user=request.user, title=_conversation_title(agent, message))

        mention_system_id = request.data.get('system_id') or None
        context = _build_onboarding_context(request.user, agent, mention_system_id)
        system_prompt = context['system_prompt']

        Message.objects.create(conversation=conversation, role='user', content=message)
        full_history = list(conversation.messages.values('role', 'content').order_by('created_at'))

        conv_id = conversation.id
        agent_id = agent.id if agent else None
        user = request.user
        mode = context.get('mode')
        org = context.get('org')
        model = (request.data.get('model') or '').strip() or context.get('agent_model')
        _, resolved_model = resolve_model(model)
        allowed_ids = context.get('allowed_ids')
        allowed_doc_ids = context.get('allowed_doc_ids')
        # Quien va a contestar viaja en el primer evento: si la mencion cambio el
        # agente, la pantalla tiene que enterarse antes de que empiece el texto.
        agente_payload = (
            {'id': agent.id, 'name': agent.name, 'handle': agent.handle} if agent else None
        )

        def event_stream():
            accumulated = []
            yield f"data: {json.dumps({'conversation_id': conv_id, 'model': resolved_model, 'agent': agente_payload})}\n\n"

            if mode == 'connected_systems':
                # Agente con datos en vivo: emite estados de progreso por cada herramienta
                # mientras consulta los sistemas, y al final el texto en trozos (efecto typing).
                from services.agent_service import run_agent_live_events
                full_text = ''
                for event in run_agent_live_events(
                    full_history, org, system_prompt, model, allowed_ids, allowed_doc_ids,
                ):
                    if 'status' in event:
                        yield f"data: {json.dumps({'status': event['status']})}\n\n"
                    elif 'final' in event:
                        full_text = event['final']
                accumulated.append(full_text)
                clean_stream = _strip_action(full_text)
                for piece in _chunk_text(clean_stream):
                    yield f"data: {json.dumps({'chunk': piece})}\n\n"
            else:
                for chunk in stream_direct(full_history, system_prompt, model):
                    accumulated.append(chunk)
                    # Don't stream the action marker to the client
                    if '__ACTION__' not in chunk:
                        yield f"data: {json.dumps({'chunk': chunk})}\n\n"

            full_response = ''.join(accumulated)

            # Detect and execute action
            action_data = _extract_action(full_response)
            action_result = None
            if action_data:
                try:
                    action_result = _execute_action(action_data, user, conversation)
                except Exception:
                    pass

            # Clean response before saving
            clean_response = _strip_action(full_response)
            if not clean_response and action_result:
                # El modelo a veces responde SOLO con la acción; que el historial
                # no quede con un mensaje vacío.
                clean_response = action_result.get('message', '')
            Message.objects.create(
                conversation_id=conv_id, role='assistant', content=clean_response,
                agent_id=agent_id, model_used=resolved_model,
            )
            Conversation.objects.filter(pk=conv_id).update()

            done_payload = {'done': True, 'model': resolved_model}

            if action_result:
                done_payload['action'] = action_result

            yield f"data: {json.dumps(done_payload)}\n\n"

        response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response


class AvailableModelsView(APIView):
    """Modelos de IA disponibles para el selector de la app: los locales de Ollama
    (/api/tags) + los cloud configurados, marcando el default activo."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.conf import settings
        import requests

        provider = getattr(settings, 'AI_PROVIDER', 'ollama')
        default_model = (getattr(settings, 'OLLAMA_CLOUD_MODEL', '')
                         if provider == 'ollama_cloud'
                         else getattr(settings, 'OLLAMA_MODEL', ''))
        models, seen = [], set()

        def add(name, kind):
            if name and name not in seen:
                seen.add(name)
                models.append({'id': name, 'label': name, 'kind': kind,
                               'default': name == default_model})

        # Locales (Ollama corriendo)
        try:
            base = getattr(settings, 'OLLAMA_BASE_URL', 'http://localhost:11434')
            r = requests.get(f'{base}/api/tags', timeout=4)
            for m in r.json().get('models', []):
                nm = m.get('name', '')
                add(nm, 'cloud' if nm.endswith('-cloud') else 'local')
        except Exception:
            pass

        # Cloud configurados (aunque no estén en /api/tags)
        for nm in getattr(settings, 'OLLAMA_CLOUD_MODELS', []):
            add(nm, 'cloud')
        add(getattr(settings, 'OLLAMA_CLOUD_MODEL', ''), 'cloud')

        # Asegura que el default esté presente
        add(default_model, 'cloud' if provider == 'ollama_cloud' else 'local')

        # Anthropic y DeepSeek — solo aparecen en el selector si hay API key configurada.
        if getattr(settings, 'ANTHROPIC_API_KEY', ''):
            add('claude-opus-4-8', 'anthropic')
            add('claude-sonnet-5', 'anthropic')
        if getattr(settings, 'DEEPSEEK_API_KEY', ''):
            add(getattr(settings, 'DEEPSEEK_MODEL', 'deepseek-v4-flash'), 'deepseek')

        return Response({'models': models, 'default': default_model})


class AgentListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_ids = Organization.objects.filter(owner=request.user).values_list('id', flat=True)
        agents = Agent.objects.filter(organization_id__in=org_ids, is_active=True)
        return Response(AgentSerializer(agents, many=True).data)

    def post(self, request):
        serializer = AgentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        org = get_object_or_404(Organization, pk=serializer.validated_data['organization'].pk, owner=request.user)
        serializer.save(organization=org)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AgentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_agent(self, pk, user):
        org_ids = Organization.objects.filter(owner=user).values_list('id', flat=True)
        return get_object_or_404(Agent, pk=pk, organization_id__in=org_ids)

    def get(self, request, pk):
        agent = self._get_agent(pk, request.user)
        return Response(AgentSerializer(agent).data)

    def put(self, request, pk):
        agent = self._get_agent(pk, request.user)
        serializer = AgentSerializer(agent, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        agent = self._get_agent(pk, request.user)
        agent.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AgentTemplateListView(APIView):
    """Galería 'Explorar' — pública (sirve a la app y al landing).

    `?featured=1` devuelve solo las destacadas (para la vitrina del landing).
    """
    permission_classes = [AllowAny]

    def get(self, request):
        qs = AgentTemplate.objects.filter(is_active=True)
        if request.query_params.get('featured') in ('1', 'true'):
            qs = qs.filter(is_featured=True)
        kind = request.query_params.get('kind')
        if kind in dict(AgentTemplate.KINDS):
            qs = qs.filter(kind=kind)
        return Response(AgentTemplateSerializer(qs, many=True).data)


class AgentTemplateUseView(APIView):
    """Obtiene (o crea la primera vez) el Agent real de la org para esta plantilla.

    Idempotente por (organization, name): los agentes "siempre disponibles"
    (kind='role', ver seed_role_agents) no se "agregan" — se resuelven solos
    la primera vez que el usuario presiona "Chat" en su tarjeta, y las
    llamadas siguientes reusan el mismo Agent (mismo historial de chat).
    Copia la receta (nombre/descr/instrucciones/área/modelo) pero NO los
    sistemas: el usuario re-mapea sus propias conexiones después.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        template = get_object_or_404(AgentTemplate, pk=pk, is_active=True)
        org = Organization.objects.filter(owner=request.user).order_by('id').first()
        if org is None:
            return Response({'detail': 'No tienes una organización.'},
                            status=status.HTTP_400_BAD_REQUEST)
        agent, created = Agent.objects.get_or_create(
            organization=org,
            name=template.name,
            defaults={
                'description': template.description,
                'instructions': template.instructions,
                'area': template.area,
                'model': template.model,
                'tools_summary': template.tools_summary,
                'recommended_frequency': template.recommended_frequency,
            },
        )
        if created:
            AgentTemplate.objects.filter(pk=template.pk).update(uses_count=template.uses_count + 1)
            # Cargar un agente al Workspace abre su configuracion en Admin: nace
            # pendiente de que la empresa le diga con que datos y reglas trabaja.
            AgentConfig.objects.get_or_create(agent=agent)
        return Response(AgentSerializer(agent).data,
                         status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class ChatView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        org_ids = Organization.objects.filter(owner=request.user).values_list('id', flat=True)
        agent = get_object_or_404(Agent, pk=pk, organization_id__in=org_ids, is_active=True)
        org = agent.organization

        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_message = serializer.validated_data['message']
        conversation_id = serializer.validated_data.get('conversation_id')

        if conversation_id:
            conversation = get_object_or_404(Conversation, pk=conversation_id, agent=agent, user=request.user)
        else:
            conversation = Conversation.objects.create(agent=agent, user=request.user, title=user_message[:120])

        Message.objects.create(conversation=conversation, role='user', content=user_message)
        history = list(conversation.messages.values('role', 'content').order_by('created_at'))

        if not org.odoo_connected:
            return Response({'detail': 'La organización no tiene Odoo conectado.'}, status=status.HTTP_400_BAD_REQUEST)

        from services.agent_service import run_agent
        response_text = run_agent(history, org)

        Message.objects.create(conversation=conversation, role='assistant', content=response_text)
        conversation.save()

        return Response({'conversation_id': conversation.id, 'message': response_text})


class ConversationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        org_ids = Organization.objects.filter(owner=request.user).values_list('id', flat=True)
        agent = get_object_or_404(Agent, pk=pk, organization_id__in=org_ids)
        convs = Conversation.objects.filter(agent=agent, user=request.user)
        return Response(ConversationListSerializer(convs, many=True).data)


class ConversationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, conv_id):
        org_ids = Organization.objects.filter(owner=request.user).values_list('id', flat=True)
        agent = get_object_or_404(Agent, pk=pk, organization_id__in=org_ids)
        conv = get_object_or_404(Conversation, pk=conv_id, agent=agent, user=request.user)
        return Response(ConversationSerializer(conv).data)

    def delete(self, request, pk, conv_id):
        org_ids = Organization.objects.filter(owner=request.user).values_list('id', flat=True)
        agent = get_object_or_404(Agent, pk=pk, organization_id__in=org_ids)
        conv = get_object_or_404(Conversation, pk=conv_id, agent=agent, user=request.user)
        conv.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserConversationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        convs = Conversation.objects.filter(user=request.user).select_related('agent').order_by('-updated_at')
        return Response(ConversationListSerializer(convs, many=True).data)


class UserConversationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, conv_id):
        conv = get_object_or_404(Conversation, pk=conv_id, user=request.user)
        return Response(ConversationSerializer(conv).data)

    def delete(self, request, conv_id):
        conv = get_object_or_404(Conversation, pk=conv_id, user=request.user)
        conv.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DocumentListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        docs = Document.objects.filter(user=request.user)
        return Response(DocumentSerializer(docs, many=True).data)

    def post(self, request):
        serializer = DocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class DocumentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        doc = get_object_or_404(Document, pk=pk, user=request.user)
        return Response(DocumentSerializer(doc).data)

    def patch(self, request, pk):
        doc = get_object_or_404(Document, pk=pk, user=request.user)
        serializer = DocumentSerializer(doc, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        doc = get_object_or_404(Document, pk=pk, user=request.user)
        doc.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Automatizaciones y Rutinas ────────────────────────────────────────────────

class OrgRequiredError(Exception):
    """No hay una empresa real (no "Personal") disponible para la operación."""


def _user_org(user, org_id=None):
    """Organización sobre la que corre la automatización/rutina del usuario.

    Excluye "Personal" a propósito (mismo criterio que agentes/dashboard/modelo:
    las automatizaciones necesitan una empresa real). Levanta OrgRequiredError
    en vez de un 404 crudo para que la vista pueda devolver un mensaje claro.
    """
    qs = Organization.objects.filter(owner=user).exclude(name='Personal')
    if org_id:
        org = qs.filter(pk=org_id).first()
    else:
        org = qs.first()
    if org is None:
        raise OrgRequiredError()
    return org


class AutomationListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        autos = Automation.objects.filter(user=request.user)
        return Response(AutomationSerializer(autos, many=True).data)

    def post(self, request):
        serializer = AutomationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            org = _user_org(request.user, request.data.get('organization'))
        except OrgRequiredError:
            return Response(
                {'organization': ['Las automatizaciones no están disponibles en "Personal" — selecciona o crea una empresa real arriba.']},
                status=status.HTTP_400_BAD_REQUEST)
        conn = serializer.validated_data.get('connection')
        if conn and conn.organization_id != org.id:
            return Response({'connection': ['La conexión no pertenece a tu empresa.']},
                            status=status.HTTP_400_BAD_REQUEST)
        serializer.save(user=request.user, organization=org)

        from django.conf import settings
        from django.core.mail import send_mail
        auto = serializer.instance
        send_mail(
            subject=f'[Afable] Nueva automatización creada — {request.user.email}',
            message=(
                f'Usuario: {request.user.email}\n'
                f'Empresa: {org.name}\n'
                f'Nombre: {auto.name}\n'
                f'Disparador: {auto.get_trigger_type_display()}\n'
                + (f'Evento: {auto.get_event_type_display()}\n' if auto.trigger_type == 'event' else '')
                + f'Prompt: {auto.prompt or "(vacío)"}'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.AFABLE_TEAM_EMAIL],
            fail_silently=True,
        )

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AutomationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        auto = get_object_or_404(Automation, pk=pk, user=request.user)
        serializer = AutomationSerializer(auto, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        conn = serializer.validated_data.get('connection')
        if conn and conn.organization_id != auto.organization_id:
            return Response({'connection': ['La conexión no pertenece a tu empresa.']},
                            status=status.HTTP_400_BAD_REQUEST)
        # Si cambia lo vigilado, el snapshot anterior deja de tener sentido.
        watched_changed = any(
            f in serializer.validated_data and serializer.validated_data[f] != getattr(auto, f)
            for f in ('connection', 'event_type', 'event_config')
        )
        serializer.save(**({'event_state': {}} if watched_changed else {}))
        return Response(serializer.data)

    def delete(self, request, pk):
        auto = get_object_or_404(Automation, pk=pk, user=request.user)
        auto.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AutomationRunNowView(APIView):
    """Ejecuta la automatización de inmediato (para probar sin esperar el intervalo)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        auto = get_object_or_404(Automation, pk=pk, user=request.user)
        from services.automation_runner import execute_automation
        out = execute_automation(auto)
        data = AutomationSerializer(auto).data
        data['run_ok'] = out['ok']
        data['fired'] = out.get('fired')  # None en programadas; True/False en eventos
        return Response(data)


class RoutineListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        routines = Routine.objects.filter(user=request.user)
        return Response(RoutineSerializer(routines, many=True).data)

    def post(self, request):
        serializer = RoutineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            org = _user_org(request.user, request.data.get('organization'))
        except OrgRequiredError:
            return Response(
                {'organization': ['Las rutinas no están disponibles en "Personal" — selecciona o crea una empresa real arriba.']},
                status=status.HTTP_400_BAD_REQUEST)
        serializer.save(user=request.user, organization=org)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class RoutineDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        routine = get_object_or_404(Routine, pk=pk, user=request.user)
        serializer = RoutineSerializer(routine, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        routine = get_object_or_404(Routine, pk=pk, user=request.user)
        routine.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RoutineRunNowView(APIView):
    """Ejecuta la rutina completa de inmediato, paso a paso."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        routine = get_object_or_404(Routine, pk=pk, user=request.user)
        from services.automation_runner import execute_routine
        out = execute_routine(routine)
        data = RoutineSerializer(routine).data
        data['run_ok'] = out['ok']
        return Response(data)


# ---------------------------------------------------------------------------
# Habilidades
# ---------------------------------------------------------------------------


class SkillListCreateView(APIView):
    """Admin › Agentes › Habilidades: la lista y crear una nueva."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        org = _user_org(request.user, request.query_params.get('organization'))
        habilidades = Skill.objects.filter(organization=org).prefetch_related('agents')
        return Response(SkillSerializer(habilidades, many=True).data)

    def post(self, request):
        org = _user_org(request.user, request.data.get('organization'))
        serializer = SkillWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        habilidad = serializer.save(organization=org, created_by=request.user)
        self._enganchar(habilidad, request.data.get('agent_ids'), org)
        return Response(SkillSerializer(habilidad).data, status=status.HTTP_201_CREATED)

    def _enganchar(self, habilidad, agent_ids, org):
        """Los agentes que la usan. Sólo los de esta empresa: una Habilidad no
        cruza de organización, y mandar un id ajeno no engancha nada."""
        if agent_ids is None:
            return
        habilidad.agents.set(Agent.objects.filter(organization=org, pk__in=agent_ids))


class SkillDetailView(SkillListCreateView):
    """Editar, reasignar o borrar una Habilidad."""

    def _get(self, request, pk):
        org = _user_org(request.user, request.data.get('organization')
                        or request.query_params.get('organization'))
        habilidad = Skill.objects.filter(organization=org, pk=pk).first()
        if habilidad is None:
            raise NotFound('Habilidad no encontrada.')
        return org, habilidad

    def get(self, request, pk):
        _, habilidad = self._get(request, pk)
        return Response(SkillSerializer(habilidad).data)

    def patch(self, request, pk):
        org, habilidad = self._get(request, pk)
        serializer = SkillWriteSerializer(habilidad, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        self._enganchar(habilidad, request.data.get('agent_ids'), org)
        return Response(SkillSerializer(habilidad).data)

    def delete(self, request, pk):
        _, habilidad = self._get(request, pk)
        habilidad.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

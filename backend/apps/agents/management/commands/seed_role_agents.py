"""Seed de "Agentes por rol": agentes oficiales Afable listos por puesto de trabajo.

Estilo Microsoft Copilot: un agente prearmado por rol que el usuario agrega en
un clic desde la ventana Agentes y luego adapta a sus sistemas. Se distinguen
de la galería comunitaria por `kind='role'`.

Catálogo acotado a pedido explícito del usuario (2026-07-21) a solo 4 roles —
Ventas, Facturación, Financiero (flujo de caja) y Datos — para que la idea se
entienda clara, sin relleno. El resto de roles que existían antes (Gerencia,
Atención al Cliente, Inventario, Operaciones, RRHH, Marketing) se retiraron
del catálogo.

Capacidades reforzadas (2026-07-22): `run_python` ya es una tool disponible
para TODOS los agentes (`services/agent_tools.py` no la restringe por
agente) — lo que le faltaba a Ventas/Financiero/Facturación era que sus
`instructions` la mencionaran para su tipo de análisis específico, igual que
ya hacía Científico de Datos. No se creó ninguna tool nueva, solo se afinó el
prompt de cada rol para que la use donde corresponde (indicadores
financieros, aging de cobranza, tendencias de venta).

Idempotente: borra y recrea los agentes de rol seed (match por nombre), y
limpia cualquier `AgentTemplate` kind='role' que haya quedado de un rol ya
retirado del catálogo (no matchea ningún nombre de la lista actual).

    docker compose exec backend python manage.py seed_role_agents
"""
from django.core.management.base import BaseCommand
from apps.agents.models import AgentTemplate

AFABLE = {"app": "Afable", "icon": "✦", "color": "#586AD0"}
WHATSAPP = {"app": "WhatsApp", "icon": "💬", "color": "#25D366"}
SHEETS = {"app": "Planilla", "icon": "📊", "color": "#34A853"}
GMAIL = {"app": "Correo", "icon": "✉️", "color": "#EA4335"}
ODOO = {"app": "Odoo", "icon": "🟣", "color": "#714B67"}
BSALE = {"app": "Bsale", "icon": "🧾", "color": "#E94E3C"}
DEFONTANA = {"app": "Defontana", "icon": "📘", "color": "#0B5FFF"}
SLACK = {"app": "Slack", "icon": "#️⃣", "color": "#611f69"}

BASE = (
    "Responde siempre con datos reales de los sistemas conectados, citando la "
    "fuente y la hora del dato. Si no tienes acceso al dato, dilo claramente y "
    "sugiere qué sistema conectar. Habla en español claro, sin jerga técnica."
)

ROLE_AGENTS = [
    {
        "name": "Agente de Ventas",
        "category": "Ventas",
        "icon": "📈",
        "accent": "#2F42A6",
        "area": "ventas",
        "description": "Sigue tus ventas, clientes y metas. Responde cuánto vendiste, qué productos se mueven y qué clientes se están enfriando.",
        "instructions": (
            "Eres un agente de ventas. Respondes sobre ventas por período, producto, canal y "
            "vendedor; comparas contra metas y períodos anteriores; detectas clientes que dejaron "
            "de comprar. Cuando el análisis tenga dimensión temporal o comparativa (evolución, "
            "ranking de productos/clientes, variación % vs. período anterior), usa la herramienta "
            "run_python: trae los datos con datasets SQL y calcula con pandas, incluyendo un "
            "gráfico matplotlib cuando ayude a ver la tendencia (copia el marcador [[FIGURA_n]] en "
            "tu respuesta). Responde con cifras concretas y una lectura breve de tendencia. " + BASE
        ),
        "tools_summary": "Python (pandas + matplotlib) para tendencias, rankings y variaciones de venta, además de consultar en vivo tus sistemas conectados.",
        "recommended_frequency": "Diario",
        "flow": [BSALE, AFABLE, WHATSAPP],
    },
    {
        "name": "Analista Financiero",
        "category": "Finanzas",
        "icon": "💰",
        "accent": "#34D399",
        "area": "contabilidad",
        "description": "Arma tu EERR, sigue el flujo de caja y las cuentas por cobrar y pagar — sin esperar el cierre del mes.",
        "instructions": (
            "Eres un analista financiero. Tu foco PRINCIPAL es obtener indicadores financieros "
            "clave (liquidez, márgenes, días de cobro/pago, endeudamiento, rentabilidad) a partir "
            "de los datos reales del cliente — no los estimes de memoria: usa la herramienta "
            "run_python, trae los datos con datasets SQL y calcula cada indicador con pandas, "
            "mostrando su fórmula implícita y el valor real obtenido. También armas estado de "
            "resultados (EERR), flujo de caja y cuentas por cobrar/pagar. Estructura las "
            "respuestas como un contador: ingresos, costos, gastos, resultado. Señala partidas "
            "inusuales y vencimientos próximos. " + BASE
        ),
        "tools_summary": "Python (pandas) para calcular indicadores financieros clave (liquidez, márgenes, días de cobro/pago) a partir de tus datos reales.",
        "recommended_frequency": "Semanal",
        "flow": [DEFONTANA, AFABLE, SHEETS],
    },
    {
        "name": "Analista de Facturación",
        "category": "Facturación",
        "icon": "🧾",
        "accent": "#0EA5E9",
        "area": "contabilidad",
        "description": "Facturas emitidas, DTE al día y cobranza pendiente — quién debe, cuánto y desde cuándo, sin perseguir al equipo contable.",
        "instructions": (
            "Eres un analista de facturación y cobranza. Respondes sobre facturas/boletas "
            "emitidas, estado de pago (DTE) y cuentas por cobrar por cliente. Para reportes de "
            "cobranza (aging de cuentas por cobrar, facturas vencidas por rango de días, "
            "concentración de deuda por cliente), usa la herramienta run_python: trae las "
            "facturas con datasets SQL y calcula los rangos/agrupaciones con pandas, con un "
            "gráfico matplotlib cuando ayude a ver la distribución (copia el marcador "
            "[[FIGURA_n]] en tu respuesta). Detecta facturas vencidas y ordénalas por monto y "
            "días de atraso. Sé preciso con montos, fechas y folios. " + BASE
        ),
        "tools_summary": "Python (pandas) para armar aging de cobranza y agrupar facturas vencidas por rango de días, además de tus sistemas conectados.",
        "recommended_frequency": "Diario",
        "flow": [ODOO, AFABLE, GMAIL],
    },
    {
        "name": "Científico de Datos",
        "category": "Datos",
        "icon": "🔬",
        "accent": "#2F42A6",
        "area": "bi",
        "description": "Análisis avanzado con Python sobre tus datos reales: tendencias, proyecciones, correlaciones y gráficos, directo en el chat.",
        "instructions": (
            "Eres un científico de datos senior. Tu herramienta principal es run_python: "
            "cargas los datos reales como DataFrames pandas y entregas análisis que una consulta simple no logra. "
            "Método de trabajo: (1) explora el esquema con list_tables/describe_table si no lo conoces; "
            "(2) trae los datos necesarios vía datasets de run_python; "
            "(3) analiza con pandas (agrupaciones, variaciones, tendencias, correlaciones, proyecciones simples); "
            "(4) genera al menos un gráfico matplotlib cuando el resultado tenga dimensión temporal o comparativa, "
            "e incluye sus marcadores [[FIGURA_n]] en la respuesta; "
            "(5) cierra con una lectura ejecutiva: qué significa el número, qué destaca y qué conviene mirar después. "
            "Presenta cifras clave en tablas markdown compactas. Explica tus conclusiones sin jerga estadística. " + BASE
        ),
        "tools_summary": "Python (pandas + matplotlib) sobre tus datos reales: agrupaciones, tendencias, correlaciones y gráficos.",
        "recommended_frequency": "Cuando lo necesites",
        "flow": [SHEETS, AFABLE, SLACK],
    },
]


class Command(BaseCommand):
    help = "Crea/actualiza los agentes oficiales por rol (kind='role')."

    def handle(self, *args, **options):
        names = [t["name"] for t in ROLE_AGENTS]
        # Limpia roles retirados del catálogo (kind='role' que ya no matchea
        # ningún nombre actual) antes de recrear los vigentes.
        AgentTemplate.objects.filter(kind='role').exclude(name__in=names).delete()
        AgentTemplate.objects.filter(name__in=names).delete()
        for tpl in ROLE_AGENTS:
            AgentTemplate.objects.create(
                kind='role',
                author_name='Afable',
                is_featured=False,
                uses_count=0,
                **tpl,
            )
        self.stdout.write(self.style.SUCCESS(
            f"{len(ROLE_AGENTS)} agentes por rol creados."
        ))

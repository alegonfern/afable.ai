"""Seed de la galería 'Explorar': plantillas de agentes/automatizaciones de la comunidad.

Idempotente: borra y recrea las plantillas seed (match por nombre).
Cada plantilla incluye `flow` = apps involucradas, que el front renderiza como
una imagen de proceso (iconos conectados).

    docker compose exec backend python manage.py seed_agent_templates
"""
from django.core.management.base import BaseCommand
from apps.agents.models import AgentTemplate

# Paletas de apps reutilizables para los flujos
SHOPIFY = {"app": "Shopify", "icon": "🛍️", "color": "#96BF48"}
WHATSAPP = {"app": "WhatsApp", "icon": "💬", "color": "#25D366"}
AFABLE = {"app": "Afable", "icon": "✦", "color": "#586AD0"}
ODOO = {"app": "Odoo", "icon": "🟣", "color": "#714B67"}
SAP = {"app": "SAP", "icon": "🔷", "color": "#0FAAFF"}
SHEETS = {"app": "Planilla", "icon": "📊", "color": "#34A853"}
GMAIL = {"app": "Correo", "icon": "✉️", "color": "#EA4335"}
SLACK = {"app": "Slack", "icon": "#️⃣", "color": "#611f69"}
HUBSPOT = {"app": "HubSpot", "icon": "🧲", "color": "#FF7A59"}
MSSQL = {"app": "SQL Server", "icon": "🗄️", "color": "#A91D22"}

# Sistemas y servicios usados en Chile
SII = {"app": "SII", "icon": "🏛️", "color": "#1F4E79"}
BSALE = {"app": "Bsale", "icon": "🧾", "color": "#E94E3C"}
DEFONTANA = {"app": "Defontana", "icon": "📘", "color": "#0B5FFF"}
NUBOX = {"app": "Nubox", "icon": "🟦", "color": "#0066CC"}
SOFTLAND = {"app": "Softland", "icon": "🟧", "color": "#F37021"}
LAUDUS = {"app": "Laudus", "icon": "📗", "color": "#2E7D32"}
WEBPAY = {"app": "Webpay", "icon": "💳", "color": "#E2231A"}
KHIPU = {"app": "Khipu", "icon": "⚡", "color": "#06B6D4"}
FLOW = {"app": "Flow", "icon": "💸", "color": "#2D9CDB"}
MERCADOPAGO = {"app": "Mercado Pago", "icon": "🔵", "color": "#00B1EA"}
CHILEXPRESS = {"app": "Chilexpress", "icon": "📦", "color": "#E30613"}
STARKEN = {"app": "Starken", "icon": "🚚", "color": "#F7941E"}
BLUEX = {"app": "Blue Express", "icon": "🔷", "color": "#003DA5"}
TALANA = {"app": "Talana", "icon": "👥", "color": "#7B61FF"}
BUK = {"app": "Buk", "icon": "🧑‍💼", "color": "#FF4D4D"}
PREVIRED = {"app": "Previred", "icon": "🏦", "color": "#1B5E20"}
JUMPSELLER = {"app": "Jumpseller", "icon": "🛒", "color": "#22B573"}
RINDEGASTOS = {"app": "Rindegastos", "icon": "🧮", "color": "#00A8A8"}
BANCOESTADO = {"app": "BancoEstado", "icon": "🏛️", "color": "#FF6600"}
TOTEAT = {"app": "Toteat", "icon": "🍽️", "color": "#FF6B35"}
INDICADORES = {"app": "Indicadores", "icon": "📊", "color": "#16A34A"}

TEMPLATES = [
    {
        "name": "Alerta de quiebre de stock",
        "category": "Inventario",
        "icon": "📦",
        "accent": "#34D399",
        "author_name": "Equipo Afable",
        "uses_count": 412,
        "is_featured": True,
        "area": "inventario",
        "description": "Vigila tu inventario y avisa por WhatsApp cuando un producto baja del mínimo, antes de que se agote.",
        "instructions": "Eres un agente de control de inventario. Revisa los niveles de stock contra el mínimo definido. Cuando un producto esté en quiebre o por quebrar, redacta una alerta clara con el nombre del producto, stock actual y bodega. Cita siempre la fuente y la hora del dato.",
        "flow": [ODOO, AFABLE, WHATSAPP],
    },
    {
        "name": "Resumen diario de ventas",
        "category": "Ventas",
        "icon": "📈",
        "accent": "#586AD0",
        "author_name": "Comercial Andes",
        "uses_count": 318,
        "is_featured": True,
        "area": "ventas",
        "description": "Cada mañana arma un resumen de las ventas del día anterior y lo envía al equipo comercial.",
        "instructions": "Eres un analista comercial. Genera un resumen ejecutivo de las ventas: total facturado, número de pedidos, ticket promedio y top de productos. Excluye pedidos anulados. Sé breve y accionable. Cita la fuente.",
        "flow": [SHOPIFY, AFABLE, SLACK],
    },
    {
        "name": "Responde '¿tienen stock?' por WhatsApp",
        "category": "Atención",
        "icon": "💬",
        "accent": "#25D366",
        "author_name": "Tienda Norte",
        "uses_count": 587,
        "is_featured": True,
        "area": "atencion",
        "description": "Cuando un cliente pregunta por disponibilidad, consulta el ERP en vivo y responde con el dato real al instante.",
        "instructions": "Eres un asistente de atención al cliente. Cuando pregunten por disponibilidad o precio de un producto, consúltalo en el sistema en tiempo real y responde con el dato exacto. Si no hay stock, ofrece alternativas. Nunca inventes; si no tienes el dato, dilo.",
        "flow": [WHATSAPP, AFABLE, ODOO],
    },
    {
        "name": "Cobranza de facturas vencidas",
        "category": "Finanzas",
        "icon": "💰",
        "accent": "#FBBF24",
        "author_name": "Equipo Afable",
        "uses_count": 241,
        "is_featured": False,
        "area": "finanzas",
        "description": "Detecta facturas vencidas y prepara recordatorios de pago personalizados por cliente.",
        "instructions": "Eres un agente de cobranza. Identifica facturas vencidas, agrúpalas por cliente y redacta recordatorios de pago cordiales con monto, número de factura y días de mora. Prioriza por monto adeudado.",
        "flow": [SAP, AFABLE, GMAIL],
    },
    {
        "name": "Calificación de leads nuevos",
        "category": "Ventas",
        "icon": "🎯",
        "accent": "#60A5FA",
        "author_name": "Growth LATAM",
        "uses_count": 176,
        "is_featured": False,
        "area": "ventas",
        "description": "Analiza cada lead nuevo del CRM y lo prioriza según su potencial para que ventas ataque primero lo importante.",
        "instructions": "Eres un agente de calificación de leads. Para cada lead nuevo, evalúa industria, tamaño y origen, asigna una prioridad (alta/media/baja) y sugiere el siguiente paso. Resume en una línea por lead.",
        "flow": [HUBSPOT, AFABLE, SLACK],
    },
    {
        "name": "Conciliación de pedidos vs facturas",
        "category": "Operaciones",
        "icon": "🔗",
        "accent": "#A78BFA",
        "author_name": "Equipo Afable",
        "uses_count": 132,
        "is_featured": False,
        "area": "operaciones",
        "description": "Cruza pedidos contra facturas emitidas y levanta las diferencias para revisión.",
        "instructions": "Eres un agente de control operacional. Cruza los pedidos con las facturas emitidas y detecta inconsistencias: pedidos sin facturar, montos que no calzan o duplicados. Lista cada diferencia con su detalle.",
        "flow": [MSSQL, AFABLE, SHEETS],
    },
    {
        "name": "Reporte semanal para gerencia",
        "category": "Operaciones",
        "icon": "🗂️",
        "accent": "#F87171",
        "author_name": "Dirección Sur",
        "uses_count": 98,
        "is_featured": False,
        "area": "gerencia",
        "description": "Consolida ventas, inventario y cobranza en un reporte ejecutivo semanal listo para la reunión.",
        "instructions": "Eres el analista de la gerencia general. Consolida los indicadores clave de la semana (ventas, quiebres de stock, cobranza pendiente) en un reporte ejecutivo breve, con tendencias y alertas. Cita las fuentes.",
        "flow": [ODOO, AFABLE, GMAIL],
    },
    {
        "name": "Onboarding de nuevos clientes",
        "category": "Atención",
        "icon": "🤝",
        "accent": "#2DD4BF",
        "author_name": "CX Studio",
        "uses_count": 84,
        "is_featured": False,
        "area": "atencion",
        "description": "Da la bienvenida a cada cliente nuevo y le envía la información clave de su cuenta automáticamente.",
        "instructions": "Eres un agente de éxito de clientes. Cuando se registra un cliente nuevo, redacta un mensaje de bienvenida personalizado con los datos de su cuenta y los próximos pasos. Tono cercano y claro.",
        "flow": [AFABLE, WHATSAPP],
    },

    # ── Contexto Chile ──────────────────────────────────────────────
    {
        "name": "Emisión de boletas y facturas al SII",
        "category": "Finanzas", "icon": "🧾", "accent": "#1F4E79",
        "author_name": "Contadores Chile", "uses_count": 643, "is_featured": True,
        "area": "finanzas",
        "description": "Genera los documentos tributarios electrónicos (DTE) desde tus ventas y los emite al SII sin pasar por planillas.",
        "instructions": "Eres un agente de facturación electrónica chileno. A partir de cada venta, prepara el DTE correspondiente (boleta o factura), valida el RUT del receptor y deja el documento listo para emitir al SII. Avisa cualquier dato faltante antes de emitir.",
        "flow": [BSALE, AFABLE, SII],
    },
    {
        "name": "Cobranza con link de pago por WhatsApp",
        "category": "Finanzas", "icon": "💸", "accent": "#2F42A6",
        "author_name": "Cobranza Smart", "uses_count": 612, "is_featured": True,
        "area": "finanzas",
        "description": "Detecta facturas por cobrar y envía al cliente un link de pago Khipu/Webpay directo por WhatsApp.",
        "instructions": "Eres un agente de cobranza chileno. Identifica las facturas pendientes por cliente, genera un mensaje cordial con el monto y el link de pago, y envíalo por WhatsApp. Prioriza por monto y días de mora. Nunca dupliques cobros ya pagados.",
        "flow": [AFABLE, KHIPU, WHATSAPP],
    },
    {
        "name": "Seguimiento de despachos Chilexpress",
        "category": "Operaciones", "icon": "📦", "accent": "#E30613",
        "author_name": "Logística Sur", "uses_count": 601, "is_featured": True,
        "area": "operaciones",
        "description": "Sigue el estado de cada envío y avisa al cliente por WhatsApp cuando su pedido sale a reparto o se entrega.",
        "instructions": "Eres un agente de logística. Cruza los pedidos con el estado de despacho de Chilexpress y notifica proactivamente al cliente los cambios relevantes (en camino, en reparto, entregado). Levanta los envíos atrasados para revisión.",
        "flow": [JUMPSELLER, AFABLE, CHILEXPRESS],
    },
    {
        "name": "Declaración de IVA mensual (F29)",
        "category": "Finanzas", "icon": "📑", "accent": "#0B5FFF",
        "author_name": "Equipo Afable", "uses_count": 287, "is_featured": False,
        "area": "finanzas",
        "description": "Consolida ventas y compras del mes y arma el borrador del Formulario 29 para revisión.",
        "instructions": "Eres un asistente tributario chileno. Reúne el IVA débito y crédito del mes desde el ERP, calcula el resultado del F29 y presenta un borrador claro con el detalle. Señala diferencias o documentos sin clasificar.",
        "flow": [DEFONTANA, AFABLE, SII],
    },
    {
        "name": "Conciliación bancaria BancoEstado",
        "category": "Finanzas", "icon": "🏦", "accent": "#FF6600",
        "author_name": "Tesorería PYME", "uses_count": 214, "is_featured": False,
        "area": "finanzas",
        "description": "Cruza la cartola del banco con los registros contables y deja solo las diferencias para revisar.",
        "instructions": "Eres un agente de conciliación bancaria. Compara los movimientos de la cartola con los asientos contables, marca lo conciliado automáticamente y lista las diferencias (cargos sin registrar, abonos no identificados) con su detalle.",
        "flow": [BANCOESTADO, AFABLE, DEFONTANA],
    },
    {
        "name": "Liquidaciones de sueldo (Talana)",
        "category": "RRHH", "icon": "💼", "accent": "#7B61FF",
        "author_name": "RRHH Andes", "uses_count": 198, "is_featured": False,
        "area": "rrhh",
        "description": "Prepara el resumen de liquidaciones del mes y las envía a cada trabajador por correo.",
        "instructions": "Eres un agente de remuneraciones. Toma las liquidaciones del mes desde Talana, valida montos y haberes, y envía a cada trabajador su liquidación con un mensaje breve. Reporta cualquier inconsistencia al área de RRHH.",
        "flow": [TALANA, AFABLE, GMAIL],
    },
    {
        "name": "Cálculo de imposiciones Previred",
        "category": "RRHH", "icon": "🧾", "accent": "#1B5E20",
        "author_name": "RRHH Andes", "uses_count": 156, "is_featured": False,
        "area": "rrhh",
        "description": "Calcula las cotizaciones previsionales del mes y prepara el archivo para declarar en Previred.",
        "instructions": "Eres un agente previsional chileno. Calcula AFP, salud e impuestos por trabajador según la normativa vigente, y deja listo el resumen para declarar en Previred. Avisa contratos o datos incompletos.",
        "flow": [BUK, AFABLE, PREVIRED],
    },
    {
        "name": "Control de stock multitienda (Bsale)",
        "category": "Inventario", "icon": "🏬", "accent": "#E94E3C",
        "author_name": "Retail Chile", "uses_count": 342, "is_featured": False,
        "area": "inventario",
        "description": "Vigila el inventario por local y avisa cuando un producto se está agotando en alguna sucursal.",
        "instructions": "Eres un agente de inventario multitienda. Revisa el stock por local en Bsale, detecta quiebres y desbalances entre sucursales, y sugiere transferencias. Cita el local y el producto en cada alerta.",
        "flow": [BSALE, AFABLE, WHATSAPP],
    },
    {
        "name": "Pedidos Jumpseller a despacho",
        "category": "Ventas", "icon": "🛒", "accent": "#22B573",
        "author_name": "Ecommerce LATAM", "uses_count": 176, "is_featured": False,
        "area": "ventas",
        "description": "Toma los pedidos pagados de tu tienda y genera la orden de despacho automáticamente.",
        "instructions": "Eres un agente de operaciones de ecommerce. Cuando un pedido de Jumpseller queda pagado, valida los datos de envío y genera la orden de despacho con el courier. Avisa pedidos con dirección incompleta.",
        "flow": [JUMPSELLER, AFABLE, STARKEN],
    },
    {
        "name": "Indicadores del día (UF, UTM, dólar)",
        "category": "Finanzas", "icon": "📊", "accent": "#16A34A",
        "author_name": "Equipo Afable", "uses_count": 264, "is_featured": False,
        "area": "finanzas",
        "description": "Cada mañana publica los indicadores económicos del día en el canal del equipo.",
        "instructions": "Eres un asistente financiero chileno. Cada mañana entrega los valores del día de UF, UTM, dólar y euro de forma breve, y comenta variaciones relevantes respecto al día anterior.",
        "flow": [INDICADORES, AFABLE, SLACK],
    },
    {
        "name": "Alertas de vencimientos tributarios SII",
        "category": "Finanzas", "icon": "⏰", "accent": "#1F4E79",
        "author_name": "Contadores Chile", "uses_count": 143, "is_featured": False,
        "area": "finanzas",
        "description": "Avisa con anticipación los vencimientos del SII (F29, F22, IVA) para que nunca se pasen.",
        "instructions": "Eres un agente de cumplimiento tributario. Lleva el calendario de obligaciones del SII y avisa con días de anticipación cada vencimiento, indicando qué documentos faltan para cumplir.",
        "flow": [SII, AFABLE, GMAIL],
    },
    {
        "name": "Resumen de ventas por local (Toteat)",
        "category": "Ventas", "icon": "🍽️", "accent": "#FF6B35",
        "author_name": "Gastronomía Chile", "uses_count": 121, "is_featured": False,
        "area": "ventas",
        "description": "Consolida las ventas de cada local de tu restaurante y arma el resumen del día.",
        "instructions": "Eres un analista para cadenas gastronómicas. Consolida las ventas por local desde Toteat, calcula ticket promedio, platos más vendidos y comparación entre sucursales. Sé breve y accionable.",
        "flow": [TOTEAT, AFABLE, SLACK],
    },
    {
        "name": "Rendición de gastos (Rindegastos)",
        "category": "Operaciones", "icon": "🧮", "accent": "#00A8A8",
        "author_name": "Finanzas PYME", "uses_count": 98, "is_featured": False,
        "area": "operaciones",
        "description": "Revisa las rendiciones de gastos del equipo y las deja listas para contabilizar.",
        "instructions": "Eres un agente de control de gastos. Revisa las rendiciones, valida respaldos y montos contra la política de la empresa, y deja un resumen para contabilizar. Marca gastos sin respaldo o fuera de política.",
        "flow": [RINDEGASTOS, AFABLE, DEFONTANA],
    },
    {
        "name": "Pago programado a proveedores",
        "category": "Finanzas", "icon": "💰", "accent": "#F37021",
        "author_name": "Tesorería PYME", "uses_count": 134, "is_featured": False,
        "area": "finanzas",
        "description": "Arma la nómina de pagos de la semana según vencimientos y la deja lista para autorizar.",
        "instructions": "Eres un agente de cuentas por pagar. Reúne las facturas de proveedores por vencer, prioriza por fecha y monto, y prepara la nómina de pagos para autorización. No incluyas facturas ya pagadas o en disputa.",
        "flow": [SOFTLAND, AFABLE, BANCOESTADO],
    },
    {
        "name": "Validación de RUT y datos de cliente",
        "category": "Operaciones", "icon": "🪪", "accent": "#0066CC",
        "author_name": "Equipo Afable", "uses_count": 167, "is_featured": False,
        "area": "operaciones",
        "description": "Verifica que el RUT y los datos de cada cliente nuevo estén correctos antes de facturar.",
        "instructions": "Eres un agente de calidad de datos chileno. Valida el dígito verificador del RUT, normaliza razón social y giro, y detecta duplicados antes de crear o facturar a un cliente. Reporta los casos dudosos.",
        "flow": [AFABLE, NUBOX],
    },
    {
        "name": "Cotizaciones automáticas (Laudus)",
        "category": "Ventas", "icon": "📄", "accent": "#2E7D32",
        "author_name": "Comercial Andes", "uses_count": 152, "is_featured": False,
        "area": "ventas",
        "description": "Cuando un cliente pide precio por WhatsApp, arma la cotización con stock y precios reales.",
        "instructions": "Eres un agente comercial. Ante una solicitud de cotización, consulta precios y disponibilidad reales, arma la propuesta con condiciones y vigencia, y respóndela al cliente. Si falta stock, ofrece alternativas.",
        "flow": [WHATSAPP, AFABLE, LAUDUS],
    },
    {
        "name": "Recordatorio de cuentas por cobrar",
        "category": "Finanzas", "icon": "🔔", "accent": "#0066CC",
        "author_name": "Cobranza Smart", "uses_count": 189, "is_featured": False,
        "area": "finanzas",
        "description": "Envía recordatorios amables a los clientes con facturas próximas a vencer.",
        "instructions": "Eres un agente de cobranza preventiva. Identifica facturas por vencer en los próximos días y envía recordatorios cordiales al cliente con monto y fecha. Escala las que ya están vencidas.",
        "flow": [NUBOX, AFABLE, WHATSAPP],
    },
    {
        "name": "Onboarding de trabajadores (Buk)",
        "category": "RRHH", "icon": "🤝", "accent": "#FF4D4D",
        "author_name": "RRHH Andes", "uses_count": 87, "is_featured": False,
        "area": "rrhh",
        "description": "Da la bienvenida a cada nuevo trabajador y le envía sus accesos y documentos clave.",
        "instructions": "Eres un agente de RRHH. Cuando ingresa un trabajador nuevo en Buk, envíale un mensaje de bienvenida con sus accesos, documentos a firmar y primeros pasos. Avisa a su jefatura.",
        "flow": [BUK, AFABLE, GMAIL],
    },
    {
        "name": "Reporte de margen por producto",
        "category": "Ventas", "icon": "📈", "accent": "#0B5FFF",
        "author_name": "BI Chile", "uses_count": 173, "is_featured": False,
        "area": "ventas",
        "description": "Calcula el margen real por producto cruzando ventas y costos, y destaca los más y menos rentables.",
        "instructions": "Eres un analista de rentabilidad. Cruza precios de venta con costos por producto, calcula el margen y ordena de mayor a menor. Destaca productos que venden mucho con margen bajo. Cita la fuente.",
        "flow": [DEFONTANA, AFABLE, SHEETS],
    },
    {
        "name": "Postventa por WhatsApp",
        "category": "Atención", "icon": "🛎️", "accent": "#25D366",
        "author_name": "CX Studio", "uses_count": 205, "is_featured": False,
        "area": "atencion",
        "description": "Responde consultas de postventa (estado de pedido, garantía, boleta) con datos reales del sistema.",
        "instructions": "Eres un agente de postventa. Responde consultas sobre estado de pedidos, garantías y reenvío de boletas consultando el sistema en vivo. Si no tienes el dato, dilo y deriva a un humano.",
        "flow": [WHATSAPP, AFABLE, BSALE],
    },
]


class Command(BaseCommand):
    help = "Crea/actualiza las plantillas de la galería Explorar"

    def handle(self, *args, **options):
        created, updated = 0, 0
        for data in TEMPLATES:
            obj, was_created = AgentTemplate.objects.update_or_create(
                name=data["name"], defaults={**data, "is_active": True},
            )
            if was_created:
                created += 1
            else:
                updated += 1
        self.stdout.write(self.style.SUCCESS(
            f"Plantillas listas: {created} creadas, {updated} actualizadas "
            f"({AgentTemplate.objects.filter(is_active=True).count()} activas)."
        ))

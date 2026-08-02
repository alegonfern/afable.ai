from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.organizations.models import Organization, IntegrationScan
from apps.agents.models import Agent, Conversation, Message, Document

User = get_user_model()

DEMO_CONTEXT_ODOO = """El sistema Odoo de Empresa Demo S.A. contiene los siguientes módulos activos:

- **Ventas**: 1,847 órdenes de venta registradas. Clientes activos: 342. Producto más vendido: Plan Pro Enterprise.
- **Facturación**: 2,103 facturas emitidas. Monto total facturado Q1 2026: $2,847,320. 47 facturas vencidas por cobrar.
- **Inventario**: 284 productos activos. 12 productos con stock crítico (bajo mínimo). Rotación promedio: 23 días.
- **RRHH**: 87 empleados activos. Departamentos: Ventas (24), Operaciones (31), Tecnología (18), Administración (14).
- **CRM**: 1,204 oportunidades registradas. Tasa de conversión: 34%. Pipeline activo: $890,000.
- **Compras**: 423 órdenes de compra en Q1. 8 proveedores críticos. Gasto total: $1,203,400."""

RECOMMENDATIONS_ODOO = [
    {"id": "r1", "title": "Análisis de cartera vencida", "description": "47 facturas vencidas detectadas. Analiza montos, clientes y días de atraso.", "prompt": "Genera un análisis detallado de las facturas vencidas del sistema. Incluye montos, clientes con mayor deuda, días de atraso promedio y recomendaciones de cobranza.", "icon": "DollarSign", "color": "#F87171"},
    {"id": "r2", "title": "Reporte ejecutivo de ventas Q1", "description": "Resumen de rendimiento comercial del primer trimestre 2026.", "prompt": "Genera un reporte ejecutivo de ventas del Q1 2026. Incluye ingresos totales, comparación con Q4, top 5 productos, regiones de mayor crecimiento y proyección Q2.", "icon": "TrendingUp", "color": "#34D399"},
    {"id": "r3", "title": "Alerta de stock crítico", "description": "12 productos bajo el mínimo de inventario requieren atención inmediata.", "prompt": "Analiza los productos con stock crítico en el inventario. Lista los 12 productos, su stock actual vs mínimo, impacto en ventas estimado y recomendación de reposición.", "icon": "Package", "color": "#F59E0B"},
    {"id": "r4", "title": "Informe de rendimiento RRHH", "description": "Análisis de dotación, rotación y costos de personal por departamento.", "prompt": "Genera un informe de recursos humanos. Incluye distribución por departamento, análisis de costos de personal sobre ingresos totales, y recomendaciones de eficiencia operacional.", "icon": "Users", "color": "#60A5FA"},
    {"id": "r5", "title": "Pipeline de ventas y proyección", "description": "$890K en pipeline activo. Analiza probabilidades y proyecta cierre.", "prompt": "Analiza el pipeline de ventas del CRM. Detalla oportunidades por etapa, probabilidad de cierre, vendedores con mejor conversión y proyección de ingresos para Q2.", "icon": "BarChart2", "color": "#A78BFA"},
    {"id": "r6", "title": "Análisis de proveedores críticos", "description": "8 proveedores concentran el 73% del gasto en compras.", "prompt": "Genera un análisis de los proveedores críticos. Incluye concentración de gasto, riesgo de dependencia, alternativas recomendadas y oportunidades de negociación.", "icon": "Truck", "color": "#FB923C"},
]

DEMO_CONVERSATIONS = [
    {
        "title": "Análisis de ventas Q1 2026",
        "messages": [
            {"role": "user", "content": "¿Cómo fueron las ventas del primer trimestre?"},
            {"role": "assistant", "content": "## Resumen de Ventas Q1 2026\n\nLas ventas del primer trimestre cerraron con **$2.4M en ingresos**, representando un crecimiento del **+12% respecto al Q4 2025**.\n\n**Highlights:**\n- Región Norte lideró con $980K (+24% vs Q4)\n- Plan Pro Enterprise fue el producto estrella con 3,100 unidades\n- Ticket promedio subió de $265 a $288\n\n**Áreas de atención:**\n- Región Sur creció solo +3%, por debajo de la meta del 10%\n- 47 facturas vencidas por un total de $128,400\n\n¿Quieres que profundice en algún área específica?"},
        ]
    },
    {
        "title": "Cruce CRM y Facturación",
        "messages": [
            {"role": "user", "content": "¿Cuántas oportunidades del CRM se convirtieron en facturas este mes?"},
            {"role": "assistant", "content": "## Conversión CRM → Facturación — Marzo 2026\n\nDe las **1,204 oportunidades** en el CRM, **412 generaron facturas** en marzo.\n\n**Tasa de conversión: 34.2%**\n\n| Etapa CRM | Oportunidades | Facturas generadas | Conversión |\n|-----------|--------------|-------------------|------------|\n| Propuesta enviada | 289 | 187 | 64.7% |\n| Negociación | 156 | 142 | 91.0% |\n| Cierre | 89 | 83 | 93.3% |\n\n**Insight clave:** Las oportunidades que pasan a 'Negociación' tienen una tasa de cierre del 91%, lo que sugiere que el proceso de calificación inicial es efectivo.\n\n¿Quieres ver qué oportunidades llevan más de 30 días en la etapa de Propuesta?"},
        ]
    },
]

DEMO_DOCUMENTS = [
    {
        "title": "Reporte Ejecutivo Q1 2026",
        "content": "# Reporte Ejecutivo — Q1 2026\n\n## Resumen General\n\nEmpresa Demo S.A. cerró el primer trimestre con resultados por encima de las proyecciones iniciales, impulsado por el crecimiento en ventas enterprise y la expansión en la Región Norte.\n\n## Indicadores Clave\n\n| Métrica | Q1 2026 | Q4 2025 | Variación |\n|---------|---------|---------|----------|\n| Ingresos | $2.4M | $2.1M | +12% |\n| Margen bruto | 41% | 38% | +3pp |\n| Clientes activos | 342 | 318 | +7.5% |\n| NPS | 67 | 61 | +6 pts |\n\n## Conclusiones\n\n1. El segmento enterprise creció 24%, validando la estrategia de upmarket\n2. La cartera vencida ($128K) requiere acción inmediata del equipo de cobranza\n3. Stock crítico en 12 SKUs puede afectar ventas de Q2 si no se gestiona\n\n## Próximos Pasos\n\n- Revisar política de crédito para clientes con más de 60 días de atraso\n- Lanzar campaña de reactivación para Región Sur\n- Gestionar reposición urgente de productos críticos",
        "grid_x": 0, "grid_y": 0, "grid_w": 7, "grid_h": 7,
    },
    {
        "title": "Análisis de Cartera Vencida",
        "content": "# Análisis de Cartera Vencida — Marzo 2026\n\n## Situación Actual\n\n**Total vencido: $128,400** distribuido en 47 facturas de 23 clientes distintos.\n\n## Distribución por Antigüedad\n\n| Rango | Facturas | Monto | % del total |\n|-------|---------|-------|-------------|\n| 1-30 días | 28 | $67,200 | 52% |\n| 31-60 días | 12 | $38,400 | 30% |\n| +60 días | 7 | $22,800 | 18% |\n\n## Clientes Críticos\n\nLos 5 clientes con mayor deuda concentran el **68% del total vencido**.\n\n## Recomendaciones\n\n1. **Acción inmediata** en facturas +60 días: considerar envío a cobranza externa\n2. **Contacto proactivo** a clientes 31-60 días con plan de pago\n3. **Revisión de límite de crédito** para los 3 clientes con historial de atraso recurrente",
        "grid_x": 7, "grid_y": 0, "grid_w": 5, "grid_h": 5,
    },
]


class Command(BaseCommand):
    help = 'Siembra datos demo para un usuario específico'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str)

    def handle(self, *args, **options):
        email = options['email']
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            self.stderr.write(f'Usuario {email} no encontrado.')
            return

        org, created = Organization.objects.get_or_create(
            owner=user, name='Empresa Demo S.A.',
            defaults={'sector': 'retail'}
        )
        self.stdout.write(f'Org: {"creada" if created else "existente"}')

        agent, _ = Agent.objects.get_or_create(
            organization=org, name='Analista Empresarial',
            defaults={'description': 'Agente de análisis con acceso a Odoo y CRM', 'is_active': True}
        )

        scan, created = IntegrationScan.objects.get_or_create(
            organization=org, system_type='odoo',
            defaults={
                'system_name': 'Odoo — Empresa Demo S.A.',
                'modules_found': ['Ventas', 'Facturación', 'Inventario', 'RRHH', 'CRM', 'Compras'],
                'ai_context': DEMO_CONTEXT_ODOO,
                'recommendations': RECOMMENDATIONS_ODOO,
            }
        )
        self.stdout.write(f'Scan Odoo: {"creado" if created else "existente"}')

        for conv_data in DEMO_CONVERSATIONS:
            conv, created = Conversation.objects.get_or_create(
                agent=agent, user=user, title=conv_data['title']
            )
            if created:
                for msg in conv_data['messages']:
                    Message.objects.create(conversation=conv, **msg)
        self.stdout.write('Conversaciones: listas')

        for doc_data in DEMO_DOCUMENTS:
            Document.objects.get_or_create(
                user=user, title=doc_data['title'],
                defaults={
                    'content': doc_data['content'],
                    'grid_x': doc_data['grid_x'], 'grid_y': doc_data['grid_y'],
                    'grid_w': doc_data['grid_w'], 'grid_h': doc_data['grid_h'],
                }
            )
        self.stdout.write('Documentos: listos')
        self.stdout.write(self.style.SUCCESS(f'Demo listo para {email}'))

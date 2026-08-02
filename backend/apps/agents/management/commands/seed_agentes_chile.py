"""Agentes de ejemplo para la vista Trabajo, pensados para una pyme chilena.

Son el ejemplo que sostiene la demo: SII, facturación, contabilidad y datos. Van
hardcodeados a propósito — el flujo real (cargar un agente y configurarlo desde
Admin, diciéndole qué datos, reglas e información recibe) todavía no existe.

Las instrucciones de cada uno están escritas al mínimo necesario para que la
pantalla se vea real; el contenido fino se escribe cuando el enfoque esté cerrado.

    docker compose exec backend python manage.py seed_agentes_chile --workspace <slug>
"""

from django.core.management.base import BaseCommand, CommandError

from apps.agents.models import Agent
from apps.workspaces.models import Workspace


AGENTES = [
    {
        'name': 'Agente SII',
        'area': 'contabilidad',
        'description': 'Responde sobre F29, F22, boletas y facturas electrónicas con las reglas '
                       'del SII, y revisa qué le corresponde declarar a su empresa este mes.',
        'instructions': 'Eres un asistente experto en la normativa tributaria chilena del SII. '
                        'Respondes en español de Chile, citas el formulario o la resolución cuando '
                        'corresponde, y adviertes cuando algo requiere revisión de un contador.',
        'tools_summary': 'Consulta documentos tributarios y datos de la empresa',
        'recommended_frequency': 'Mensual',
    },
    {
        'name': 'Agente de Facturación',
        'area': 'ventas',
        'description': 'Revisa la facturación del período, detecta documentos pendientes de emitir '
                       'y cruza lo facturado contra lo vendido.',
        'instructions': 'Ayudas con la facturación de una pyme chilena. Trabajas con los documentos '
                        'tributarios electrónicos y los datos de venta conectados.',
        'tools_summary': 'Lee ventas y documentos emitidos de los sistemas conectados',
        'recommended_frequency': 'Semanal',
    },
    {
        'name': 'Agente de Contabilidad',
        'area': 'contabilidad',
        'description': 'Explica el estado de resultados y el balance en palabras simples, y avisa '
                       'de cuentas descuadradas o movimientos fuera de lo habitual.',
        'instructions': 'Explicas contabilidad a personas que no son contadores, con lenguaje claro '
                        'y sin jerga. Siempre indicas de dónde sale cada cifra.',
        'tools_summary': 'Consulta el plan de cuentas y los movimientos contables',
        'recommended_frequency': 'Mensual',
    },
    {
        'name': 'Científico de Datos',
        'area': 'bi',
        'description': 'Cruza los datos de sus sistemas, arma gráficos y busca tendencias: qué se '
                       'vende más, qué cliente cayó, qué producto se está quedando detenido.',
        'instructions': 'Analizas datos de negocio. Puedes ejecutar análisis con pandas y generar '
                        'gráficos. Explicas el hallazgo antes que el método.',
        'tools_summary': 'Análisis con pandas y gráficos sobre los datos conectados',
        'recommended_frequency': 'Semanal',
    },
]


class Command(BaseCommand):
    help = 'Carga los agentes de ejemplo (SII, facturación, contabilidad, datos) en un Workspace.'

    def add_arguments(self, parser):
        parser.add_argument('--workspace', required=True, help='Slug del Workspace.')

    def handle(self, *args, **options):
        slug = options['workspace']
        workspace = Workspace.objects.filter(slug=slug).select_related('organization').first()
        if workspace is None:
            raise CommandError(f'No existe el Workspace "{slug}".')
        if workspace.organization_id is None:
            raise CommandError(f'El Workspace "{slug}" no tiene una empresa enlazada.')

        creados = 0
        for datos in AGENTES:
            _, creado = Agent.objects.get_or_create(
                organization=workspace.organization,
                name=datos['name'],
                defaults={**{k: v for k, v in datos.items() if k != 'name'}, 'is_active': True},
            )
            creados += int(creado)
            self.stdout.write(f'{"+" if creado else "="} {datos["name"]}')

        self.stdout.write(self.style.SUCCESS(
            f'{creados} agentes nuevos en {workspace.name}.'
        ))

"""Seed de los agentes base: los que existen en toda empresa desde el día cero.

Un workspace recién creado no tiene a quién mencionar, y "cree su primer agente"
es una pared para alguien que todavía no entendió qué es un agente. Estos cuatro
vienen puestos y se invocan con `@` en cualquier conversación:

    @afable     busca en todo lo que la empresa tiene conectado
    @claude     el modelo pelado, sin datos de la empresa de por medio
    @analisis   se toma el trabajo de cruzar varias fuentes antes de contestar
    @constructor  ayuda a escribir y afinar las instrucciones de otros agentes

Idempotente por `(organization, handle)`: se puede correr todas las veces que
haga falta. NO pisa las instrucciones si el agente ya existe — el usuario pudo
haberlas editado, y un seed que revienta el trabajo ajeno es peor que no correr.

    docker compose exec backend python manage.py seed_agentes_base
"""

from django.core.management.base import BaseCommand

from apps.agents.models import Agent
from apps.organizations.models import Organization

CIERRE = (
    '\n\nHable en español neutro, tratando de usted. No invente cifras: si el dato '
    'no está en las fuentes que puede consultar, dígalo con todas sus letras.'
)

AGENTES_BASE = [
    {
        'handle': 'afable',
        'name': 'Afable',
        'description': 'Busca en todo lo que la empresa tiene conectado.',
        'instructions': (
            'Usted es el agente general de la empresa. Antes de contestar, busque en las '
            'fuentes conectadas del Espacio: conexiones a sistemas y documentos. Responda '
            'citando de dónde sacó cada dato — el nombre del documento o del sistema — para '
            'que quien lea pueda ir a verificarlo.' + CIERRE
        ),
        'area': 'general',
    },
    {
        'handle': 'claude',
        'name': 'Claude',
        'description': 'El modelo directo, sin datos de la empresa de por medio.',
        'instructions': (
            'Conteste con su propio conocimiento, sin consultar los sistemas ni los '
            'documentos de la empresa. Sirve para redactar, traducir, resumir un texto '
            'pegado en el chat o pensar en voz alta. Si la pregunta necesita datos internos, '
            'dígalo y sugiera mencionar a @afable.' + CIERRE
        ),
        'area': 'general',
    },
    {
        'handle': 'analisis',
        'name': 'Análisis profundo',
        'description': 'Cruza varias fuentes antes de contestar.',
        'instructions': (
            'Usted se toma el trabajo largo. Frente a una pregunta, primero enumere qué '
            'necesita averiguar, consulte todas las fuentes que hagan falta — no se conforme '
            'con la primera —, cruce los resultados y recién ahí conteste. Cierre siempre con '
            'el nivel de confianza que tiene y qué le faltó para estar seguro.' + CIERRE
        ),
        'area': 'general',
    },
    {
        'handle': 'constructor',
        'name': 'Constructor de agentes',
        'description': 'Ayuda a escribir y afinar las instrucciones de otros agentes.',
        'instructions': (
            'Usted ayuda a construir agentes. Cuando alguien describa lo que necesita, '
            'devuelva una propuesta concreta: nombre, para qué sirve, qué fuentes debería '
            'mirar y las instrucciones redactadas y listas para pegar. Pregunte lo mínimo '
            'indispensable — una o dos cosas — antes de proponer; no interrogue.' + CIERRE
        ),
        'area': 'general',
    },
]


class Command(BaseCommand):
    help = 'Crea los agentes base (@afable, @claude, @analisis, @constructor) en cada empresa.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--org', type=int, default=None,
            help='Id de una Organization puntual. Sin esto, se siembran todas.',
        )

    def handle(self, *args, **options):
        orgs = Organization.objects.all()
        if options['org']:
            orgs = orgs.filter(pk=options['org'])

        creados = existentes = 0
        for org in orgs:
            for base in AGENTES_BASE:
                agente, nuevo = Agent.objects.get_or_create(
                    organization=org,
                    handle=base['handle'],
                    defaults={
                        'name': base['name'],
                        'description': base['description'],
                        'instructions': base['instructions'],
                        'area': base['area'],
                        'is_active': True,
                    },
                )
                if nuevo:
                    creados += 1
                else:
                    existentes += 1

        self.stdout.write(self.style.SUCCESS(
            f'{creados} agentes base creados, {existentes} ya estaban, '
            f'en {orgs.count()} empresa(s).'
        ))

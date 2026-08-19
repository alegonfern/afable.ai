"""Comando para (re)sembrar los agentes base en empresas que ya existen.

⚠️ **El camino normal ya NO es este.** Una empresa nueva los recibe sola al crearse
(`apps/agents/agentes_base.py`, llamado desde `Organization.crear_para_dueno`). Este
comando queda para las empresas creadas ANTES de ese cambio, que nacieron vacías.

Del catálogo original:

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

from apps.agents.agentes_base import (
    AGENTES_BASE, acortar_handles, poner_caras, sembrar_en,
)
from apps.organizations.models import Organization

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
        caras = cortos = 0
        for org in orgs:
            nuevos = sembrar_en(org)
            creados += nuevos
            existentes += len(AGENTES_BASE) - nuevos
            # Y los que ya existían sin cara: la galería no puede quedar a medias, con
            # unos agentes reconocibles y otros en gris.
            caras += poner_caras(org)
            cortos += acortar_handles(org)

        self.stdout.write(self.style.SUCCESS(
            f'{creados} agentes base creados, {existentes} ya estaban, '
            f'{caras} recibieron su cara, {cortos} handles acortados, '
            f'en {orgs.count()} empresa(s).'
        ))

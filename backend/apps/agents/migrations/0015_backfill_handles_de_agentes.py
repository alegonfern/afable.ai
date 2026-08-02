"""Los agentes que ya existían no tenían con qué ser mencionados.

Se les arma el handle desde el nombre, resolviendo los choques dentro de cada
empresa. Sin esto quedarían todos con el handle vacío y `@` no encontraría nada.
Va en una migración aparte de la que agregó el campo porque la constraint de
unicidad ya está creada y hay que respetarla al llenar.
"""

from django.db import migrations
from django.utils.text import slugify


def poner_handle_a_los_agentes_existentes(apps, schema_editor):
    Agent = apps.get_model('agents', 'Agent')
    tomados = {}

    # Los que ya tienen handle reservan su lugar antes de repartir el resto.
    for agente in Agent.objects.exclude(handle='').only('organization_id', 'handle'):
        tomados.setdefault(agente.organization_id, set()).add(agente.handle)

    for agente in Agent.objects.filter(handle='').order_by('organization_id', 'id'):
        base = slugify(agente.name)[:50] or 'agente'
        usados = tomados.setdefault(agente.organization_id, set())
        candidato, n = base, 2
        while candidato in usados:
            candidato = f'{base}-{n}'
            n += 1
        usados.add(candidato)
        agente.handle = candidato
        agente.save(update_fields=['handle'])


def sin_vuelta(apps, schema_editor):
    """No se revierte: borrar los handles rompería las menciones ya escritas."""


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0014_agent_handle_message_agent_and_more'),
    ]

    operations = [
        migrations.RunPython(poner_handle_a_los_agentes_existentes, sin_vuelta),
    ]

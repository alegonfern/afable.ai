"""El titular del plan pasa del Workspace a la Empresa.

Un plan cubre **todos** los Workspaces de la empresa. Cobrar por área habría significado
que abrir un Workspace nuevo cuesta plata, y entonces nadie los usaría para lo que sirven.

La facturación se había construido colgada del Workspace unas horas antes, cuando Workspace
todavía era la empresa. El dato se conserva: cada fila se lleva al dueño de su Workspace.
"""

import django.db.models.deletion
from django.db import migrations, models

MODELOS = ['clientepasarela', 'metodopago', 'subscription', 'payment']
RELACIONES = {
    'clientepasarela': 'clientes_pasarela',
    'metodopago': 'metodos_pago',
    'subscription': 'subscriptions',
    'payment': 'payments',
}


def subir_a_la_empresa(apps, schema_editor):
    for nombre in ['ClientePasarela', 'MetodoPago', 'Subscription', 'Payment']:
        modelo = apps.get_model('payments', nombre)
        for fila in modelo.objects.select_related('workspace').all():
            fila.organization_id = fila.workspace.organization_id
            fila.save(update_fields=['organization'])


def volver_atras(apps, schema_editor):
    Workspace = apps.get_model('workspaces', 'Workspace')
    por_org = {ws.organization_id: ws.id for ws in Workspace.objects.all()}
    for nombre in ['ClientePasarela', 'MetodoPago', 'Subscription', 'Payment']:
        modelo = apps.get_model('payments', nombre)
        for fila in modelo.objects.all():
            fila.workspace_id = por_org.get(fila.organization_id)
            fila.save(update_fields=['workspace'])


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0003_precios_en_dolares'),
        ('organizations', '0014_empresa_es_el_nivel_de_arriba'),
    ]

    operations = [
        # El unique de (workspace, proveedor) tiene que salir antes de tocar la columna.
        migrations.AlterUniqueTogether(name='clientepasarela', unique_together=set()),
    ] + [
        migrations.AddField(
            model_name=modelo,
            name='organization',
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.CASCADE,
                related_name=RELACIONES[modelo], to='organizations.organization',
            ),
        )
        for modelo in MODELOS
    ] + [
        migrations.RunPython(subir_a_la_empresa, volver_atras),
    ] + [
        migrations.RemoveField(model_name=modelo, name='workspace') for modelo in MODELOS
    ] + [
        migrations.AlterField(
            model_name=modelo,
            name='organization',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name=RELACIONES[modelo], to='organizations.organization',
            ),
        )
        for modelo in MODELOS
    ] + [
        migrations.AlterUniqueTogether(
            name='clientepasarela', unique_together={('organization', 'proveedor')},
        ),
    ]

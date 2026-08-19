"""La Sesión pasa a vivir dentro de un Workspace, no de la empresa entera.

El trabajo va abajo: una Sesión es de un área ("Cliente Rever" es de Proyectos), no de toda
la empresa. Las que ya existían se mudan al Workspace **General**, que es el que recibe a
todos — mandarlas a un área restringida las habría escondido de gente que hoy las ve.
"""

import django.db.models.deletion
from django.db import migrations, models


def mudar_al_general(apps, schema_editor):
    Sesion = apps.get_model('sesiones', 'Sesion')
    Space = apps.get_model('workspaces', 'Space')

    generales = {}
    for sesion in Sesion.objects.select_related('workspace').all():
        org_id = sesion.workspace.organization_id
        if org_id not in generales:
            generales[org_id] = (
                Space.objects.filter(organization_id=org_id, visibility='abierto').first()
                or Space.objects.filter(organization_id=org_id).first()
            )
        destino = generales[org_id]
        if destino is None:
            continue
        sesion.espacio_id = destino.id
        sesion.save(update_fields=['espacio'])


def volver_atras(apps, schema_editor):
    Sesion = apps.get_model('sesiones', 'Sesion')
    Workspace = apps.get_model('workspaces', 'Workspace')
    por_org = {ws.organization_id: ws.id for ws in Workspace.objects.all()}
    for sesion in Sesion.objects.select_related('espacio').all():
        if sesion.espacio_id:
            sesion.workspace_id = por_org.get(sesion.espacio.organization_id)
            sesion.save(update_fields=['workspace'])


class Migration(migrations.Migration):

    dependencies = [
        ('sesiones', '0002_instrucciones_y_defectos'),
        ('workspaces', '0011_personas_y_espacios_a_la_empresa'),
    ]

    operations = [
        migrations.AddField(
            model_name='sesion',
            name='espacio',
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.CASCADE,
                related_name='sesiones_nuevas', to='workspaces.space',
            ),
        ),
        migrations.RunPython(mudar_al_general, volver_atras),
        migrations.RemoveField(model_name='sesion', name='workspace'),
        migrations.RenameField(model_name='sesion', old_name='espacio', new_name='workspace'),
        migrations.AlterField(
            model_name='sesion',
            name='workspace',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='sesiones', to='workspaces.space',
            ),
        ),
    ]

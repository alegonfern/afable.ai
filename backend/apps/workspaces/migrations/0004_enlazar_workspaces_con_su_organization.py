"""Enlaza cada Workspace existente con la Organization que administra.

Parte del puente descrito en `Workspace.organization`: la app anterior cuelga las
conexiones, los documentos, el contexto y los agentes de `Organization`, y el prompt
del agente lee su sector. Sin este enlace, lo que se edite en la pantalla de
Workspace no tendría efecto sobre lo que ya funciona.

Cada Organization solo puede quedar enlazada a un Workspace (es OneToOne), así que
si un usuario administra varios, el primero se queda con la que ya existía y los
demás estrenan una nueva.
"""

from django.db import migrations


ROLE_ADMIN = 'admin'


def enlazar(apps, schema_editor):
    Workspace = apps.get_model('workspaces', 'Workspace')
    Membership = apps.get_model('workspaces', 'Membership')
    Organization = apps.get_model('organizations', 'Organization')

    tomadas = set()

    for workspace in Workspace.objects.filter(organization__isnull=True).order_by('id'):
        admin = (
            Membership.objects
            .filter(workspace=workspace, role=ROLE_ADMIN)
            .order_by('joined_at')
            .first()
        )
        if admin is None:
            continue

        propias = Organization.objects.filter(owner_id=admin.user_id).exclude(id__in=tomadas)
        # Se prefiere una real sobre la "Personal" que crea sola apps/agents/views.py.
        org = propias.exclude(name='Personal').order_by('id').first() or propias.order_by('id').first()

        if org is None:
            org = Organization.objects.create(
                owner_id=admin.user_id,
                name=workspace.name,
                sector=workspace.sector or 'otro',
            )

        workspace.organization = org
        workspace.save(update_fields=['organization'])
        tomadas.add(org.id)


def desenlazar(apps, schema_editor):
    Workspace = apps.get_model('workspaces', 'Workspace')
    Workspace.objects.update(organization=None)


class Migration(migrations.Migration):

    dependencies = [
        ('workspaces', '0003_workspace_employees_workspace_organization_and_more'),
        ('organizations', '0009_companydocument_external_id_companydocument_source_and_more'),
    ]

    operations = [
        migrations.RunPython(enlazar, desenlazar),
    ]

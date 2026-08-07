"""Las personas y los Espacios pasan a colgar de la Empresa.

Segundo paso de los tres niveles. Cuando termina esta migración:

- `Membership` e `Invitation` cuelgan de la **Empresa** (el rol es de la empresa, no de un
  área: ser editor en Ventas y miembro en Finanzas sería un permiso que nadie puede
  explicar en una línea).
- El `Space` cuelga de la Empresa y su slug pasa a ser único en toda la instalación,
  porque va a viajar solo en la URL.
- Cada Empresa queda con un Workspace **General** abierto. Es el que hereda lo que existía
  antes de que hubiera áreas: sin él, una empresa que nunca creó un Espacio se quedaría sin
  ningún lugar donde abrir una Sesión.

El modelo `Workspace` viejo —el que era la empresa— todavía existe al terminar acá: lo
borra `0012`, después de que `payments`, `sesiones` y `agents` suelten sus llaves.
"""

import django.db.models.deletion
from django.db import migrations, models
from django.utils.text import slugify


def subir_a_la_empresa(apps, schema_editor):
    Organization = apps.get_model('organizations', 'Organization')
    Membership = apps.get_model('workspaces', 'Membership')
    Invitation = apps.get_model('workspaces', 'Invitation')
    Space = apps.get_model('workspaces', 'Space')
    Workspace = apps.get_model('workspaces', 'Workspace')

    for fila in Membership.objects.select_related('workspace').all():
        fila.organization_id = fila.workspace.organization_id
        fila.save(update_fields=['organization'])

    for fila in Invitation.objects.select_related('workspace').all():
        fila.organization_id = fila.workspace.organization_id
        fila.save(update_fields=['organization'])

    # Los slugs de Espacio eran únicos POR Workspace; ahora son únicos a secas.
    vistos = set()
    for espacio in Space.objects.select_related('workspace').all():
        espacio.organization_id = espacio.workspace.organization_id
        slug = espacio.slug
        if slug in vistos:
            n = 2
            while f'{slug}-{n}' in vistos:
                n += 1
            slug = f'{slug}-{n}'
            espacio.slug = slug
        vistos.add(slug)
        espacio.save(update_fields=['organization', 'slug'])

    # El General de cada empresa que no tenga ya uno abierto.
    for ws in Workspace.objects.select_related('organization').all():
        org = ws.organization
        if org is None:
            continue
        if Space.objects.filter(organization=org, visibility='abierto').exists():
            continue
        base = slugify(f'{org.name}-general')[:120] or 'general'
        candidato, n = base, 2
        while Space.objects.filter(slug=candidato).exists():
            candidato, n = f'{base}-{n}', n + 1
        Space.objects.create(
            organization=org, workspace=ws, name='General', slug=candidato,
            visibility='abierto',
            description='Donde trabaja toda la empresa. Se creó solo al separar la '
                        'empresa de sus Workspaces.',
        )


def volver_atras(apps, schema_editor):
    """Se recupera desde la Empresa: cada una tenía un solo Workspace."""
    Membership = apps.get_model('workspaces', 'Membership')
    Invitation = apps.get_model('workspaces', 'Invitation')
    Space = apps.get_model('workspaces', 'Space')
    Workspace = apps.get_model('workspaces', 'Workspace')

    por_org = {ws.organization_id: ws.id for ws in Workspace.objects.all()}
    for modelo in (Membership, Invitation, Space):
        for fila in modelo.objects.all():
            fila.workspace_id = por_org.get(fila.organization_id)
            fila.save(update_fields=['workspace'])


class Migration(migrations.Migration):

    # Sin transacción única: Postgres no deja alterar una tabla en la misma transacción
    # en la que se acaban de mover sus datos ("pending trigger events"). Cada operación
    # va por separado, que es justo lo que hace falta acá.
    atomic = False

    dependencies = [
        ('workspaces', '0010_onboarding_oculto'),
        ('organizations', '0014_empresa_es_el_nivel_de_arriba'),
    ]

    operations = [
        # ── Las llaves nuevas, todavía opcionales ────────────────────────────
        migrations.AddField(
            model_name='membership',
            name='organization',
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.CASCADE,
                related_name='memberships', to='organizations.organization',
            ),
        ),
        migrations.AddField(
            model_name='invitation',
            name='organization',
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.CASCADE,
                related_name='invitations', to='organizations.organization',
            ),
        ),
        migrations.AddField(
            model_name='space',
            name='organization',
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.CASCADE,
                related_name='workspaces', to='organizations.organization',
            ),
        ),

        migrations.RunPython(subir_a_la_empresa, volver_atras),

        # ── Fuera las viejas ─────────────────────────────────────────────────
        migrations.RemoveConstraint(model_name='membership', name='unica_membresia_por_workspace'),
        migrations.RemoveConstraint(model_name='invitation', name='unica_invitacion_viva_por_correo'),
        migrations.RemoveConstraint(model_name='space', name='unico_slug_de_espacio_por_workspace'),

        migrations.RemoveField(model_name='membership', name='workspace'),
        migrations.RemoveField(model_name='invitation', name='workspace'),
        migrations.RemoveField(model_name='space', name='workspace'),

        # ── Y ahora sí, obligatorias ─────────────────────────────────────────
        migrations.AlterField(
            model_name='membership',
            name='organization',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='memberships', to='organizations.organization',
            ),
        ),
        migrations.AlterField(
            model_name='invitation',
            name='organization',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='invitations', to='organizations.organization',
            ),
        ),
        migrations.AlterField(
            model_name='space',
            name='organization',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='workspaces', to='organizations.organization',
            ),
        ),
        migrations.AlterField(
            model_name='space',
            name='slug',
            field=models.SlugField(max_length=140, unique=True),
        ),

        migrations.AddConstraint(
            model_name='membership',
            constraint=models.UniqueConstraint(
                fields=('organization', 'user'), name='unica_membresia_por_empresa',
            ),
        ),
        migrations.AddConstraint(
            model_name='invitation',
            constraint=models.UniqueConstraint(
                condition=models.Q(('accepted_at__isnull', True), ('revoked_at__isnull', True)),
                fields=('organization', 'email'), name='unica_invitacion_viva_por_correo',
            ),
        ),
    ]

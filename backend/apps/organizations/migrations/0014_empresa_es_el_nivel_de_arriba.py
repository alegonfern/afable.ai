"""La Empresa recibe la identidad que estaba duplicada en el Workspace.

Primer paso de los tres niveles (Empresa → Workspace → Sesión). Acá sólo se SUMAN campos
y se copian los datos; la tabla vieja se desarma en la migración de `workspaces`, que corre
después. Partirlo así deja este paso reversible sin perder nada.

Los campos venían espejados a mano por `Workspace.mirror_to_organization`, que se ejecutaba
en cada guardado. Se copian igual uno por uno porque el espejo no cubría el logo, el correo
de facturación ni el permiso de crear agentes.
"""

from django.db import migrations, models


def bajar_identidad_del_workspace(apps, schema_editor):
    """Cada Empresa toma el slug y la identidad del Workspace que la administraba."""
    Organization = apps.get_model('organizations', 'Organization')
    Workspace = apps.get_model('workspaces', 'Workspace')

    for ws in Workspace.objects.select_related('organization').all():
        org = ws.organization
        if org is None:
            continue
        org.slug = ws.slug
        org.logo = ws.logo
        org.billing_email = ws.billing_email
        org.agent_creation_policy = ws.agent_creation_policy
        org.onboarding_oculto = ws.onboarding_oculto
        # El espejo ya los copiaba, pero si alguno quedó vacío manda el del Workspace:
        # era la pantalla que la gente editaba.
        org.name = ws.name or org.name
        org.sector = ws.sector or org.sector
        org.description = ws.description or org.description
        org.employees = ws.employees or org.employees
        org.rut = ws.tax_id or org.rut
        org.save()

    # Una Empresa sin Workspace que la administrara igual necesita slug: es lo que viaja
    # en la URL.
    from django.utils.text import slugify
    for org in Organization.objects.filter(slug__isnull=True):
        base = slugify(org.name)[:120] or 'empresa'
        candidato, n = base, 2
        while Organization.objects.filter(slug=candidato).exclude(pk=org.pk).exists():
            candidato, n = f'{base}-{n}', n + 1
        org.slug = candidato
        org.save(update_fields=['slug'])


def volver_atras(apps, schema_editor):
    """Los campos se van con el AddField; no hay nada que deshacer en los datos."""


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0013_companydocument_restringido'),
        ('workspaces', '0010_onboarding_oculto'),
    ]

    operations = [
        migrations.AddField(
            model_name='organization',
            name='slug',
            field=models.SlugField(blank=True, max_length=140, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='organization',
            name='logo',
            field=models.ImageField(blank=True, null=True, upload_to='workspace_logos/'),
        ),
        migrations.AddField(
            model_name='organization',
            name='billing_email',
            field=models.EmailField(blank=True, help_text='Correo para comprobantes de pago.', max_length=254),
        ),
        migrations.AddField(
            model_name='organization',
            name='agent_creation_policy',
            field=models.CharField(
                choices=[('todos', 'Todos los miembros'), ('editores', 'Editores y administradores'), ('admins', 'Solo administradores')],
                default='editores', help_text='Quién puede crear agentes en esta empresa.', max_length=16,
            ),
        ),
        migrations.AddField(
            model_name='organization',
            name='onboarding_oculto',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(bajar_identidad_del_workspace, volver_atras),
    ]

"""Le da un Workspace propio a los usuarios que ya existían.

Sin esto, quien tenía cuenta antes de la Etapa 1 queda sin ninguna membresía y por
lo tanto sin acceso a nada — incluido el superuser con el que se prueba en local.
Los modelos históricos no traen los métodos del modelo, así que el slug y el rol
se arman a mano acá.
"""

from django.db import migrations
from django.utils.text import slugify


ROLE_ADMIN = 'admin'


def crear_workspaces(apps, schema_editor):
    User = apps.get_model('authentication', 'User')
    Workspace = apps.get_model('workspaces', 'Workspace')
    Membership = apps.get_model('workspaces', 'Membership')

    for user in User.objects.filter(memberships__isnull=True).order_by('date_joined'):
        quien = (user.first_name or '').strip() or user.email.split('@')[0]
        nombre = f'Workspace de {quien}'

        base = slugify(nombre)[:120] or 'workspace'
        slug = base
        sufijo = 2
        while Workspace.objects.filter(slug=slug).exists():
            slug = f'{base}-{sufijo}'
            sufijo += 1

        workspace = Workspace.objects.create(name=nombre, slug=slug)
        Membership.objects.create(workspace=workspace, user=user, role=ROLE_ADMIN)


def revertir(apps, schema_editor):
    """Al revés no se borra nada: los Workspace creados acá pueden tener contenido."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('workspaces', '0001_initial'),
        ('authentication', '0006_remove_user_areas_remove_user_org_admin'),
    ]

    operations = [
        migrations.RunPython(crear_workspaces, revertir),
    ]

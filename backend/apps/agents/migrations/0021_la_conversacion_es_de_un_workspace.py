"""La conversación deja de apuntar a un Espacio y apunta a un Workspace.

Es el mismo dato con el nombre correcto: el Espacio pasó a llamarse Workspace. `null`
sigue significando lo mismo — una conversación personal, que no es de ningún equipo.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0020_disparador_publica_en_sesion'),
        ('workspaces', '0011_personas_y_espacios_a_la_empresa'),
    ]

    operations = [
        migrations.RenameField(
            model_name='conversation', old_name='space', new_name='workspace',
        ),
    ]

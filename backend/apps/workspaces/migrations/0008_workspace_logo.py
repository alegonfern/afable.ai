"""El logo del Workspace.

No existía en ningún modelo —tampoco en `Organization`— y hace falta para que el selector
pueda decir en qué empresa se está trabajando sin obligar a leer el nombre: quien tiene dos
Workspaces los distingue de un vistazo por la marca.

Vacío es lo normal y no un caso de error: sin logo cargado, la pantalla dibuja un monograma
con la inicial y un color derivado del slug.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspaces', '0007_quitar_task'),
    ]

    operations = [
        migrations.AddField(
            model_name='workspace',
            name='logo',
            field=models.ImageField(blank=True, null=True, upload_to='workspace_logos/'),
        ),
    ]

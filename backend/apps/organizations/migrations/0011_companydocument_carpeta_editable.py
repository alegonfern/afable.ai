"""El documento vive en una carpeta y sabe si su texto se puede editar.

Escrita a mano: las migraciones generadas dentro del contenedor quedan de root.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('archivos', '0001_initial'),
        ('organizations', '0010_companydocument_sesion'),
    ]

    operations = [
        migrations.AddField(
            model_name='companydocument',
            name='carpeta',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='documentos', to='archivos.carpeta',
            ),
        ),
        migrations.AddField(
            model_name='companydocument',
            name='editable',
            field=models.BooleanField(default=False),
        ),
    ]

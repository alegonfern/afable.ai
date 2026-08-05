"""Un documento puede restringirse.

Nace en `False`: nada de lo que ya existía cambia de visibilidad.

Escrita a mano: las migraciones generadas dentro del contenedor quedan de root.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0012_backfill_editable'),
    ]

    operations = [
        migrations.AddField(
            model_name='companydocument',
            name='restringido',
            field=models.BooleanField(default=False),
        ),
    ]

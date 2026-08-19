"""Un documento puede pertenecer a una Sesión.

Los archivos de una Sesión son `CompanyDocument` y no un modelo propio, así heredan la
extracción de texto, el indexado semántico y el alcance de los agentes.

Escrita a mano: las migraciones generadas dentro del contenedor quedan de root.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('sesiones', '0001_initial'),
        ('organizations', '0009_companydocument_external_id_companydocument_source_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='companydocument',
            name='sesion',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                related_name='archivos', to='sesiones.sesion',
            ),
        ),
    ]

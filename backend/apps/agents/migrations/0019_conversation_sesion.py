"""Una conversación puede vivir en una Sesión.

Escrita a mano: las migraciones generadas dentro del contenedor quedan de root.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('sesiones', '0001_initial'),
        ('agents', '0018_automation_schedule_config_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='conversation',
            name='sesion',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='conversations', to='sesiones.sesion',
            ),
        ),
    ]

"""Lo que hace que la Sesión sirva para algo: instrucciones para sus agentes, agente
por defecto y habilidades por defecto.

Escrita a mano: las migraciones generadas dentro del contenedor quedan de root.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0019_conversation_sesion'),
        ('sesiones', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='sesion',
            name='instrucciones_para_agentes',
            field=models.TextField(
                blank=True,
                help_text='Lo ven todos los agentes que trabajen en esta Sesion.',
            ),
        ),
        migrations.AddField(
            model_name='sesion',
            name='agente_por_defecto',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='sesiones_por_defecto', to='agents.agent',
            ),
        ),
        migrations.AddField(
            model_name='sesion',
            name='habilidades_por_defecto',
            field=models.ManyToManyField(blank=True, related_name='sesiones', to='agents.skill'),
        ),
    ]

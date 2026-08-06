"""Un Disparador puede publicar en una Sesión, no solo mandar un correo.

Es lo que cierra el principio de los Pods —"todo lo que un humano puede hacer, un agente
también puede hacerlo"— que estaba a medias: el agente ejecutaba, pero solo si alguien
apretaba ▷, y el resultado se iba por correo a una sola persona. Ahora abre una conversación
en el trabajo del equipo sin que nadie se lo pida, y si corresponde deja la tarea anotada.

`notify_email` pasa a admitir vacío: con una Sesión puesta, exigir un correo obligaría a
mandar un mail que nadie pidió. Que no haya NINGÚN destino se rechaza más arriba.

`Conversation.autonoma` marca las que abrió el agente por su cuenta. Sin la marca, en el feed
se leerían como si alguien las hubiera escrito, y "lo escribió una persona" contra "lo trajo
un agente solo" es justo la diferencia que hay que poder ver.
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
            model_name='automation',
            name='sesion',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='automatizaciones', to='sesiones.sesion',
            ),
        ),
        migrations.AddField(
            model_name='automation',
            name='crear_tarea',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='automation',
            name='agent',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='automations', to='agents.agent',
            ),
        ),
        migrations.AlterField(
            model_name='automation',
            name='notify_email',
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.AddField(
            model_name='conversation',
            name='autonoma',
            field=models.BooleanField(default=False),
        ),
    ]

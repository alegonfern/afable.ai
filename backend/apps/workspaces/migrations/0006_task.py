"""Tareas del Espacio.

Escrita a mano y no con `makemigrations`: las migraciones generadas dentro del
contenedor quedan de root y no se pueden tocar desde el host.
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('agents', '0018_automation_schedule_config_and_more'),
        ('workspaces', '0005_space_space_unico_slug_de_espacio_por_workspace'),
    ]

    operations = [
        migrations.CreateModel(
            name='Task',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField(
                    blank=True,
                    help_text='Lo que hay que hacer. Si la toma un agente, esto es su instruccion.',
                )),
                ('state', models.CharField(
                    choices=[('pendiente', 'Pendiente'), ('en_curso', 'En curso'), ('lista', 'Lista')],
                    default='pendiente', max_length=12,
                )),
                ('resultado', models.TextField(blank=True)),
                ('resultado_error', models.CharField(blank=True, max_length=500)),
                ('ejecutada_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('agent', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='tareas', to='agents.agent',
                )),
                ('assignee', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='tareas_asignadas', to=settings.AUTH_USER_MODEL,
                )),
                ('created_by', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to=settings.AUTH_USER_MODEL,
                )),
                ('space', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='tasks', to='workspaces.space',
                )),
            ],
            options={
                'verbose_name': 'Tarea',
                'verbose_name_plural': 'Tareas',
                'db_table': 'workspace_tasks',
                'ordering': ['-created_at'],
            },
        ),
    ]

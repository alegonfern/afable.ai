"""Sesiones, sus miembros y sus Tareas.

Escrita a mano: las migraciones generadas dentro del contenedor quedan de root y no
se pueden editar desde el host.
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('agents', '0018_automation_schedule_config_and_more'),
        # La tabla vieja de tareas se borra antes de crear la nueva.
        ('workspaces', '0007_quitar_task'),
    ]

    operations = [
        migrations.CreateModel(
            name='Sesion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120)),
                ('slug', models.SlugField(max_length=140)),
                ('description', models.TextField(blank=True, help_text='De que se trata esta Sesion.')),
                ('icon', models.CharField(blank=True, help_text='Emoji de la tarjeta.', max_length=8)),
                ('visibility', models.CharField(
                    choices=[
                        ('abierta', 'Abierta — cualquiera del Workspace entra'),
                        ('restringida', 'Restringida — solo quien se invite'),
                    ],
                    default='abierta', max_length=16,
                )),
                ('archivada', models.BooleanField(default=False)),
                ('archivada_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to=settings.AUTH_USER_MODEL,
                )),
                ('workspace', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='sesiones', to='workspaces.workspace',
                )),
            ],
            options={
                'verbose_name': 'Sesión',
                'verbose_name_plural': 'Sesiones',
                'db_table': 'sesiones',
                'ordering': ['archivada', 'name'],
            },
        ),
        migrations.CreateModel(
            name='SesionMiembro',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(
                    choices=[('miembro', 'Miembro'), ('editor', 'Editor')],
                    default='miembro', max_length=12,
                )),
                ('joined_at', models.DateTimeField(auto_now_add=True)),
                ('sesion', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='miembros', to='sesiones.sesion',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='sesiones_miembro', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Miembro de Sesión',
                'verbose_name_plural': 'Miembros de Sesión',
                'db_table': 'sesion_miembros',
                'ordering': ['user__first_name', 'user__email'],
            },
        ),
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
                ('sesion', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='tasks', to='sesiones.sesion',
                )),
            ],
            options={
                'verbose_name': 'Tarea',
                'verbose_name_plural': 'Tareas',
                'db_table': 'sesion_tasks',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddField(
            model_name='sesion',
            name='members',
            field=models.ManyToManyField(
                related_name='sesiones', through='sesiones.SesionMiembro',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddConstraint(
            model_name='sesion',
            constraint=models.UniqueConstraint(
                fields=('workspace', 'slug'), name='unico_slug_de_sesion_por_workspace',
            ),
        ),
        migrations.AddConstraint(
            model_name='sesionmiembro',
            constraint=models.UniqueConstraint(
                fields=('sesion', 'user'), name='una_vez_por_sesion',
            ),
        ),
    ]

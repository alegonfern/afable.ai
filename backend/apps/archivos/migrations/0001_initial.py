"""Carpetas y versiones.

Escrita a mano: las migraciones generadas dentro del contenedor quedan de root.
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('agents', '0019_conversation_sesion'),
        ('organizations', '0010_companydocument_sesion'),
    ]

    operations = [
        migrations.CreateModel(
            name='Carpeta',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120)),
                ('slug', models.SlugField(max_length=140)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to=settings.AUTH_USER_MODEL,
                )),
                ('organization', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='carpetas', to='organizations.organization',
                )),
                ('parent', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name='hijas', to='archivos.carpeta',
                )),
            ],
            options={
                'verbose_name': 'Carpeta',
                'verbose_name_plural': 'Carpetas',
                'db_table': 'archivos_carpetas',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Version',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('numero', models.PositiveIntegerField(help_text='1, 2, 3… en orden de escritura.')),
                ('contenido', models.TextField(blank=True)),
                ('origen', models.CharField(
                    choices=[('persona', 'Una persona'), ('agente', 'Un agente'), ('sistema', 'El sistema')],
                    default='persona', max_length=12,
                )),
                ('mensaje', models.CharField(
                    blank=True, help_text='Qué se cambió y por qué, en una línea.', max_length=300,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('agente', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='versiones_escritas', to='agents.agent',
                )),
                ('autor', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='versiones_escritas', to=settings.AUTH_USER_MODEL,
                )),
                ('document', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='versiones', to='organizations.companydocument',
                )),
            ],
            options={
                'verbose_name': 'Versión',
                'verbose_name_plural': 'Versiones',
                'db_table': 'archivos_versiones',
                'ordering': ['-numero'],
            },
        ),
        migrations.AddConstraint(
            model_name='carpeta',
            constraint=models.UniqueConstraint(
                fields=('organization', 'parent', 'name'), name='una_carpeta_por_nombre_y_lugar',
            ),
        ),
        migrations.AddConstraint(
            model_name='version',
            constraint=models.UniqueConstraint(
                fields=('document', 'numero'), name='un_numero_por_documento',
            ),
        ),
    ]

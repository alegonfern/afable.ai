"""Permisos por carpeta y por archivo.

Restringir es la excepción: los dos campos nacen en `False`, así que nada de lo que ya
existía cambia de visibilidad al aplicar esto.

Escrita a mano: las migraciones generadas dentro del contenedor quedan de root.
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('organizations', '0012_backfill_editable'),
        ('archivos', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='carpeta',
            name='restringida',
            field=models.BooleanField(
                default=False,
                help_text='Si esta en True, solo entran las personas con permiso.',
            ),
        ),
        migrations.CreateModel(
            name='Permiso',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nivel', models.CharField(
                    choices=[('lectura', 'Puede ver'), ('edicion', 'Puede editar')],
                    default='lectura', max_length=10,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('carpeta', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name='permisos', to='archivos.carpeta',
                )),
                ('document', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                    related_name='permisos', to='organizations.companydocument',
                )),
                ('otorgado_por', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to=settings.AUTH_USER_MODEL,
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='permisos_de_archivos', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Permiso',
                'verbose_name_plural': 'Permisos',
                'db_table': 'archivos_permisos',
                'ordering': ['user__first_name', 'user__email'],
            },
        ),
        migrations.AddConstraint(
            model_name='permiso',
            constraint=models.UniqueConstraint(
                condition=models.Q(('carpeta__isnull', False)),
                fields=('carpeta', 'user'), name='un_permiso_por_carpeta_y_persona',
            ),
        ),
        migrations.AddConstraint(
            model_name='permiso',
            constraint=models.UniqueConstraint(
                condition=models.Q(('document__isnull', False)),
                fields=('document', 'user'), name='un_permiso_por_documento_y_persona',
            ),
        ),
        migrations.AddConstraint(
            model_name='permiso',
            constraint=models.CheckConstraint(
                check=models.Q(
                    models.Q(('carpeta__isnull', False), ('document__isnull', True)),
                    models.Q(('carpeta__isnull', True), ('document__isnull', False)),
                    _connector='OR',
                ),
                name='el_permiso_es_de_una_carpeta_o_de_un_documento',
            ),
        ),
    ]

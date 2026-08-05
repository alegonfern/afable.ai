"""Un permiso sin persona vale para todo el Workspace.

Dar acceso a un equipo de veinte personas eran veinte permisos cargados a mano, uno por
uno. Con `user` nulo alcanza uno: "que lo vea todo el equipo, pero que solo Ana y Beto lo
editen" pasa de veintidós filas a tres.

Los dos únicos por item existen porque en Postgres dos filas con `user` nulo NO chocan
contra un UNIQUE que incluya esa columna — sin ellos se podrían acumular varios permisos
de Workspace sobre la misma carpeta, con niveles distintos y sin forma de saber cuál manda.
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('archivos', '0002_permisos'),
    ]

    operations = [
        migrations.AlterField(
            model_name='permiso',
            name='user',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                related_name='permisos_de_archivos', to=settings.AUTH_USER_MODEL,
            ),
        ),
        # Los dos de antes se rehacen para que solo apliquen a permisos con persona.
        migrations.RemoveConstraint(
            model_name='permiso', name='un_permiso_por_carpeta_y_persona',
        ),
        migrations.RemoveConstraint(
            model_name='permiso', name='un_permiso_por_documento_y_persona',
        ),
        migrations.AddConstraint(
            model_name='permiso',
            constraint=models.UniqueConstraint(
                condition=models.Q(('carpeta__isnull', False), ('user__isnull', False)),
                fields=('carpeta', 'user'), name='un_permiso_por_carpeta_y_persona',
            ),
        ),
        migrations.AddConstraint(
            model_name='permiso',
            constraint=models.UniqueConstraint(
                condition=models.Q(('document__isnull', False), ('user__isnull', False)),
                fields=('document', 'user'), name='un_permiso_por_documento_y_persona',
            ),
        ),
        migrations.AddConstraint(
            model_name='permiso',
            constraint=models.UniqueConstraint(
                condition=models.Q(('carpeta__isnull', False), ('user__isnull', True)),
                fields=('carpeta',), name='un_permiso_de_workspace_por_carpeta',
            ),
        ),
        migrations.AddConstraint(
            model_name='permiso',
            constraint=models.UniqueConstraint(
                condition=models.Q(('document__isnull', False), ('user__isnull', True)),
                fields=('document',), name='un_permiso_de_workspace_por_documento',
            ),
        ),
    ]

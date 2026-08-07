"""El paso final: se va el Workspace-empresa y el Espacio toma su nombre.

Corre al final a propósito: para acá, `payments`, `sesiones` y `agents` ya soltaron sus
llaves al modelo viejo, así que borrarlo no arrastra nada.

Queda `Empresa → Workspace → Sesión`. El Espacio no desaparece como idea —sigue siendo un
contenedor con su gente y su conocimiento—, sólo deja de llamarse de una manera distinta a
lo que es.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('workspaces', '0011_personas_y_espacios_a_la_empresa'),
        ('payments', '0004_la_empresa_es_la_que_paga'),
        ('sesiones', '0003_la_sesion_vive_en_un_workspace'),
        ('agents', '0021_la_conversacion_es_de_un_workspace'),
    ]

    operations = [
        # Primero se va el viejo: su tabla se llama `workspaces` y el Espacio la necesita.
        migrations.DeleteModel(name='Workspace'),
        migrations.RenameModel(old_name='Space', new_name='Workspace'),
        migrations.AlterModelTable(name='workspace', table='workspaces'),
        migrations.AlterModelOptions(
            name='workspace',
            options={
                'ordering': ['name'],
                'verbose_name': 'Workspace',
                'verbose_name_plural': 'Workspaces',
            },
        ),
    ]

"""Las Tareas se van del Espacio a la Sesión.

El pendiente es del trabajo (la Sesión), no del contenedor de permisos (el Espacio).
Se borra la tabla y se crea de nuevo en `apps.sesiones` en vez de moverla con
`SeparateDatabaseAndState`: `workspace_tasks` nació hoy mismo, no está en producción
y no tiene una sola fila en ninguna base — mover el estado del ORM entre apps para
preservar cero registros sería complejidad sin beneficio.

Escrita a mano: las migraciones generadas dentro del contenedor quedan de root.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('workspaces', '0006_task'),
    ]

    operations = [
        migrations.DeleteModel(name='Task'),
    ]

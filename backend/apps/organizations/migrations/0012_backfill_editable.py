"""Marca como editables los documentos de texto que ya existían.

`editable` nació con `default=False`, así que todo lo cargado antes quedó de solo
lectura — incluidos los `.txt` y `.md`, que sí se pueden editar. Esto lo corrige una vez.

La lógica se copia de `services.documentos.es_editable` en vez de importarla: una
migración tiene que seguir haciendo lo mismo dentro de diez versiones, y para eso no
puede depender de código que va a cambiar.
"""
from django.db import migrations

CONTENT_TYPES = (
    'text/plain', 'text/markdown', 'text/x-markdown', 'text/csv',
    'application/json', 'text/html',
)
EXTENSIONES = ('.md', '.markdown', '.txt', '.csv', '.json', '.html')


def marcar(apps, schema_editor):
    CompanyDocument = apps.get_model('organizations', 'CompanyDocument')
    for doc in CompanyDocument.objects.all().iterator():
        ct = (doc.content_type or '').split(';')[0].strip().lower()
        titulo = (doc.title or '').lower()
        nombre_archivo = (doc.file.name or '').lower() if doc.file else ''
        editable = (
            ct in CONTENT_TYPES
            or ct.startswith('text/')
            or titulo.endswith(EXTENSIONES)
            or nombre_archivo.endswith(EXTENSIONES)
        )
        if editable and not doc.editable:
            doc.editable = True
            doc.save(update_fields=['editable'])


def deshacer(apps, schema_editor):
    """Nada que deshacer: el estado anterior era 'todo en False', que es el default."""


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0011_companydocument_carpeta_editable'),
    ]

    operations = [
        migrations.RunPython(marcar, deshacer),
    ]

"""
Primera migracion de las fuentes de conocimiento: la extension `vector` y la
tabla de fragmentos.

Escrita a mano y no con `makemigrations` a proposito: las migraciones generadas
dentro del contenedor quedan de root y no se pueden tocar desde el host.
"""
import pgvector.django
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('organizations', '0009_companydocument_external_id_companydocument_source_and_more'),
    ]

    operations = [
        # CREATE EXTENSION IF NOT EXISTS vector. La imagen de la base es
        # pgvector/pgvector:pg16, asi que la extension esta disponible; esto la
        # habilita en la base concreta.
        pgvector.django.VectorExtension(),
        migrations.CreateModel(
            name='Fragmento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('orden', models.PositiveIntegerField(help_text='Posicion del fragmento dentro del documento, desde 0.')),
                ('texto', models.TextField()),
                ('embedding', pgvector.django.VectorField(dimensions=768)),
                ('modelo', models.CharField(max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('document', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='fragmentos', to='organizations.companydocument',
                )),
                ('organization', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='fragmentos', to='organizations.organization',
                )),
            ],
            options={
                'ordering': ['document_id', 'orden'],
            },
        ),
        migrations.AddConstraint(
            model_name='fragmento',
            constraint=models.UniqueConstraint(
                fields=('document', 'orden'), name='fragmento_unico_por_documento',
            ),
        ),
        migrations.AddIndex(
            model_name='fragmento',
            index=models.Index(fields=['organization'], name='fragmento_org_idx'),
        ),
        migrations.AddIndex(
            model_name='fragmento',
            index=pgvector.django.HnswIndex(
                ef_construction=64, fields=['embedding'], m=16,
                name='fragmento_embedding_hnsw', opclasses=['vector_cosine_ops'],
            ),
        ),
    ]

"""
Indexa los documentos de la empresa para la busqueda semantica.

Sin argumentos indexa solo lo que falta (nunca indexado, o indexado con otro
modelo de embeddings). Es el comando que hay que correr una vez despues de
instalar esto, porque los documentos que ya estaban cargados no pasaron por
ningun enganche de indexado.
"""
from django.core.management.base import BaseCommand

from services.embeddings import EmbeddingsNoDisponibles, disponible, modelo_activo
from services.indexing import documentos_sin_indexar, indexar_documento


class Command(BaseCommand):
    help = 'Trocea y vectoriza los documentos de la empresa para la busqueda semantica.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--todo', action='store_true',
            help='Reindexa TODOS los documentos, no solo los que faltan.',
        )
        parser.add_argument(
            '--empresa', type=int, default=None,
            help='id de la Organization a indexar (por defecto, todas).',
        )

    def handle(self, *args, **opciones):
        if not disponible(recargar=True):
            self.stderr.write(self.style.ERROR(
                f'No se puede vectorizar con «{modelo_activo()}». Revisa que Ollama este '
                f'corriendo y que el modelo este bajado (`ollama pull {modelo_activo()}`), '
                f'o pon EMBEDDINGS_PROVIDER=ninguno para apagar la busqueda semantica.'
            ))
            return

        org = None
        if opciones['empresa']:
            from apps.organizations.models import Organization
            org = Organization.objects.filter(pk=opciones['empresa']).first()
            if org is None:
                self.stderr.write(self.style.ERROR(
                    f'No existe una empresa con id={opciones["empresa"]}.'
                ))
                return

        if opciones['todo']:
            from apps.organizations.models import CompanyDocument
            docs = CompanyDocument.objects.exclude(extracted_text='')
            if org is not None:
                docs = docs.filter(organization=org)
        else:
            docs = documentos_sin_indexar(org)

        docs = list(docs)
        if not docs:
            self.stdout.write('No hay documentos por indexar.')
            return

        self.stdout.write(
            f'Indexando {len(docs)} documento(s) con «{modelo_activo()}»...'
        )
        fragmentos = fallados = 0
        for doc in docs:
            try:
                n = indexar_documento(doc)
            except EmbeddingsNoDisponibles as e:
                # Si el proveedor se cae a mitad del backfill, no tiene sentido
                # seguir intentando con los que quedan.
                self.stderr.write(self.style.ERROR(f'Se corto el indexado: {e}'))
                break
            except Exception as e:
                fallados += 1
                self.stderr.write(self.style.WARNING(
                    f'  «{doc.title}» (id={doc.pk}) fallo: {e}'
                ))
                continue
            fragmentos += n
            self.stdout.write(f'  «{doc.title}» → {n} fragmento(s)')

        resumen = f'Listo: {fragmentos} fragmento(s) indexados.'
        if fallados:
            resumen += f' {fallados} documento(s) fallaron.'
        self.stdout.write(self.style.SUCCESS(resumen))

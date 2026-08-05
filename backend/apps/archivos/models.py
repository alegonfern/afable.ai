"""
Archivos: carpetas, versiones y la historia de cada documento.

El documento en sí sigue siendo `organizations.CompanyDocument` — es lo que ya tiene el
archivo, el texto extraído, el indexado semántico y el alcance de los agentes. Lo que
esta app agrega alrededor es lo que le faltaba para poder trabajar de verdad con él:
**dónde está** (una carpeta) y **cómo llegó a ser lo que es** (sus versiones).

## Por qué una app aparte y no todo junto en `organizations`

`organizations` es la app del enfoque anterior, la que se va reemplazando. Meterle un
sistema de archivos completo adentro profundizaría la dependencia justo de lo que se
quiere retirar. `CompanyDocument` se queda ahí porque moverlo es una migración enorme y
media aplicación lo usa; lo nuevo nace afuera.

## Qué se versiona, y qué no

Se versiona el **texto**. Un `.md` o un `.txt` —y todo lo que Afable escriba— se puede
editar y volver atrás. Un PDF, un Word o un Excel se guardan y se leen, pero no se
editan en el lugar: no hay forma honesta de escribirles de vuelta sin romperles el
formato. Para esos, "mejorá este documento" produce un documento NUEVO.
"""
from django.conf import settings
from django.db import models
from django.utils.text import slugify


class Carpeta(models.Model):
    """Una carpeta del árbol de archivos de la empresa.

    Es un árbol simple con `parent`: sin `parent` es una carpeta de la raíz. No se usa
    una librería de árboles (mptt y compañía) a propósito — un árbol de carpetas de una
    pyme tiene decenas de nodos, no miles, y `parent` con un `select_related` alcanza.
    """

    organization = models.ForeignKey(
        'organizations.Organization', on_delete=models.CASCADE, related_name='carpetas',
    )
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140)
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True, related_name='hijas',
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'archivos_carpetas'
        ordering = ['name']
        constraints = [
            # Dos carpetas con el mismo nombre en el mismo lugar es un error de quien
            # las crea, no algo que haya que tolerar y desambiguar despues.
            models.UniqueConstraint(
                fields=['organization', 'parent', 'name'],
                name='una_carpeta_por_nombre_y_lugar',
            ),
        ]
        verbose_name = 'Carpeta'
        verbose_name_plural = 'Carpetas'

    def __str__(self):
        return self.ruta()

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:140] or 'carpeta'
        super().save(*args, **kwargs)

    def ruta(self):
        """`Contabilidad / 2026 / Facturas`, para el rastro de migas."""
        partes, nodo, vistos = [], self, set()
        while nodo is not None and nodo.pk not in vistos:
            vistos.add(nodo.pk)
            partes.append(nodo.name)
            nodo = nodo.parent
        return ' / '.join(reversed(partes))

    def ancestros(self):
        """De la raíz hasta el padre. Con guarda de ciclo: un `parent` mal puesto
        colgaría la petición para siempre en vez de fallar."""
        cadena, nodo, vistos = [], self.parent, {self.pk}
        while nodo is not None and nodo.pk not in vistos:
            vistos.add(nodo.pk)
            cadena.append(nodo)
            nodo = nodo.parent
        return list(reversed(cadena))

    def es_descendiente_de(self, otra):
        """Si `otra` está en la cadena de padres de esta carpeta.

        Es lo que evita mover una carpeta dentro de sí misma o de una de sus hijas, que
        dejaría un ciclo y con él una rama huérfana del árbol.
        """
        if otra is None:
            return False
        for ancestro in self.ancestros():
            if ancestro.pk == otra.pk:
                return True
        return False


# Quién escribió una versión: una persona, un agente, o el sistema.
ORIGEN_PERSONA = 'persona'
ORIGEN_AGENTE = 'agente'
ORIGEN_SISTEMA = 'sistema'
ORIGENES = [
    (ORIGEN_PERSONA, 'Una persona'),
    (ORIGEN_AGENTE, 'Un agente'),
    (ORIGEN_SISTEMA, 'El sistema'),
]


class Version(models.Model):
    """Una versión del texto de un documento.

    Cada escritura crea una, con quién la hizo y por qué. Es lo que permite ver qué
    cambió, quién lo cambió y volver atrás — y es lo que hace que dejar a un agente
    editar documentos sea razonable en vez de temerario: nada se pierde, todo se ve.

    La versión 1 es el estado con el que el documento entró al sistema (lo subido o lo
    que la IA escribió al crearlo), así que un documento siempre tiene al menos una y
    "volver al original" es siempre posible.
    """

    document = models.ForeignKey(
        'organizations.CompanyDocument', on_delete=models.CASCADE, related_name='versiones',
    )
    numero = models.PositiveIntegerField(help_text='1, 2, 3… en orden de escritura.')
    contenido = models.TextField(blank=True)

    origen = models.CharField(max_length=12, choices=ORIGENES, default=ORIGEN_PERSONA)
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='versiones_escritas',
    )
    # Cuando la escribió un agente. Se guardan los dos: quién pidió (autor) y quién
    # escribió (agente), porque para revisar un cambio hacen falta ambos.
    agente = models.ForeignKey(
        'agents.Agent', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='versiones_escritas',
    )
    mensaje = models.CharField(
        max_length=300, blank=True,
        help_text='Qué se cambió y por qué, en una línea.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'archivos_versiones'
        ordering = ['-numero']
        constraints = [
            models.UniqueConstraint(
                fields=['document', 'numero'], name='un_numero_por_documento',
            ),
        ]
        verbose_name = 'Versión'
        verbose_name_plural = 'Versiones'

    def __str__(self):
        return f'{self.document_id} v{self.numero}'

    @property
    def quien(self):
        """Cómo se firma esta versión en la pantalla."""
        if self.origen == ORIGEN_AGENTE and self.agente:
            return f'@{self.agente.handle or self.agente.name}'
        if self.autor:
            return self.autor.get_full_name() or self.autor.email
        return 'el sistema'

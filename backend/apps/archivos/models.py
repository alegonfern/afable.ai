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

    # Restringir es la EXCEPCION, no el default: sin esto todo lo que ya existia se
    # habria vuelto invisible de golpe, y los agentes habrian perdido lo que leian.
    # Sin restringir, la carpeta la ve y la edita cualquier miembro del Workspace.
    restringida = models.BooleanField(
        default=False,
        help_text='Si esta en True, solo entran las personas con permiso.',
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


# ── Permisos ──────────────────────────────────────────────────────────────────

NIVEL_LECTURA = 'lectura'
NIVEL_EDICION = 'edicion'
NIVELES = [
    (NIVEL_LECTURA, 'Puede ver'),
    (NIVEL_EDICION, 'Puede editar'),
]
ORDEN_DE_NIVELES = {NIVEL_LECTURA: 0, NIVEL_EDICION: 1}


class Permiso(models.Model):
    """Quien entra a una carpeta o a un documento restringido, y con que nivel.

    ## El modelo, en una frase

    **Restringir es la excepcion.** Sin nada restringido, los archivos de la empresa los
    ve y los edita cualquier miembro del Workspace — que es como venia funcionando. Al
    marcar una carpeta o un archivo como restringido, ahi si hace falta un permiso.

    ## La regla de herencia: manda la restriccion mas cercana

    Para saber si alguien entra a un archivo se camina hacia arriba: archivo, su carpeta,
    la carpeta de esa carpeta. **La primera restriccion que se encuentra decide**, y hace
    falta un permiso en ESE nodo (o mas arriba). Si no hay ninguna restriccion en toda la
    cadena, entra cualquier miembro.

    Se eligio "la mas cercana manda" en vez de sumar permisos de todos los niveles porque
    es lo que se puede explicar en una linea en la pantalla: "esta carpeta es restringida,
    solo estas personas". Un modelo aditivo obliga a que la gente calcule.

    Dos excepciones, siempre: el administrador del Workspace y quien creo el archivo. El
    primero porque no puede administrar lo que no ve; el segundo porque perder acceso a lo
    que uno mismo subio no se entiende de ninguna manera.
    """

    # Uno de los dos, nunca los dos: el permiso es de una carpeta o de un documento.
    carpeta = models.ForeignKey(
        Carpeta, on_delete=models.CASCADE, null=True, blank=True, related_name='permisos',
    )
    document = models.ForeignKey(
        'organizations.CompanyDocument', on_delete=models.CASCADE,
        null=True, blank=True, related_name='permisos',
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='permisos_de_archivos',
    )
    nivel = models.CharField(max_length=10, choices=NIVELES, default=NIVEL_LECTURA)

    otorgado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'archivos_permisos'
        ordering = ['user__first_name', 'user__email']
        constraints = [
            models.UniqueConstraint(
                fields=['carpeta', 'user'], name='un_permiso_por_carpeta_y_persona',
                condition=models.Q(carpeta__isnull=False),
            ),
            models.UniqueConstraint(
                fields=['document', 'user'], name='un_permiso_por_documento_y_persona',
                condition=models.Q(document__isnull=False),
            ),
            # Un permiso que no apunta a nada, o que apunta a las dos cosas, es un error
            # de programacion: mejor que la base lo rechace que descubrirlo despues.
            models.CheckConstraint(
                check=(
                    models.Q(carpeta__isnull=False, document__isnull=True)
                    | models.Q(carpeta__isnull=True, document__isnull=False)
                ),
                name='el_permiso_es_de_una_carpeta_o_de_un_documento',
            ),
        ]
        verbose_name = 'Permiso'
        verbose_name_plural = 'Permisos'

    def __str__(self):
        sobre = self.carpeta or self.document
        return f'{self.user} — {self.nivel} sobre {sobre}'

    @property
    def puede_editar(self):
        return self.nivel == NIVEL_EDICION

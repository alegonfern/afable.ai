"""Quién puede ver y editar un archivo o una carpeta.

Toda pregunta sobre acceso a archivos se responde acá y en ningún otro lado, por lo mismo
que los permisos del Workspace viven en un solo archivo: una regla repetida en seis
vistas es una regla que en la séptima se olvida — y acá lo que se olvida es una fuga.

## El modelo, en tres reglas

1. **Restringir es la excepción.** Sin nada restringido, los archivos de la empresa los ve
   y los edita cualquier miembro del Workspace. Es como venía funcionando, y es lo que
   permite que introducir permisos no vuelva invisible de golpe todo lo que ya existía.
2. **Manda la restricción más cercana.** Se camina hacia arriba —archivo, su carpeta, la
   carpeta de esa carpeta— y la primera restricción que aparece decide: hace falta un
   permiso en ESE nodo o más arriba. Si no hay ninguna restricción en la cadena, entra
   cualquier miembro.
3. **Dos siempre entran**: el administrador del Workspace (no puede administrar lo que no
   ve) y quien subió el archivo (perder acceso a lo propio no se entiende de ninguna
   manera).

## El permiso de brocha gorda

Un `Permiso` **sin persona** (`user=None`) vale para cualquier miembro del Workspace. Es
lo que hace practicable el caso más común de una empresa: "que lo vea todo el equipo, pero
que solo estos dos lo editen". Sin él, eso eran tantos permisos como personas, cargados de
a uno — y una lista así nadie la mantiene al día.

Cuando alguien tiene los dos, **gana el más alto**: un permiso personal está puesto a
propósito para esa persona, así que no puede restarle lo que el Workspace ya le daba.

## La propiedad que este módulo existe para garantizar

**Nadie puede usar un agente para leer lo que él mismo no puede leer.** El alcance de
documentos del agente se intersecta con lo que ve la persona que está conversando (ver
`_build_onboarding_context`). Sin eso, restringir un archivo sería teatro: bastaría con
preguntárselo al agente.
"""
from django.db.models import Q

from apps.workspaces.models import ROLE_ADMIN

from .models import NIVEL_EDICION, NIVEL_LECTURA, ORDEN_DE_NIVELES, Carpeta, Permiso


def _es_admin(membership):
    return membership is not None and membership.role == ROLE_ADMIN


def _mejor(permisos):
    """El nivel más alto de una lista de permisos, o None si está vacía.

    Sirve para juntar el permiso personal con el de todo el Workspace: quien tiene lectura
    por ser del equipo y edición a nombre propio, edita.
    """
    niveles = [p.nivel for p in permisos if p.nivel in ORDEN_DE_NIVELES]
    if not niveles:
        return None
    return max(niveles, key=lambda n: ORDEN_DE_NIVELES[n])


def _mios_y_del_workspace(user):
    """Filtro de los permisos que le sirven a esta persona: el suyo y el del Workspace."""
    return Q(user=user) | Q(user__isnull=True)


def _cadena_de_carpetas(carpeta):
    """La carpeta y sus ancestros, de la más cercana a la raíz."""
    if carpeta is None:
        return []
    return [carpeta] + list(reversed(carpeta.ancestros()))


def nivel_sobre_carpeta(user, carpeta, membership=None):
    """El nivel de acceso a una carpeta: 'edicion', 'lectura' o None.

    None significa que no la ve — ni siquiera sabe que existe.
    """
    if carpeta is None:
        # La raíz no se restringe: es el contenedor de todo lo no restringido.
        return NIVEL_EDICION
    if _es_admin(membership):
        return NIVEL_EDICION

    cadena = _cadena_de_carpetas(carpeta)
    # De la más cercana hacia arriba: la primera restringida decide.
    for nodo in cadena:
        if not nodo.restringida:
            continue
        if nodo.created_by_id and user is not None and nodo.created_by_id == user.id:
            return NIVEL_EDICION
        return _mejor(Permiso.objects.filter(_mios_y_del_workspace(user), carpeta=nodo))

    # Ninguna restringida en toda la cadena.
    return NIVEL_EDICION


def nivel_sobre_documento(user, doc, membership=None):
    """El nivel de acceso a un documento: 'edicion', 'lectura' o None."""
    if _es_admin(membership):
        return NIVEL_EDICION
    if doc.uploaded_by_id and user is not None and doc.uploaded_by_id == user.id:
        return NIVEL_EDICION

    if doc.restringido:
        return _mejor(Permiso.objects.filter(_mios_y_del_workspace(user), document=doc))

    # Sin restricción propia, hereda la de su carpeta.
    return nivel_sobre_carpeta(user, doc.carpeta, membership)


def puede_ver(user, doc, membership=None):
    return nivel_sobre_documento(user, doc, membership) is not None


def puede_editar(user, doc, membership=None):
    nivel = nivel_sobre_documento(user, doc, membership)
    return nivel is not None and ORDEN_DE_NIVELES[nivel] >= ORDEN_DE_NIVELES[NIVEL_EDICION]


def carpetas_visibles(user, org, membership=None):
    """Las carpetas de la empresa que esta persona ve.

    Se resuelve en Python y no en una sola consulta a propósito: la herencia es un
    recorrido hacia arriba y expresarla en SQL exigiría una recursiva difícil de leer. Un
    árbol de carpetas de una pyme tiene decenas de nodos, así que el costo es irrelevante
    y lo que se gana es que la regla se pueda auditar leyéndola.
    """
    todas = list(Carpeta.objects.filter(organization=org).select_related('parent'))
    if _es_admin(membership):
        return todas

    # Si no hay ninguna restringida, se ven todas — el caso común, y sin consultas extra.
    if not any(c.restringida for c in todas):
        return todas

    por_id = {c.pk: c for c in todas}
    con_permiso = set(
        Permiso.objects.filter(_mios_y_del_workspace(user), carpeta__organization=org)
        .values_list('carpeta_id', flat=True)
    )

    def alcanza(carpeta):
        nodo, vistos = carpeta, set()
        while nodo is not None and nodo.pk not in vistos:
            vistos.add(nodo.pk)
            if nodo.restringida:
                propia = nodo.created_by_id and user is not None and nodo.created_by_id == user.id
                return bool(propia or nodo.pk in con_permiso)
            nodo = por_id.get(nodo.parent_id)
        return True

    return [c for c in todas if alcanza(c)]


def documentos_visibles(user, org, membership=None):
    """Los documentos de la empresa que esta persona ve, como QuerySet.

    Es lo que se intersecta con el alcance del agente: la garantía de que preguntarle a un
    agente no sirve para saltear un permiso.
    """
    from apps.organizations.models import CompanyDocument

    qs = CompanyDocument.objects.filter(organization=org)
    if _es_admin(membership):
        return qs

    visibles = {c.pk for c in carpetas_visibles(user, org, membership)}
    hay_restringidos = (
        CompanyDocument.objects.filter(organization=org, restringido=True).exists()
        or Carpeta.objects.filter(organization=org, restringida=True).exists()
    )
    if not hay_restringidos:
        return qs

    con_permiso = set(
        Permiso.objects.filter(_mios_y_del_workspace(user), document__organization=org)
        .values_list('document_id', flat=True)
    )

    return qs.filter(
        # Lo propio, siempre.
        Q(uploaded_by=user)
        # Restringido a mano: hace falta un permiso sobre el documento.
        | Q(restringido=True, id__in=con_permiso)
        # Sin restricción propia: hereda la carpeta, que tiene que ser visible. En la raíz
        # (`carpeta=None`) no hay nada que heredar, así que se ve.
        | Q(restringido=False, carpeta__isnull=True)
        | Q(restringido=False, carpeta_id__in=visibles)
    ).distinct()


def _permisos_de(carpeta=None, document=None):
    return (
        Permiso.objects.filter(carpeta=carpeta) if carpeta is not None
        else Permiso.objects.filter(document=document)
    )


def serializar_permisos(carpeta=None, document=None):
    """Con quién está compartido, para la pantalla.

    El de todo el Workspace queda FUERA de esta lista y se informa aparte
    (`nivel_del_workspace`): meterlo como una fila más, sin nombre, se leería como una
    persona rara — y lo que hay que entender es que es de otra clase.
    """
    return [
        {
            'user': p.user_id,
            'name': p.user.get_full_name() or p.user.email,
            'email': p.user.email,
            'nivel': p.nivel,
        }
        for p in _permisos_de(carpeta, document).exclude(user__isnull=True).select_related('user')
    ]


def nivel_del_workspace(carpeta=None, document=None):
    """El nivel que tiene todo el Workspace sobre el ítem, o None si no tiene."""
    p = _permisos_de(carpeta, document).filter(user__isnull=True).first()
    return p.nivel if p else None

"""El único lugar donde se crea una notificación.

Embudo único a propósito, como los permisos: si avisar se hiciera desde cada vista, la
regla de "a nadie se le avisa de lo suyo" habría que acordarse de aplicarla cada vez, y
basta olvidarla una vez para que la campana se llene de ruido propio y se deje de mirar.
"""
import logging

from .models import Notificacion

logger = logging.getLogger(__name__)


def avisar(destinatarios, *, tipo, titulo, detalle='', enlace='', organization=None,
           excepto=None):
    """Crea una notificación para cada destinatario. Devuelve cuántas creó.

    `excepto` es quien provocó el hecho: nunca se le avisa a sí mismo.
    """
    ids_excluidos = set()
    if excepto is not None:
        ids_excluidos.add(getattr(excepto, 'id', excepto))

    unicos = {}
    for u in destinatarios or []:
        if u is None:
            continue
        uid = getattr(u, 'id', u)
        if uid and uid not in ids_excluidos:
            unicos[uid] = u

    if not unicos:
        return 0

    try:
        Notificacion.objects.bulk_create([
            Notificacion(
                user_id=uid, organization=organization, tipo=tipo,
                titulo=titulo[:200], detalle=detalle[:300], enlace=enlace[:300],
            )
            for uid in unicos
        ])
    except Exception:
        # ⚠️ Avisar NUNCA puede voltear la acción que lo provocó. Que se pierda un aviso
        # es molesto; que no se pueda mandar un mensaje porque falló el aviso es un error
        # que la persona no entiende y no puede sortear.
        logger.exception('No se pudieron crear notificaciones (%s)', tipo)
        return 0

    return len(unicos)


def avisar_del_mensaje(conversation, autor, texto):
    """Alguien escribió en un hilo de una Sesión: se le avisa al resto del equipo.

    Un hilo personal no avisa a nadie — no hay a quién. Lo que hace multiplayer a una
    Sesión es que lo escrito ahí llegue solo, sin que los demás tengan que pasar a mirar.
    """
    sesion = getattr(conversation, 'sesion', None)
    if sesion is None:
        return 0

    from .models import TIPO_MENSAJE

    quien = autor.get_full_name() or autor.email
    organizacion = (
        sesion.workspace.organization if getattr(sesion, 'workspace_id', None) else None
    )
    return avisar(
        list(sesion.members.all()),
        tipo=TIPO_MENSAJE,
        titulo=f'{quien} escribió en {sesion.name}',
        detalle=(texto or '').strip()[:200],
        enlace=f'/app/sesiones/{sesion.slug}',
        organization=organizacion,
        excepto=autor,
    )


def avisar_de_la_tarea(tarea, autor):
    """A quien le asignaron una tarea. A nadie más: una tarea tiene un responsable."""
    if tarea.assignee_id is None:
        return 0

    from .models import TIPO_TAREA

    sesion = tarea.sesion
    organizacion = (
        sesion.workspace.organization if getattr(sesion, 'workspace_id', None) else None
    )
    return avisar(
        [tarea.assignee],
        tipo=TIPO_TAREA,
        titulo=f'Te asignaron «{tarea.title}»',
        detalle=f'En la Sesión {sesion.name}',
        enlace=f'/app/sesiones/{sesion.slug}',
        organization=organizacion,
        excepto=autor,
    )

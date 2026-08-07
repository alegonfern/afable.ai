"""Quién puede entrar a una conversación, y con los permisos de quién se le contesta.

Hasta acá una conversación era de UNA persona: se buscaba con `user=request.user`, así que
un compañero podía ver un hilo compartido en una Sesión pero al intentar responder recibía
un 404. Compartir era "dejar leer", no "dejar entrar".

⭐ **La regla que no se puede romper: la respuesta se arma con lo que alcanza QUIEN
PREGUNTA, no quien abrió el hilo.** Sin esto, un hilo compartido sería la forma más
cómoda de leer lo que uno no puede ver: basta que alguien con más acceso lo abra y me
invite. Rompería la única propiedad que el producto promete sobre permisos —nadie puede
usar un agente para alcanzar lo que él no alcanza— y la rompería sin dejar rastro.
"""

from rest_framework.exceptions import NotFound

from .models import Conversation


def hilo_para_escribir(user, conversation_id):
    """La conversación en la que esta persona tiene derecho a escribir, o 404.

    Dos caminos, y ninguno más:

    - **Un hilo personal** (sin Sesión) es de quien lo abrió. Nadie más entra.
    - **Un hilo de una Sesión** es del equipo: entra cualquiera que alcance esa Sesión.

    404 y no 403 en los dos casos, igual que en el resto de la app: para quien está
    afuera, el hilo no existe.
    """
    conversacion = (
        Conversation.objects
        .select_related('sesion', 'agent')
        .filter(pk=conversation_id)
        .first()
    )
    if conversacion is None:
        raise NotFound('Conversación no encontrada.')

    if conversacion.user_id == user.id:
        return conversacion

    if conversacion.sesion_id and _alcanza_la_sesion(user, conversacion.sesion):
        return conversacion

    raise NotFound('Conversación no encontrada.')


def _alcanza_la_sesion(user, sesion):
    """Si esa persona entra a la Sesión. Se apoya en el embudo que ya existe."""
    from apps.sesiones.permissions import sesiones_visibles

    from apps.workspaces.permissions import membership_por_organizacion

    organizacion = sesion.workspace.organization if sesion.workspace_id else None
    membership = membership_por_organizacion(user, organizacion)
    if membership is None:
        return False
    return sesiones_visibles(membership).filter(pk=sesion.pk).exists()


def le_hablan_a_la_ia(texto, hay_mas_de_uno):
    """Si el agente tiene que contestar este mensaje.

    En un hilo de una persona contesta siempre: es un chat con la IA. En uno donde hay
    equipo, **contesta sólo cuando lo mencionan** — un asistente que responde cada mensaje
    de una conversación entre cinco personas la vuelve inusable, y es el error que hace que
    los bots terminen apagados. El resto del tiempo escucha: lo que se dijo queda como
    contexto para cuando lo llamen.
    """
    if not hay_mas_de_uno:
        return True
    return '@' in (texto or '')

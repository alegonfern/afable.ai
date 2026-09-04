"""Qué le conviene hacer ahora a esta persona, calculado sin gastar un solo token.

## La regla que gobierna este módulo

> **Recomendar es una consulta. Solo actuar cuesta.**

Todo lo que hay acá sale del estado real de la empresa con consultas a la base. Ninguna
recomendación llama al modelo. La IA entra recién cuando la persona toca una — y ahí la
llamada vale la pena, porque la pidió.

Es la diferencia entre un producto que acompaña y uno que quema presupuesto de fondo. Un
informe automático cada mañana es una llamada al modelo por empresa y por día que nadie
pidió; esto es una consulta SQL que se hace cuando alguien abre el chat.

## Por qué no se guarda el estado

Igual que en `apps/workspaces/primeros_pasos.py`, del que este módulo toma la idea: nada se
marca como «listo». Cada recomendación se recalcula. Guardarlo haría que el producto siga
felicitando a quien borró su única conexión, que es justo cuando hay que avisarle.

## En qué se diferencia de los primeros pasos

`primeros_pasos` es **la primera hora** y es **solo del administrador**: sus seis pasos son
cosas que nadie más puede hacer, y se cierra cuando la empresa arrancó.

Esto no caduca y le habla a cada persona según lo que **ella** puede hacer. Un miembro no
puede conectar un sistema, pero sí puede subir lo suyo y preguntarle a sus documentos, y
ese consejo le sirve el mes tres igual que el primer día.
"""
from apps.workspaces.models import ROLE_ADMIN, ROLE_EDITOR

# Cuántas se muestran. Tres es el tope porque son atajos en una pantalla que la persona
# vino a usar para otra cosa: una lista larga de consejos deja de leerse y pasa a ser
# decoración que hay que esquivar.
TOPE = 3


def _puede_administrar(membership):
    return membership is not None and membership.role == ROLE_ADMIN


def _puede_editar(membership):
    return membership is not None and membership.role in (ROLE_ADMIN, ROLE_EDITOR)


def para(organization, usuario, membership=None):
    """Las recomendaciones de esta persona, de la más urgente a la menos.

    Cada una trae `mensaje`: lo que se manda al chat cuando la tocan. No es una ruta a otra
    pantalla a propósito — el chat es la puerta del producto, y una recomendación que te
    saca de la conversación te obliga a volver.
    """
    from apps.archivos.models import PUBLICACION_PENDIENTE, Carpeta, SolicitudDePublicacion
    from apps.agents.models import Conversation
    from apps.organizations.models import CompanyDocument, SystemConnection
    from apps.workspaces.models import Membership
    from services.estructura_inicial import carpeta_personal
    from services.propuestas_de_agente import carpetas_con_material

    salida = []

    hay_carpetas = Carpeta.objects.filter(organization=organization, personal=False).exists()
    hay_documentos = CompanyDocument.objects.filter(organization=organization).exists()

    # 1. Sin estructura no hay nada más que hacer: es la puerta.
    if not hay_carpetas and _puede_administrar(membership):
        salida.append({
            'clave': 'armar_empresa',
            'texto': 'Armemos su empresa',
            'detalle': 'Todavía no hay dónde guardar nada.',
            'mensaje': 'Quiero empezar. Ayúdame a armar mi empresa en Afable.',
        })

    # 2. Una carpeta con material y sin agente es valor esperando a ser recogido.
    for carpeta in carpetas_con_material(organization, usuario, membership)[:2]:
        salida.append({
            'clave': f'agente_{carpeta.pk}',
            'texto': f'¿Le armo el agente de {carpeta.name}?',
            'detalle': f'Ya tiene documentos suficientes para responder sobre eso.',
            'mensaje': f'Quiero un agente para la carpeta {carpeta.name}.',
        })

    # 3. Lo que el equipo quiere publicar y está esperando. Va alto: alguien está trabado.
    if _puede_editar(membership):
        pendientes = SolicitudDePublicacion.objects.filter(
            destino__organization=organization, estado=PUBLICACION_PENDIENTE,
        ).count()
        if pendientes:
            salida.append({
                'clave': 'aprobar_publicaciones',
                'texto': f'Hay {pendientes} archivo{"s" if pendientes > 1 else ""} esperando su visto bueno',
                'detalle': 'Su equipo quiere aportarlos a la carpeta de la empresa.',
                'mensaje': '¿Qué archivos están esperando que los apruebe?',
            })

    # 4. Documentos cargados que nadie preguntó todavía. Es el «ajá» sin ocurrir.
    if hay_documentos and not Conversation.objects.filter(
        agent__organization=organization,
    ).exists():
        salida.append({
            'clave': 'primera_pregunta',
            'texto': 'Pregúntele algo a lo que ya subió',
            'detalle': 'Hay documentos cargados y nadie les ha preguntado nada.',
            'mensaje': '¿Qué me puedes decir sobre los documentos que ya tengo cargados?',
        })

    # 5. Solo. El pilar del equipo, dicho cuando corresponde y no como eslogan.
    if _puede_editar(membership):
        if Membership.objects.filter(organization=organization).count() == 1:
            salida.append({
                'clave': 'invitar',
                'texto': 'Invite a alguien de su equipo',
                'detalle': 'Por ahora está usted solo acá.',
                'mensaje': 'Quiero invitar a alguien de mi equipo.',
            })

    # 6. Sin herramientas. Va último a propósito: el producto entra por documentos y
    #    equipo, y empujar la integración antes de tiempo es el orden de la estrategia
    #    anterior.
    if _puede_editar(membership) and not SystemConnection.objects.filter(
        organization=organization, is_active=True,
    ).exists():
        salida.append({
            'clave': 'conectar',
            'texto': 'Conecte una herramienta que ya usa',
            'detalle': 'Su Odoo, su base de datos, su Drive.',
            'mensaje': 'Quiero conectar una herramienta que ya uso.',
        })

    # 7. Su propia carpeta vacía. Le habla a quien no puede hacer nada de lo anterior.
    if not salida and not hay_documentos:
        mia = carpeta_personal(organization, usuario)
        if not CompanyDocument.objects.filter(carpeta=mia).exists():
            salida.append({
                'clave': 'subir_lo_mio',
                'texto': 'Suba lo suyo',
                'detalle': 'Lo que ponga en su carpeta es privado hasta que decida compartirlo.',
                'mensaje': 'Quiero subir un documento y preguntarle.',
            })

    # 8. Cuando no falta nada, no se inventa una recomendación. Un producto que siempre
    #    tiene algo que decirte deja de decir algo cuando importa.
    return salida[:TOPE]


def hay_agentes(organization):
    """Si la empresa ya tiene al menos un agente. Lo usa la pantalla para saber si el
    recorrido de arranque terminó."""
    from apps.agents.models import Agent

    return Agent.objects.filter(organization=organization, is_active=True).exists()

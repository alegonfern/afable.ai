"""Los cuatro agentes que toda empresa tiene desde el día cero.

⭐ **Por qué esto vive acá y no en un comando.** Estaba en un `manage.py seed_agentes_base`
que había que acordarse de correr — y las empresas creadas después de la última corrida
nacían **sin un solo agente**. Quien se registraba abría la galería y no tenía con quién
hablar: la pantalla que vende el producto, vacía. Da igual cuánto valga el chat si el
primer día no hay nadie del otro lado.

Ahora los siembra `Organization.crear_para_dueno`, que es el único camino por el que nace
una empresa. El comando quedó para reparar las que ya existían vacías.

Se invocan con `@` en cualquier conversación:

    @afable       busca en todo lo que la empresa tiene conectado
    @claude       el modelo pelado, sin datos de la empresa de por medio
    @analisis     cruza varias fuentes antes de contestar
    @constructor  ayuda a escribir y afinar las instrucciones de otros agentes

Idempotente por `(organization, handle)`. **NO pisa las instrucciones si el agente ya
existe**: alguien pudo haberlas editado, y un seed que revienta el trabajo ajeno es peor
que no correr.
"""
import logging

logger = logging.getLogger(__name__)

CIERRE = (
    '\n\nHable en español neutro, tratando de usted. No invente cifras: si el dato '
    'no está en las fuentes que puede consultar, dígalo con todas sus letras.'
)

AGENTES_BASE = [
    {
        'handle': 'afable',
        'icon': '✳️',
        'accent': '#586AD0',
        'name': 'Afable',
        'description': 'Busca en todo lo que la empresa tiene conectado.',
        'instructions': (
            'Usted es el agente general de la empresa. Antes de contestar, busque en las '
            'fuentes conectadas del Espacio: conexiones a sistemas y documentos. Responda '
            'citando de dónde sacó cada dato — el nombre del documento o del sistema — para '
            'que quien lea pueda ir a verificarlo.' + CIERRE
        ),
        'area': 'general',
    },
    {
        'handle': 'claude',
        'icon': '◻️',
        'accent': '#D9A388',
        'name': 'Claude',
        'description': 'El modelo directo, sin datos de la empresa de por medio.',
        'instructions': (
            'Conteste con su propio conocimiento, sin consultar los sistemas ni los '
            'documentos de la empresa. Sirve para redactar, traducir, resumir un texto '
            'pegado en el chat o pensar en voz alta. Si la pregunta necesita datos internos, '
            'dígalo y sugiera mencionar a @afable.' + CIERRE
        ),
        'area': 'general',
    },
    {
        'handle': 'analisis',
        'icon': '🔎',
        'accent': '#3E8E7E',
        'name': 'Análisis profundo',
        'description': 'Cruza varias fuentes antes de contestar.',
        'instructions': (
            'Usted se toma el trabajo largo. Frente a una pregunta, primero enumere qué '
            'necesita averiguar, consulte todas las fuentes que hagan falta — no se conforme '
            'con la primera —, cruce los resultados y recién ahí conteste. Cierre siempre con '
            'el nivel de confianza que tiene y qué le faltó para estar seguro.' + CIERRE
        ),
        'area': 'general',
    },
    {
        'handle': 'constructor',
        'icon': '🛠️',
        'accent': '#C77D3E',
        'name': 'Constructor de agentes',
        'description': 'Ayuda a escribir y afinar las instrucciones de otros agentes.',
        'instructions': (
            'Usted ayuda a construir agentes. Cuando alguien describa lo que necesita, '
            'devuelva una propuesta concreta: nombre, para qué sirve, qué fuentes debería '
            'mirar y las instrucciones redactadas y listas para pegar. Pregunte lo mínimo '
            'indispensable — una o dos cosas — antes de proponer; no interrogue.' + CIERRE
        ),
        'area': 'general',
    },
]


def sembrar_en(organization):
    """Deja los agentes base en esa empresa. Devuelve cuántos creó.

    ⚠️ **No puede voltear el registro.** Si esto falla, la persona se queda sin agentes
    —molesto, y reparable con el comando— pero si además la dejara sin cuenta, no tendría
    ni cómo volver a intentarlo.
    """
    from .models import Agent

    creados = 0
    try:
        for base in AGENTES_BASE:
            _, nuevo = Agent.objects.get_or_create(
                organization=organization,
                handle=base['handle'],
                defaults={
                    'name': base['name'],
                    'description': base['description'],
                    'instructions': base['instructions'],
                    'area': base['area'],
                    'icon': base.get('icon', ''),
                    'accent': base.get('accent', ''),
                    'is_active': True,
                },
            )
            creados += 1 if nuevo else 0
    except Exception:
        logger.exception('No se pudieron sembrar los agentes base en %s', organization.pk)
    return creados


# Las caras de los agentes que trae Afable, incluidos los de rol que siembran otros
# comandos. Está acá y no en cada seed porque es una sola cosa —cómo se ven los agentes
# oficiales— y repartida en cuatro archivos se desincroniza sola.
CARAS_CONOCIDAS = {
    'afable': ('✳️', '#586AD0'),
    'claude': ('◻️', '#D9A388'),
    'analisis': ('🔎', '#3E8E7E'),
    'constructor': ('🛠️', '#C77D3E'),
    'afable-assistant': ('✳️', '#586AD0'),
    'agente-de-contabilidad': ('📊', '#3E8E7E'),
    'agente-de-facturacion': ('🧾', '#4F7CC4'),
    'agente-sii': ('🇨🇱', '#C25B5B'),
    'cientifico-de-datos': ('📈', '#9A7BC8'),
}


def poner_caras(organization=None):
    """Le pone su cara a los agentes oficiales que todavía no la tienen.

    ⚠️ Solo rellena lo VACÍO. Si alguien eligió un emoji para su agente, pisárselo sería
    exactamente el tipo de seed que revienta el trabajo ajeno.
    """
    from .models import Agent

    qs = Agent.objects.all()
    if organization is not None:
        qs = qs.filter(organization=organization)

    tocados = 0
    for agente in qs.filter(handle__in=CARAS_CONOCIDAS):
        icono, color = CARAS_CONOCIDAS[agente.handle]
        campos = []
        if not agente.icon:
            agente.icon = icono
            campos.append('icon')
        if not agente.accent:
            agente.accent = color
            campos.append('accent')
        if campos:
            agente.save(update_fields=campos)
            tocados += 1
    return tocados


# Handles cortos para los agentes oficiales. `@agente-de-contabilidad` es impronunciable
# y nadie lo escribe: en un producto donde se invoca con `@`, el handle ES la interfaz.
HANDLES_CORTOS = {
    'agente-de-contabilidad': 'contabilidad',
    'agente-de-facturacion': 'facturacion',
    'agente-sii': 'sii',
    'cientifico-de-datos': 'datos',
}


def acortar_handles(organization=None):
    """Acorta los handles largos de los agentes oficiales. Devuelve cuántos cambió.

    ⚠️ **Solo si nadie lo mencionó todavía.** Un handle es la identidad con la que se lo
    invoca: cambiarlo rompe las menciones ya escritas en los hilos, y un `@` que dejó de
    resolver es un mensaje del pasado que cambia de significado. Por eso se comprueba
    mensaje por mensaje antes de tocar nada, y el que ya se usó se queda como está.
    """
    from .models import Agent, Message

    qs = Agent.objects.filter(handle__in=HANDLES_CORTOS)
    if organization is not None:
        qs = qs.filter(organization=organization)

    cambiados = 0
    for agente in qs:
        nuevo = HANDLES_CORTOS[agente.handle]
        if Message.objects.filter(content__icontains=f'@{agente.handle}').exists():
            logger.info('No se acorta @%s: ya está mencionado en un hilo', agente.handle)
            continue
        if Agent.objects.filter(organization=agente.organization, handle=nuevo).exists():
            continue
        agente.handle = nuevo
        agente.save(update_fields=['handle'])
        cambiados += 1
    return cambiados

"""La ficha del agente: qué hace, a qué alcanza y qué preguntarle.

⭐ **Por qué existe.** La galería decía el nombre y una frase. Con eso una pyme no puede
decidir a cuál preguntarle, ni sabe si el agente está viendo sus documentos o contestando
de memoria — y un agente del que no se sabe qué alcanza no se usa para nada que importe.

Tres cosas, en el orden en que se necesitan:

1. **A qué alcanza**: los documentos y los sistemas concretos, por su nombre. Es la
   diferencia entre "una IA" y "la IA de mi empresa".
2. **Qué preguntarle**: tres ejemplos escritos con SUS fuentes. Una caja de texto vacía es
   la peor pantalla para alguien que nunca usó esto.
3. **Qué ya hizo**: respuestas y documentos. La prueba de que sirve — y lo que un día
   justifica pagar por uno.
"""
from apps.workspaces.permissions import alcance_de_agente

# Cuántas fuentes se nombran. Más que esto deja de ser información y pasa a ser un
# inventario: quien lee quiere saber "¿está viendo mis precios?", no la lista completa.
MAX_FUENTES = 6


def _preguntas(agent, documentos, conexiones):
    """Tres ejemplos concretos, armados con lo que este agente realmente alcanza.

    Genéricas ("hazme un resumen") no enseñan nada. La gracia es que digan el nombre del
    documento de la empresa: ahí se entiende de golpe qué es esto.
    """
    ejemplos = []
    if conexiones:
        ejemplos.append(f'¿Cómo vamos este mes según {conexiones[0]}?')
    for doc in documentos[:2]:
        ejemplos.append(f'¿Qué dice «{doc}»?')
    if documentos:
        ejemplos.append('Resume lo más importante de nuestros documentos y déjalo guardado.')

    if not ejemplos:
        # Sin fuentes todavía: se dice lo que SÍ puede hacer hoy, en vez de prometer.
        ejemplos = [
            'Redáctame una propuesta para un cliente nuevo.',
            'Explícame en palabras simples qué conviene revisar este mes.',
        ]
    return ejemplos[:3]


def ficha_de(agent, organization):
    """Todo lo que la pantalla del agente necesita mostrar."""
    from apps.organizations.models import CompanyDocument, SystemConnection

    ids_conexiones, ids_documentos = alcance_de_agente(agent)

    docs = CompanyDocument.objects.filter(organization=organization)
    if ids_documentos is not None:
        docs = docs.filter(id__in=ids_documentos)
    conns = SystemConnection.objects.filter(organization=organization, is_active=True)
    if ids_conexiones is not None:
        conns = conns.filter(id__in=ids_conexiones)

    titulos = list(docs.order_by('title').values_list('title', flat=True)[:MAX_FUENTES])
    sistemas = list(conns.order_by('name').values_list('name', flat=True)[:MAX_FUENTES])

    # Lo que este agente ya produjo. Se cuenta lo REGISTRADO, no se estima: es la prueba
    # de que trabajó, y una cifra inflada la desarma entera.
    from apps.agents.models import Message

    respuestas = Message.objects.filter(agent=agent, role='assistant')
    documentos_escritos = sum(
        len(m.artefactos or []) for m in respuestas.only('artefactos')
    )

    return {
        'alcance': {
            'documentos': titulos,
            'total_documentos': docs.count(),
            'sistemas': sistemas,
            'total_sistemas': conns.count(),
            # Sin fuentes contesta de memoria, y hay que decirlo: alguien que cree que le
            # está respondiendo con sus datos toma decisiones sobre arena.
            'sin_fuentes': not titulos and not sistemas,
        },
        'preguntas': _preguntas(agent, titulos, sistemas),
        'trabajo': {
            'respuestas': respuestas.count(),
            'documentos': documentos_escritos,
            'ultima_vez': (
                respuestas.order_by('-created_at').values_list('created_at', flat=True).first()
            ),
        },
    }

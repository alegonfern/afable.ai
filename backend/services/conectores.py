"""El catálogo de conectores: qué es cada uno y qué se gana al conectarlo.

## Por qué esto es un catálogo y no una lista de nombres

Hasta ahora conectar algo era elegir de una lista de cinco palabras técnicas —«mssql»,
«postgresql»— y llenar credenciales. Eso funciona para quien ya sabe qué es cada cosa, que
es justamente la persona que este producto no tiene enfrente.

Cada ficha responde tres preguntas, en el orden en que se las hace alguien que no es
técnico: **qué trae**, **qué voy a poder preguntarle** y **qué agente aparece**. Un conector
que no puede contestar las tres no está listo para ofrecerse.

## «Conectores» en pantalla, «sistema operativo» en el pitch

Decidido el 31-08. El argumento de que Afable se vuelve el sistema operativo de la empresa
es bueno para vender y pésimo como rótulo: a un no técnico «sistema operativo de tu empresa»
no le dice nada, y «conecta tu Odoo» sí. Son dos audiencias y no tienen por qué compartir
vocabulario.

## Las dos reglas del usuario, que aquí se hacen código

1. **Cada conector crea su estructura de carpetas si no la tenía** (`carpeta`). Lo que entra
   por una herramienta necesita un lugar donde vivir, igual que lo que se sube a mano — y ese
   lugar es de donde después cuelga su agente.
2. **Un conector se desactiva, nunca se elimina.** Borrarlo se llevaría por delante la
   consistencia de lo que ya entró por él: documentos que quedan sin origen, agentes que
   apuntaban a algo que ya no está. Se apaga y deja de traer datos; lo que trajo se
   queda.

## Sobre `estado`

Los que dicen `pronto` **no están construidos**. Aparecen en el catálogo porque quien evalúa
Afable necesita ver hacia dónde va, pero se muestran como lo que son. Prometer un conector
que no existe se paga en la primera reunión en que alguien intenta usarlo.
"""

DISPONIBLE = 'disponible'
PRONTO = 'pronto'

# ⭐ Todo lo que se conecta es una HERRAMIENTA. No hay una categoría «sistemas» aparte:
# el ERP, el CRM, la base de datos, la facturación y WhatsApp entran todos por la misma
# puerta, y cada uno es una capacidad más que la empresa le suma a Afable. Separarlos en
# dos clases era vocabulario de la estrategia anterior, donde conectar el ERP era la
# entrada al producto; ahora la entrada son los documentos y el equipo.
#
# Lo que sí cambia entre una herramienta y otra es **cuánto se hunde**, y eso es un dato
# técnico, no una categoría que el usuario deba ver:
#   profunda — credenciales y escaneo del esquema (Odoo, SAP, una base de datos)
#   suave    — se acopla y listo (Drive, planillas, Slack, WhatsApp)
PROFUNDA = 'profunda'
SUAVE = 'suave'

CATALOGO = [
    {
        'clave': 'odoo',
        'nombre': 'Odoo',
        'profundidad': PROFUNDA,
        'estado': DISPONIBLE,
        'titular': 'Conecte su Odoo y opere desde Afable.',
        'que_trae': [
            'Sus clientes, productos, pedidos y facturas, en vivo.',
            'No copia nada: lee de su Odoo cada vez que pregunta.',
        ],
        'que_podra_preguntar': [
            '¿Cuánto facturamos este mes?',
            '¿Qué clientes tienen facturas vencidas?',
            '¿Qué productos se están quedando sin stock?',
        ],
        'agente': 'Un agente que consulta su Odoo y responde con los datos de hoy.',
        'carpeta': 'Odoo',
    },
    {
        'clave': 'mssql',
        'nombre': 'SAP Business One',
        'profundidad': PROFUNDA,
        'estado': DISPONIBLE,
        'titular': 'Traiga sus reportes de SAP y pregúnteles en español.',
        'que_trae': [
            'Las tablas de su SAP Business One, a través de SQL Server.',
            'Se escanea el esquema una vez para saber qué hay dónde.',
        ],
        'que_podra_preguntar': [
            '¿Cómo vienen las ventas contra el mes pasado?',
            '¿Qué documentos quedaron sin cerrar?',
        ],
        'agente': 'Un agente que arma los reportes que hoy le pide a alguien del área.',
        'carpeta': 'SAP',
    },
    {
        'clave': 'postgresql',
        'nombre': 'Base de datos',
        'profundidad': PROFUNDA,
        'estado': DISPONIBLE,
        'titular': 'Su propia base de datos, preguntada en español.',
        'que_trae': [
            'Cualquier base PostgreSQL a la que tenga acceso.',
            'Solo lectura: Afable nunca escribe en su base.',
        ],
        'que_podra_preguntar': [
            'Lo que hoy le pide a alguien que sepa escribir consultas.',
        ],
        'agente': 'Un agente que traduce sus preguntas a consultas y le explica el resultado.',
        'carpeta': 'Base de datos',
    },
    {
        'clave': 'csv',
        'nombre': 'Excel y CSV',
        'profundidad': SUAVE,
        'estado': DISPONIBLE,
        'titular': 'Sus planillas, sin dejar de ser planillas.',
        'que_trae': [
            'Los archivos que ya usa, con sus columnas y sus totales.',
            'Afable también las edita: cambiar una celda no lo devuelve a Excel.',
        ],
        'que_podra_preguntar': [
            '¿Qué cambió en esta planilla respecto de la del mes pasado?',
            'Súmame esta columna por sucursal.',
        ],
        'agente': 'Un agente que lee y corrige sus planillas sin romperles el formato.',
        'carpeta': 'Planillas',
    },
    {
        'clave': 'google_drive',
        'nombre': 'Google Drive',
        'profundidad': SUAVE,
        'estado': DISPONIBLE,
        'titular': 'Lo que ya está en su Drive, sin volver a subirlo.',
        'que_trae': [
            'Una carpeta de Drive, sincronizada sola.',
            'Si alguien edita un archivo allá, Afable lo relee.',
        ],
        'que_podra_preguntar': [
            '¿Qué decía el contrato que subimos en marzo?',
        ],
        'agente': 'Un agente sobre los documentos de esa carpeta.',
        'carpeta': 'Drive',
    },
    {
        'clave': 'hubspot',
        'nombre': 'HubSpot',
        'profundidad': PROFUNDA,
        'estado': PRONTO,
        'titular': 'Sus leads y su embudo, con alguien mirándolos.',
        'que_trae': [
            'Contactos, negocios y el estado de cada uno.',
        ],
        'que_podra_preguntar': [
            '¿Qué oportunidades se están enfriando?',
            '¿A quién no le hemos respondido esta semana?',
        ],
        'agente': 'Un agente que le avisa qué se está enfriando antes de que se pierda.',
        'carpeta': 'HubSpot',
    },
    {
        'clave': 'facturacion',
        'nombre': 'Facturación electrónica',
        'profundidad': PROFUNDA,
        'estado': PRONTO,
        'titular': 'Emita según sus clientes, sin salir de la conversación.',
        'que_trae': [
            'Sus documentos emitidos y recibidos.',
        ],
        'que_podra_preguntar': [
            '¿Qué facturas vencen esta semana?',
        ],
        'agente': 'Un agente que revisa lo emitido y avisa lo que falta cobrar.',
        'carpeta': 'Facturación',
    },
    {
        'clave': 'slack',
        'nombre': 'Slack y Teams',
        'profundidad': SUAVE,
        'estado': PRONTO,
        'titular': 'Hable con sus agentes donde ya trabaja el equipo.',
        'que_trae': [
            'Sus agentes, disponibles en los canales que ya usa.',
        ],
        'que_podra_preguntar': [
            'Lo mismo que acá, sin cambiar de ventana.',
        ],
        'agente': 'Los agentes que ya tiene, alcanzables desde el chat del equipo.',
        'carpeta': None,
    },
    {
        'clave': 'whatsapp',
        'nombre': 'WhatsApp',
        'profundidad': SUAVE,
        'estado': PRONTO,
        'titular': 'Los avisos importantes, en el teléfono.',
        'que_trae': [
            'Las notificaciones de sus agentes y disparadores.',
        ],
        'que_podra_preguntar': [
            'Por ahora avisa; conversar por WhatsApp viene después.',
        ],
        'agente': None,
        'carpeta': None,
    },
]

_POR_CLAVE = {c['clave']: c for c in CATALOGO}


def catalogo(solo_disponibles=False):
    if solo_disponibles:
        return [c for c in CATALOGO if c['estado'] == DISPONIBLE]
    return list(CATALOGO)


def ficha(clave):
    return _POR_CLAVE.get(clave)


def carpeta_del_conector(organization, clave, creado_por=None):
    """La carpeta donde vive lo que entra por ese conector. La crea si no existía.

    Es la primera regla del usuario hecha código. Devuelve `None` para los conectores que
    no traen documentos —Slack y WhatsApp llevan avisos hacia afuera, no traen material—
    porque crearles una carpeta vacía sería ensuciar el árbol con algo que nunca se llena.

    Cuelga de la carpeta de la empresa, no de la raíz: lo que entra por una herramienta
    conectada es de la empresa, no de una persona.
    """
    from apps.archivos.models import Carpeta

    datos = ficha(clave)
    if not datos or not datos.get('carpeta'):
        return None

    raiz = Carpeta.objects.filter(
        organization=organization, parent=None, name=organization.name,
    ).first()

    carpeta, _ = Carpeta.objects.get_or_create(
        organization=organization, parent=raiz, name=datos['carpeta'],
        defaults={'created_by': creado_por},
    )
    return carpeta

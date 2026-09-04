"""El agente no se configura: se propone.

Es la pieza que hace verdadera la frase «Afable reemplaza al implementador». El
implementador era, entre otras cosas, quien sabía **qué agente hacía falta**. Un formulario
en blanco que pide «instrucciones» le devuelve esa decisión al usuario que no es técnico,
que es justamente el que no puede tomarla — y el agente que sale de ahí no sirve, o peor,
nunca se llega a crear.

## La regla que gobierna todo esto

> ⛔ **Nunca un agente desde una pantalla en blanco. Siempre desde una carpeta que ya tiene
> algo adentro.**

Sin repositorio no hay agente. Si esto se relaja, los agentes vuelven a ser un producto
suelto y el orden del enfoque se rompe solo.

## El nombre lo escribe Afable, no la carpeta

Acá está la diferencia con «cada carpeta es un agente», que suena parecido y no lo es. Si
el agente se llamara como su carpeta, una carpeta llamada «cosas» daría un agente llamado
«cosas», y el repositorio entero heredaría los nombres improvisados de quien creó las
carpetas un martes apurado.

En cambio, **el nombre y la descripción salen de lo que hay adentro**: una carpeta «cosas»
con doce facturas produce un agente de facturación, bien nombrado. La persona acepta o
corrige, pero nunca parte de cero.

## Por qué hace falta material antes

Un agente sobre una carpeta vacía contesta que no sabe nada. Esa es la primera impresión
que hace que alguien no vuelva, así que se espera a que haya con qué trabajar
(`UMBRAL_DOCUMENTOS`). Es la misma razón por la que la propuesta aparece **después** de
subir cosas y no en el alta de la empresa.
"""
import json
import logging

logger = logging.getLogger(__name__)

# Cuántos documentos tiene que haber en la rama para que valga la pena proponer. Tres es
# poco a propósito: el objetivo es que la propuesta aparezca temprano, cuando la persona
# todavía está subiendo cosas y el impulso está vivo. Esperar a veinte es esperar a que se
# haya ido.
UMBRAL_DOCUMENTOS = 3

# Cuántos títulos se le muestran al modelo para que deduzca de qué trata la carpeta. Con
# quince alcanza para reconocer el patrón y no se paga un prompt largo por algo que se
# resuelve leyendo unos pocos nombres.
TITULOS_PARA_DEDUCIR = 15

INSTRUCCION = (
    'Mira los nombres de los archivos de una carpeta de una empresa y deduce qué agente de '
    'IA le serviría a esa empresa sobre ese material.\n\n'
    'Responde SOLO un JSON con estas claves, sin texto alrededor:\n'
    '- "nombre": cómo se llama el agente. Dos o tres palabras, en español, que digan de qué '
    'se ocupa. Nunca uses el nombre de la carpeta si es vago ("cosas", "varios", "nueva '
    'carpeta"): fíjate en los archivos.\n'
    '- "descripcion": una frase de lo que puede responder, dirigida a quien lo va a usar.\n'
    '- "instrucciones": cómo debe comportarse, en dos o tres frases. Sé concreto sobre qué '
    'mirar y qué responder con este material.\n'
    '- "icono": un solo emoji que lo represente.\n'
)


def _documentos_de(carpeta):
    from apps.organizations.models import CompanyDocument

    return CompanyDocument.objects.filter(carpeta__in=carpeta.rama())


def carpetas_con_material(org, usuario, membership=None):
    """Las carpetas que ya tienen con qué trabajar y todavía no tienen agente.

    Se filtra por lo que esa persona puede editar: proponerle un agente sobre una carpeta
    que no puede tocar sería ofrecerle algo que no va a poder aceptar — y de paso le
    revelaría que esa carpeta existe.
    """
    from apps.archivos.models import Carpeta
    from apps.archivos.permisos import NIVEL_EDICION, nivel_sobre_carpeta

    candidatas = []
    for carpeta in Carpeta.objects.filter(organization=org, personal=False):
        if carpeta.agentes.exists():
            continue
        if _documentos_de(carpeta).count() < UMBRAL_DOCUMENTOS:
            continue
        if nivel_sobre_carpeta(usuario, carpeta, membership) != NIVEL_EDICION:
            continue
        candidatas.append(carpeta)
    return candidatas


def _de_respaldo(carpeta):
    """Qué proponer cuando el modelo no está disponible o contesta cualquier cosa.

    Es peor que lo que redacta el modelo —vuelve a caer en el nombre de la carpeta— pero es
    mucho mejor que no proponer nada: sin esto, un problema con el proveedor de IA dejaría
    al producto entero sin su forma de crear agentes.
    """
    return {
        'nombre': carpeta.name,
        'descripcion': f'Responde sobre lo que hay en {carpeta.ruta()}.',
        'instrucciones': (
            f'Respondes sobre los documentos de la carpeta {carpeta.ruta()}. '
            'Cita siempre el documento del que sacaste la respuesta. '
            'Si algo no está en esos documentos, dilo en vez de suponerlo.'
        ),
        'icono': '📁',
        'de_respaldo': True,
    }


def redactar(carpeta):
    """Le pide al modelo el nombre, la descripción y las instrucciones del agente.

    Nunca levanta: si el modelo falla, contesta con texto que no es JSON, o devuelve algo
    incompleto, se cae al respaldo. Una propuesta imperfecta sirve; una excepción en medio
    de la pantalla de archivos, no.
    """
    titulos = list(
        _documentos_de(carpeta)
        .order_by('-created_at')
        .values_list('title', flat=True)[:TITULOS_PARA_DEDUCIR]
    )
    if not titulos:
        return _de_respaldo(carpeta)

    lista = '\n'.join(f'- {t}' for t in titulos)
    consulta = f'Carpeta: «{carpeta.name}»\nArchivos:\n{lista}'

    try:
        from services.agent_service import chat_direct, modelo_autonomo

        crudo = chat_direct(
            [{'role': 'user', 'content': consulta}],
            system_prompt=INSTRUCCION,
            # Nadie pidió esta propuesta: la paga la casa, así que va en el modelo
            # económico y no en el que la empresa tenga puesto para el chat.
            model=modelo_autonomo(),
            organization=carpeta.organization,
            motivo='propuesta_de_agente',
        )
        propuesta = _leer_json(crudo)
    except Exception:
        logger.exception('No se pudo redactar la propuesta de agente para %s', carpeta.pk)
        return _de_respaldo(carpeta)

    if not propuesta:
        return _de_respaldo(carpeta)

    respaldo = _de_respaldo(carpeta)
    return {
        'nombre': (propuesta.get('nombre') or respaldo['nombre']).strip()[:255],
        'descripcion': (propuesta.get('descripcion') or respaldo['descripcion']).strip(),
        'instrucciones': (propuesta.get('instrucciones') or respaldo['instrucciones']).strip(),
        'icono': (propuesta.get('icono') or '📁').strip()[:8],
        'de_respaldo': False,
    }


def _leer_json(texto):
    """El JSON del modelo, aunque venga envuelto en explicaciones o en un bloque de código."""
    if not texto:
        return None
    limpio = texto.strip()
    if limpio.startswith('```'):
        limpio = limpio.split('```')[1] if '```' in limpio[3:] else limpio[3:]
        if limpio.startswith('json'):
            limpio = limpio[4:]
    ini, fin = limpio.find('{'), limpio.rfind('}')
    if ini == -1 or fin <= ini:
        return None
    try:
        datos = json.loads(limpio[ini:fin + 1])
    except (ValueError, TypeError):
        return None
    return datos if isinstance(datos, dict) else None


def crear_desde_propuesta(carpeta, usuario, propuesta=None, membership=None):
    """Crea el agente de esa carpeta. Es el «aceptar» de la propuesta.

    Comprueba el permiso otra vez, con el mismo motor que la pantalla: entre que se mostró
    la propuesta y que la persona la aceptó, la carpeta pudo volverse restringida.
    """
    from apps.agents.models import Agent
    from apps.archivos.permisos import NIVEL_EDICION, nivel_sobre_carpeta

    if nivel_sobre_carpeta(usuario, carpeta, membership) != NIVEL_EDICION:
        raise PermissionError('No puedes crear un agente en esa carpeta.')

    ya = carpeta.agentes.first()
    if ya is not None:
        return ya

    datos = propuesta or redactar(carpeta)
    return Agent.objects.create(
        organization=carpeta.organization,
        carpeta=carpeta,
        name=datos['nombre'],
        description=datos.get('descripcion', ''),
        instructions=datos.get('instrucciones', ''),
        icon=datos.get('icono', ''),
        created_by=usuario,
    )

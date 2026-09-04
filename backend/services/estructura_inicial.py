"""La estructura de carpetas con la que arranca una empresa.

Es la pieza donde Afable deja de ser una carpeta vacía. Un usuario que no es técnico no
sabe qué carpetas necesita su empresa — y esa es exactamente la parte que antes ponía el
implementador. Acá esa decisión viene tomada, y sale del **rubro**: una constructora y una
consultora no necesitan lo mismo, así que proponer siempre el mismo árbol sería una
plantilla, no criterio.

## Las dos clases de carpeta

**`root` — la carpeta de la cuenta.** La información de la empresa, y de donde salen los
agentes. **La ve todo el equipo; solo los administradores la modifican.** En pantalla no se
llama «root»: se llama como la empresa, porque «root» es vocabulario de sistemas y no le
dice nada a quien nunca abrió una terminal.

**La carpeta de cada persona.** Una por usuario, y todo lo que hay adentro es privado. Ahí
trabaja con lo suyo hasta que decide aportarlo.

## Cómo se consiguen esos permisos sin tocar el motor

`apps/archivos/permisos.py` es lo más delicado del sistema y no hace falta moverlo:

- **`root`**: `restringida=True` más un `Permiso` de brocha gorda (`user=None`) con nivel
  **lectura**. Todo el equipo lee; los administradores editan porque el motor los deja
  entrar siempre (`_es_admin`).
- **Remuneraciones**: `restringida=True` y ningún permiso. Solo entran los administradores.
- **La carpeta personal**: `restringida=True`, sin permisos, con `created_by` puesto. El
  motor le da edición a quien la creó, así que su dueño entra y nadie más.

## Publicar

Nadie publica por su cuenta: se **pide** publicar y un administrador o editor aprueba, con
un destino que quien aprueba puede corregir. Eso vive en `apps/archivos/publicaciones.py`;
acá solo se arma el terreno.
"""
from django.db import transaction

# Lo que toda empresa tiene, sea cual sea su rubro. El orden es el de la pantalla.
BASE = [
    ('Información de la empresa', []),
    ('Contabilidad', ['Conciliación', 'Impuestos']),
    ('Facturación', []),
    ('Ventas', []),
    ('Clientes', []),
    ('Proveedores', []),
    ('Bancos y tesorería', []),
    ('Legal', []),
    ('Personas', []),
    ('Procesos internos', []),
]

# Lo propio de cada rubro, que se suma a BASE. Son cinco porque cinco preguntas se pueden
# contestar en el onboarding sin que parezca un formulario; si hicieran falta veinte, la
# elección volvería a ser trabajo del usuario.
POR_RUBRO = {
    'servicios': [
        ('Proyectos', []),
        ('Propuestas', []),
        ('Contratos', []),
    ],
    'comercio': [
        ('Inventario', []),
        ('Sucursales', []),
        ('Postventa', []),
    ],
    'manufactura': [
        ('Producción', []),
        ('Materias primas', []),
        ('Calidad', []),
        ('Mantenimiento', []),
    ],
    'construccion': [
        ('Obras', []),
        ('Subcontratos', []),
        ('Permisos', []),
        ('Estados de pago', []),
    ],
    'general': [
        ('Inventario', []),
        ('Postventa', []),
    ],
}

RUBROS = [
    ('servicios', 'Servicios o consultoría'),
    ('comercio', 'Comercio o retail'),
    ('manufactura', 'Manufactura o producción'),
    ('construccion', 'Construcción'),
    ('general', 'Otro'),
]

# Dentro de `root` pero solo para administradores. Van aparte de Personas a propósito:
# el reglamento interno lo lee cualquiera, las liquidaciones no.
SOLO_ADMINISTRADORES = [
    ('Remuneraciones', []),
    ('Directorio y socios', []),
]

# ⚠️ La carpeta personal NO puede llamarse igual para todos: `Carpeta` tiene una
# constraint `una_carpeta_por_nombre_y_lugar` (organization + parent + name), así que
# dos «Mi espacio» en la raíz de la misma empresa chocan y la segunda persona se queda
# sin carpeta. Se nombra con la persona, y la pantalla es la que dice «Mi espacio»
# cuando el que mira es su dueño.


def _crear(organization, nombre, creado_por, parent=None, restringida=False):
    from apps.archivos.models import Carpeta

    carpeta, _ = Carpeta.objects.get_or_create(
        organization=organization, parent=parent, name=nombre,
        defaults={'created_by': creado_por, 'restringida': restringida},
    )
    return carpeta


def _lectura_para_todo_el_equipo(carpeta):
    """El permiso de brocha gorda que hace a `root` legible por cualquiera."""
    from apps.archivos.models import NIVEL_LECTURA, Permiso

    Permiso.objects.get_or_create(
        carpeta=carpeta, user=None, defaults={'nivel': NIVEL_LECTURA},
    )


@transaction.atomic
def crear_estructura(organization, rubro='general', creado_por=None):
    """Arma `root` y su contenido. Devuelve la carpeta `root`.

    Es idempotente: correrlo dos veces no duplica nada, porque todo pasa por
    `get_or_create`. Importa, porque el onboarding se puede reintentar.
    """
    root = _crear(organization, organization.name, creado_por, restringida=True)
    _lectura_para_todo_el_equipo(root)

    arbol = BASE + POR_RUBRO.get(rubro, POR_RUBRO['general'])
    for nombre, hijas in arbol:
        carpeta = _crear(organization, nombre, creado_por, parent=root)
        for hija in hijas:
            _crear(organization, hija, creado_por, parent=carpeta)

    # Sin permiso de brocha gorda: la restricción más cercana manda, y acá no hay
    # ninguno, así que solo entran los administradores.
    for nombre, _hijas in SOLO_ADMINISTRADORES:
        _crear(organization, nombre, creado_por, parent=root, restringida=True)

    return root


def nombre_personal(user):
    """Con qué nombre se guarda la carpeta de una persona."""
    return (user.get_full_name() or '').strip() or user.email


def carpeta_personal(organization, user):
    """La carpeta privada de una persona. La crea si no existe.

    `created_by` es lo que le da acceso: el motor de permisos le devuelve edición a quien
    creó una carpeta restringida, así que su dueño entra y nadie más — salvo los
    administradores, que entran a todo porque no pueden administrar lo que no ven.

    Se busca por `created_by`, no por nombre: si alguien se cambia el nombre en su perfil
    no puede aparecerle una carpeta nueva y vacía en lugar de la suya.
    """
    from apps.archivos.models import Carpeta

    ya = Carpeta.objects.filter(
        organization=organization, created_by=user, parent=None, personal=True,
    ).first()
    if ya:
        return ya

    base = nombre_personal(user)
    nombre, n = base, 2
    while Carpeta.objects.filter(
        organization=organization, parent=None, name=nombre,
    ).exists():
        nombre = f'{base} ({n})'
        n += 1

    return Carpeta.objects.create(
        organization=organization, parent=None, name=nombre,
        created_by=user, restringida=True, personal=True,
    )

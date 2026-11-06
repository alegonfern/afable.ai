"""Exportar a Excel e importar desde Excel (o CSV) en Compras y Ventas (24-10-2026).

Exportar: cualquier lista (pedidos, contactos, productos, un reporte) sale como .xlsx con los
mismos nombres de columna que se ven en pantalla.

Importar: productos y contactos, desde la plantilla que se descarga aquí mismo o desde un archivo
con esas columnas. Lo que ya existe (mismo código de producto, mismo RUT) se actualiza; lo demás se
crea. Las filas con problemas no detienen la carga: se informan con su número de fila.
"""

import csv
import io
from decimal import Decimal

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from apps.finanzas.models import Contacto

from .models import Producto
from .operaciones import ErrorComercial, decimal

XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


def libro(titulo, columnas, filas):
    """Un .xlsx con una hoja: encabezado en negrita, columnas a lo ancho del contenido."""
    wb = Workbook()
    ws = wb.active
    ws.title = titulo[:31]
    ws.append(columnas)
    for celda in ws[1]:
        celda.font = Font(bold=True)
    for fila in filas:
        ws.append([float(v) if isinstance(v, Decimal) else v for v in fila])
    for i, nombre in enumerate(columnas, start=1):
        largo = max([len(str(nombre))] + [len(str(f[i - 1])) for f in filas if i - 1 < len(f) and f[i - 1] is not None])
        ws.column_dimensions[get_column_letter(i)].width = min(max(10, largo + 2), 60)
    ws.freeze_panes = 'A2'
    salida = io.BytesIO()
    wb.save(salida)
    return salida.getvalue()


# ── Importar ──────────────────────────────────────────────────────────────────

COLUMNAS_PRODUCTOS = ['Código', 'Nombre', 'Tipo', 'Unidad', 'Precio de venta', 'Costo', 'Stock mínimo', 'Exento',
                      'Familia', 'Ubicación', 'Código de barras']
COLUMNAS_CONTACTOS = ['RUT', 'Razón social', 'Giro', 'Dirección', 'Comuna', 'Ciudad', 'Correo', 'Teléfono',
                      'Persona de contacto', 'Cliente', 'Proveedor']
EJEMPLO_PRODUCTOS = [['SILLA-01', 'Silla ergonómica', 'Almacenable', 'un', 89000, 52000, 5, 'No', 'Muebles', 'A-01',
                      '7801234567890'],
                     ['INST', 'Instalación', 'Servicio', 'hr', 25000, 0, 0, 'No', '', '', '']]
EJEMPLO_CONTACTOS = [['76.543.210-K', 'Comercial Andes SpA', 'Comercio', 'Av. Siempre Viva 123', 'Santiago',
                      'Santiago', 'compras@andes.cl', '+56 9 1234 5678', 'María Pérez', 'Sí', 'No']]


def plantilla(que):
    if que == 'productos':
        return libro('Productos', COLUMNAS_PRODUCTOS, EJEMPLO_PRODUCTOS)
    return libro('Contactos', COLUMNAS_CONTACTOS, EJEMPLO_CONTACTOS)


def _clave(texto):
    """Encabezado comparable: sin tildes, mayúsculas ni espacios de más."""
    import unicodedata
    t = unicodedata.normalize('NFKD', str(texto or '')).encode('ascii', 'ignore').decode().lower()
    return ' '.join(t.split())


def leer_filas(archivo):
    """[(número de fila, {encabezado normalizado: valor})] de un .xlsx o un .csv."""
    nombre = (getattr(archivo, 'name', '') or '').lower()
    datos = archivo.read()
    if nombre.endswith('.csv') or not datos[:2] == b'PK':
        texto = datos.decode('utf-8-sig', errors='replace')
        delimitador = ';' if texto.split('\n', 1)[0].count(';') >= texto.split('\n', 1)[0].count(',') else ','
        filas = list(csv.reader(io.StringIO(texto), delimiter=delimitador))
    else:
        try:
            ws = load_workbook(io.BytesIO(datos), read_only=True, data_only=True).active
        except Exception:
            raise ErrorComercial('No se pudo leer el archivo: súbalo como Excel (.xlsx) o CSV.')
        filas = [list(f) for f in ws.iter_rows(values_only=True)]
    if not filas:
        raise ErrorComercial('El archivo está vacío.')
    encabezado = [_clave(h) for h in filas[0]]
    salida = []
    for i, f in enumerate(filas[1:], start=2):
        if not any(str(v or '').strip() for v in f):
            continue
        salida.append((i, {encabezado[j]: f[j] for j in range(min(len(encabezado), len(f))) if encabezado[j]}))
    return salida


def _si(v):
    return _clave(v) in ('si', 's', 'x', '1', 'true', 'verdadero', 'yes')


def _texto(v, largo):
    if v is None:
        return ''
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()[:largo]


TIPOS_PRODUCTO = {'almacenable': Producto.ALMACENABLE, 'consumible': Producto.CONSUMIBLE, 'servicio': Producto.SERVICIO}


def importar_productos(org, archivo):
    creados = actualizados = 0
    errores = []
    for n, f in leer_filas(archivo):
        try:
            nombre = _texto(f.get('nombre'), 200)
            codigo = _texto(f.get('codigo'), 40)
            if not nombre:
                raise ErrorComercial('falta el nombre')
            p = (Producto.objects.filter(organization=org, codigo=codigo).first() if codigo else None) \
                or Producto.objects.filter(organization=org, codigo='', nombre__iexact=nombre).first()
            nuevo = p is None
            p = p or Producto(organization=org)
            p.nombre, p.codigo = nombre, codigo or p.codigo
            if f.get('tipo') not in (None, ''):
                tipo = TIPOS_PRODUCTO.get(_clave(f['tipo']))
                if tipo is None:
                    raise ErrorComercial(f'tipo «{f["tipo"]}» no válido (Almacenable, Consumible o Servicio)')
                p.tipo = tipo
            if f.get('unidad') not in (None, ''):
                p.unidad = _texto(f['unidad'], 20)
            for col, campo, nom in (('precio de venta', 'precio_venta', 'el precio'), ('costo', 'costo', 'el costo'),
                                    ('stock minimo', 'stock_minimo', 'el stock mínimo')):
                if f.get(col) not in (None, ''):
                    setattr(p, campo, decimal(f[col], nom.capitalize(), 0))
            if f.get('exento') not in (None, ''):
                p.exento = _si(f['exento'])
            for col, campo, largo in (('familia', 'familia', 80), ('ubicacion', 'ubicacion', 40),
                                      ('codigo de barras', 'codigo_barras', 40)):
                if f.get(col) not in (None, ''):
                    setattr(p, campo, _texto(f[col], largo))
            p.save()
            creados += nuevo
            actualizados += not nuevo
        except ErrorComercial as e:
            errores.append({'fila': n, 'motivo': str(e)})
    return {'creados': creados, 'actualizados': actualizados, 'errores': errores}


def importar_contactos(org, archivo, normalizar_rut):
    creados = actualizados = 0
    errores = []
    campos = [('giro', 'giro', 255), ('direccion', 'direccion', 255), ('comuna', 'comuna', 80), ('ciudad', 'ciudad', 80),
              ('correo', 'email', 254), ('telefono', 'telefono', 30), ('persona de contacto', 'persona_contacto', 120)]
    for n, f in leer_filas(archivo):
        try:
            nombre = _texto(f.get('razon social') or f.get('nombre'), 255)
            if not nombre:
                raise ErrorComercial('falta la razón social')
            rut = normalizar_rut(f.get('rut'))
            c = (Contacto.objects.filter(organization=org, rut=rut).first() if rut else None) \
                or Contacto.objects.filter(organization=org, rut='', razon_social__iexact=nombre).first()
            nuevo = c is None
            c = c or Contacto(organization=org, rut=rut)
            c.razon_social = nombre
            for col, campo, largo in campos:
                if f.get(col) not in (None, ''):
                    setattr(c, campo, _texto(f[col], largo))
            if c.email and '@' not in c.email:
                raise ErrorComercial(f'correo «{c.email}» no válido')
            if f.get('cliente') not in (None, ''):
                c.es_cliente = _si(f['cliente'])
            if f.get('proveedor') not in (None, ''):
                c.es_proveedor = _si(f['proveedor'])
            c.save()
            creados += nuevo
            actualizados += not nuevo
        except ErrorComercial as e:
            errores.append({'fila': n, 'motivo': str(e)})
    return {'creados': creados, 'actualizados': actualizados, 'errores': errores}

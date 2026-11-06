"""Reportes de Ventas y Compras (24-10-2026): por producto, por cliente o proveedor y por mes.

Se arman con las órdenes confirmadas del período (por su fecha), sin IVA y en pesos. En ventas se
calcula el margen con el costo promedio de cada producto (lo que costó en las recepciones, o el
costo de su ficha si nunca se recibió); las líneas sin producto no tienen costo y se cuentan aparte.
"""

from collections import OrderedDict
from decimal import Decimal

from .models import CERO, VENTA, Pedido
from .operaciones import costo_promedio

MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']


def _pct(parte, total):
    return round(float(parte) * 100 / float(total), 1) if total else None


def generar(org, tipo, desde, hasta, por):
    pedidos = (Pedido.objects.filter(organization=org, tipo=tipo, estado=Pedido.CONFIRMADO,
                                     fecha__gte=desde, fecha__lte=hasta)
               .select_related('contacto').prefetch_related('lineas__producto'))
    venta = tipo == VENTA
    costos = {}
    filas = OrderedDict()
    total = {'monto': 0, 'costo': 0, 'cantidad': CERO, 'pedidos': 0}
    for p in pedidos:
        total['pedidos'] += 1
        vistos = set()
        for l in p.lineas.all():
            monto = p.a_pesos(l.subtotal)
            costo = None
            if venta and l.producto_id:
                if l.producto_id not in costos:
                    costos[l.producto_id] = costo_promedio(org, l.producto)
                costo = int(round(costos[l.producto_id] * l.cantidad))
            if por == 'producto':
                clave = l.producto_id or f'libre:{l.descripcion.lower()}'
                nombre = l.producto.nombre if l.producto_id else l.descripcion
                extra = {'unidad': l.unidad}
            elif por == 'contacto':
                clave, nombre, extra = p.contacto_id, p.contacto.razon_social, {'rut': p.contacto.rut}
            else:
                clave = p.fecha.strftime('%Y-%m')
                nombre, extra = f'{MESES[p.fecha.month - 1]} {p.fecha.year}', {}
            f = filas.setdefault(clave, {'clave': str(clave), 'nombre': nombre, 'cantidad': CERO, 'monto': 0,
                                         'costo': 0, 'sin_costo': 0, 'pedidos': 0, **extra})
            f['cantidad'] += l.cantidad
            f['monto'] += monto
            if costo is None:
                f['sin_costo'] += monto
            else:
                f['costo'] += costo
                total['costo'] += costo
            if clave not in vistos:
                f['pedidos'] += 1
                vistos.add(clave)
            total['monto'] += monto
            total['cantidad'] += l.cantidad
    salida = []
    for f in filas.values():
        con_costo = f['monto'] - f['sin_costo']
        f['margen'] = con_costo - f['costo'] if venta and con_costo else None
        f['margen_pct'] = _pct(f['margen'], con_costo) if f['margen'] is not None else None
        f['participacion_pct'] = _pct(f['monto'], total['monto'])
        f['cantidad'] = format(f['cantidad'].normalize(), 'f')
        salida.append(f)
    if por != 'mes':
        salida.sort(key=lambda f: -f['monto'])
    margen_total = None
    if venta:
        con_costo = total['monto'] - sum(f['sin_costo'] for f in salida)
        margen_total = con_costo - total['costo'] if con_costo else None
    return {
        'filas': salida,
        'total': {'monto': total['monto'], 'costo': total['costo'], 'pedidos': total['pedidos'],
                  'margen': margen_total,
                  'margen_pct': _pct(margen_total, total['monto'] - sum(f['sin_costo'] for f in salida))
                  if margen_total is not None else None},
    }


COLUMNAS = {
    'producto': ['Producto', 'Unidad', 'Cantidad', 'Monto sin IVA', 'Participación %'],
    'contacto': ['Nombre', 'RUT', 'Órdenes', 'Monto sin IVA', 'Participación %'],
    'mes': ['Mes', 'Órdenes', 'Monto sin IVA'],
}


def a_planilla(datos, tipo, por):
    venta = tipo == VENTA
    columnas = list(COLUMNAS[por])
    if venta:
        columnas += ['Costo', 'Margen', 'Margen %']
    filas = []
    for f in datos['filas']:
        if por == 'producto':
            fila = [f['nombre'], f.get('unidad', ''), Decimal(f['cantidad']), f['monto'], f['participacion_pct']]
        elif por == 'contacto':
            fila = [f['nombre'], f.get('rut', ''), f['pedidos'], f['monto'], f['participacion_pct']]
        else:
            fila = [f['nombre'], f['pedidos'], f['monto']]
        if venta:
            fila += [f['costo'], f['margen'], f['margen_pct']]
        filas.append(fila)
    return columnas, filas

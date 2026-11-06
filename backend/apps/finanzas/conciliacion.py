"""Conciliación bancaria ("El cuadre"): cruzar la cartola del banco con los documentos del SII.

Qué hace:
1. `leer_cartola` lee el CSV o Excel del banco (fecha, glosa, cargo/abono o monto, saldo).
   ⚠️ Cada banco exporta distinto: está armado con columnas habituales y probado con una
   cartola de ejemplo. Con cartolas reales se agregan nombres a ALIAS, sin tocar el resto.
2. `cargar_cartola` guarda los movimientos (sin repetir al volver a subir) y corre el cruce.
3. `cruzar` explica solo lo que es claro:
   - un abono con UNA venta (o varias del mismo cliente) por el mismo monto, emitida antes;
   - un cargo con UNA compra u honorario (líquido, sin la retención) por el mismo monto;
   - comisiones y pagos de impuestos por su glosa;
   - un cargo y un abono por el mismo monto entre cuentas propias quedan como POSIBLE
     traspaso (lo confirma la persona: puede ser casualidad).
   Lo dudoso no se cruza: queda pendiente con sus candidatos.
4. Al conciliar, el documento queda pagado con la fecha real del banco.
"""

import hashlib
import io
import re
from collections import defaultdict
from datetime import date, timedelta
from itertools import combinations

from django.db import transaction
from django.db.models import Q

from . import constantes as c
from .importador import _clave, _fecha, _leer_texto, leer_filas
from .models import Cartola, CierreMes, DocumentoTributario, MovimientoBancario

ALIAS = {
    'fecha': ['fecha', 'fecha movimiento', 'fecha operacion', 'fecha contable'],
    'descripcion': ['descripcion', 'glosa', 'detalle', 'concepto', 'descripcion movimiento'],
    'cargo': ['cargo', 'cargos', 'debito', 'debitos', 'egreso', 'egresos', 'giro', 'giros'],
    'abono': ['abono', 'abonos', 'credito', 'creditos', 'ingreso', 'ingresos', 'deposito', 'depositos'],
    'monto': ['monto', 'importe', 'valor'],
    'saldo': ['saldo', 'saldo disponible', 'saldo contable'],
}

# Días hacia atrás en que puede estar el documento que paga un movimiento.
VENTANA_DIAS = 150
# Días de diferencia aceptados entre los dos lados de un traspaso.
VENTANA_TRASPASO = 3

GLOSAS = [
    (re.compile(r'comisi|mantenci|cargo por servicio|impuesto timbre|seguro desgrav', re.I), 'comision'),
    (re.compile(r'\bf29\b|tesorer|\btgr\b|\bsii\b|impuesto', re.I), 'impuestos'),
    (re.compile(r'remuneraci|sueldo|liquidaci', re.I), 'remuneraciones'),
]


class CartolaNoReconocida(ValueError):
    pass


def _monto_cl(v):
    v = (v or '').strip().replace('$', '').replace(' ', '')
    if not v or v == '-':
        return 0
    negativo = v.startswith('-') or (v.startswith('(') and v.endswith(')'))
    v = v.strip('-()').replace('.', '').replace(',', '.')
    n = int(round(float(v)))
    return -n if negativo else n


def _filas_excel(contenido):
    import openpyxl
    libro = openpyxl.load_workbook(io.BytesIO(contenido), read_only=True, data_only=True)
    hoja = libro.active
    filas = []
    for fila in hoja.iter_rows(values_only=True):
        vals = ['' if x is None else (x.strftime('%d/%m/%Y') if hasattr(x, 'strftime') else str(x)) for x in fila]
        if any(v.strip() for v in vals):
            filas.append(vals)
    return filas


def leer_cartola(contenido: bytes, nombre: str):
    """Devuelve (movimientos [{fecha, descripcion, monto, saldo, fila}], errores)."""
    if nombre.lower().endswith(('.xlsx', '.xlsm')):
        filas = _filas_excel(contenido)
    else:
        encabezado, resto = leer_filas(contenido)
        filas = [encabezado] + resto
    # El encabezado puede no estar en la primera fila (los bancos ponen títulos arriba).
    inicio, mapa = None, {}
    for i, fila in enumerate(filas[:15]):
        claves = [_clave(x) for x in fila]
        m = {}
        for campo, alias in ALIAS.items():
            for a in alias:
                if a in claves:
                    m[campo] = claves.index(a)
                    break
        if 'fecha' in m and ('monto' in m or 'cargo' in m or 'abono' in m):
            inicio, mapa = i, m
            break
    if inicio is None:
        raise CartolaNoReconocida(
            'No se reconocen las columnas de la cartola. Se necesita al menos la fecha y el '
            'monto (o cargos y abonos).')

    movimientos, errores = [], []
    for n, fila in enumerate(filas[inicio + 1:], start=inicio + 2):
        def campo(k):
            i = mapa.get(k)
            return fila[i] if i is not None and i < len(fila) else ''
        try:
            if not campo('fecha').strip():
                continue
            if 'monto' in mapa:
                monto = _monto_cl(campo('monto'))
            else:
                monto = _monto_cl(campo('abono')) - abs(_monto_cl(campo('cargo')))
            if monto == 0:
                continue
            movimientos.append({
                'fecha': _fecha(campo('fecha')), 'descripcion': campo('descripcion').strip()[:255],
                'monto': monto, 'saldo': _monto_cl(campo('saldo')) if 'saldo' in mapa and campo('saldo').strip() else None,
                'fila': n,
            })
        except (ValueError, IndexError) as e:
            errores.append({'fila': n, 'motivo': str(e)})
    return movimientos, errores


def _huella(m, orden):
    base = f'{m["fecha"].isoformat()}|{m["monto"]}|{m["descripcion"]}|{orden}'
    return hashlib.sha1(base.encode()).hexdigest()


@transaction.atomic
def cargar_cartola(cuenta, contenido: bytes, nombre: str, usuario=None):
    movimientos, errores = leer_cartola(contenido, nombre)
    cartola = Cartola.objects.create(organization=cuenta.organization, cuenta=cuenta,
                                     nombre_archivo=nombre[:255], subida_por=usuario, errores=errores)
    vistos = defaultdict(int)
    nuevos = duplicados = 0
    for m in movimientos:
        clave = (m['fecha'], m['monto'], m['descripcion'])
        vistos[clave] += 1                       # dos movimientos idénticos el mismo día valen
        _, creado = MovimientoBancario.objects.get_or_create(
            cuenta=cuenta, huella=_huella(m, vistos[clave]),
            defaults={'organization': cuenta.organization, 'cartola': cartola, 'fecha': m['fecha'],
                      'descripcion': m['descripcion'], 'monto': m['monto'], 'saldo': m['saldo']},
        )
        nuevos += creado
        duplicados += not creado
    if movimientos:
        cartola.desde = min(m['fecha'] for m in movimientos)
        cartola.hasta = max(m['fecha'] for m in movimientos)
        ultimos = [m for m in movimientos if m['saldo'] is not None]
        if ultimos:
            cartola.saldo_final = max(ultimos, key=lambda m: (m['fecha'], m['fila']))['saldo']
    cartola.nuevos, cartola.duplicados = nuevos, duplicados
    cartola.save()
    cruzar(cuenta.organization)
    return cartola


# ── El cruce ────────────────────────────────────────────────────────────────

def monto_a_pagar(d):
    """Lo que se mueve en el banco por un documento: el total, o el líquido en honorarios."""
    base = d.monto_total - d.monto_retenido if d.libro == c.LIBRO_HONORARIOS else d.monto_total
    return d.signo * base


def documentos_sin_respaldo(organization):
    """Documentos que todavía no tienen un movimiento del banco que los explique."""
    return (DocumentoTributario.objects.filter(organization=organization, movimientos__isnull=True)
            .exclude(tipo_documento__in=c.TIPOS_QUE_RESTAN))


def _palabras(texto):
    return {p for p in _clave(texto).split() if len(p) > 3 and p not in {'ltda', 'spa', 'limitada', 'chile', 'servicios'}}


def candidatos(mov, sin_respaldo=None):
    """Documentos que podrían explicar el movimiento, del más al menos probable."""
    qs = sin_respaldo if sin_respaldo is not None else documentos_sin_respaldo(mov.organization)
    libros = [c.LIBRO_VENTAS] if mov.monto > 0 else [c.LIBRO_COMPRAS, c.LIBRO_HONORARIOS]
    qs = qs.filter(libro__in=libros, fecha__lte=mov.fecha,
                   fecha__gte=mov.fecha - timedelta(days=VENTANA_DIAS))
    glosa = _palabras(mov.descripcion)
    objetivo = abs(mov.monto)
    salida = []
    for d in qs:
        nombre = len(glosa & _palabras(d.razon_social)) > 0 or d.rut.split('-')[0] in mov.descripcion.replace('.', '')
        diferencia = abs(monto_a_pagar(d) - objetivo)
        salida.append((diferencia, not nombre, abs((mov.fecha - d.fecha).days), d, nombre))
    salida.sort(key=lambda x: (x[0], x[1], x[2]))
    return [(d, dif, nombre) for dif, _, _, d, nombre in salida]


def _conciliar(mov, docs, origen):
    mov.documentos.set(docs)
    mov.estado = MovimientoBancario.CONCILIADO
    mov.origen = origen
    mov.save(update_fields=['estado', 'origen'])
    for d in docs:
        d.pagado = True
        d.fecha_pago = mov.fecha
        d.save(update_fields=['pagado', 'fecha_pago'])


@transaction.atomic
def cruzar(organization):
    """Explica solo lo que es claro. Devuelve cuántos movimientos cruzó."""
    pendientes = list(MovimientoBancario.objects.filter(organization=organization,
                                                        estado=MovimientoBancario.PENDIENTE,
                                                        pareja__isnull=True).order_by('fecha', 'id'))
    cruzados = 0
    usados = set()
    for mov in pendientes:
        # 1) Glosas que se explican solas.
        for patron, tipo in GLOSAS:
            if mov.monto < 0 and patron.search(mov.descripcion):
                mov.estado, mov.origen, mov.tipo_sin_documento = MovimientoBancario.IDENTIFICADO, 'auto', tipo
                mov.save(update_fields=['estado', 'origen', 'tipo_sin_documento'])
                cruzados += 1
                break
        if mov.estado != MovimientoBancario.PENDIENTE:
            continue
        # 2) Un documento con el mismo monto: si es uno solo, o uno solo con el nombre en la glosa.
        cands = [x for x in candidatos(mov) if x[0].id not in usados]
        exactos = [x for x in cands if x[1] == 0]
        elegido = None
        if len(exactos) == 1:
            elegido = [exactos[0][0]]
        elif len(exactos) > 1:
            con_nombre = [x for x in exactos if x[2]]
            if len(con_nombre) == 1 or (con_nombre and len({x[0].rut for x in con_nombre}) == 1):
                elegido = [con_nombre[0][0]]
        # 3) Varias facturas de un mismo cliente o proveedor que suman el monto (hasta 4).
        if not elegido:
            por_rut = defaultdict(list)
            nombrados = set()
            for d, _, nombre in cands:
                por_rut[d.rut].append(d)
                if nombre:
                    nombrados.add(d.rut)
            # Si la glosa nombra a alguien, la suma se busca solo entre sus documentos: otro
            # proveedor cuyas facturas sumen lo mismo no explica un pago que dice a quién fue.
            # (Regresión real, 25-10-2026: "PAGO PROVEEDOR FERRETERÍA…" quedó con dos
            # facturas de Transportes.)
            for rut, docs in por_rut.items():
                if nombrados and rut not in nombrados:
                    continue
                docs = docs[:8]
                for k in range(2, min(4, len(docs)) + 1):
                    for combo in combinations(docs, k):
                        if sum(monto_a_pagar(d) for d in combo) == abs(mov.monto):
                            elegido = list(combo)
                            break
                    if elegido:
                        break
                if elegido:
                    break
        if elegido:
            _conciliar(mov, elegido, 'auto')
            usados.update(d.id for d in elegido)
            cruzados += 1

    # 4) Posibles traspasos entre cuentas propias: se sugieren, no se dan por hechos.
    restantes = list(MovimientoBancario.objects.filter(organization=organization,
                                                       estado=MovimientoBancario.PENDIENTE,
                                                       pareja__isnull=True))
    cargos = [m for m in restantes if m.monto < 0]
    abonos = [m for m in restantes if m.monto > 0]
    emparejados = set()
    for cargo in cargos:
        for abono in abonos:
            if (abono.id not in emparejados and abono.cuenta_id != cargo.cuenta_id
                    and abono.monto == -cargo.monto
                    and abs((abono.fecha - cargo.fecha).days) <= VENTANA_TRASPASO):
                cargo.pareja, abono.pareja = abono, cargo
                cargo.save(update_fields=['pareja'])
                abono.save(update_fields=['pareja'])
                emparejados.add(abono.id)
                break
    return cruzados


# ── Acciones de la persona ──────────────────────────────────────────────────

@transaction.atomic
def conciliar_manual(mov, documentos):
    deshacer(mov)
    _conciliar(mov, documentos, 'manual')


@transaction.atomic
def identificar(mov, tipo, nota=''):
    deshacer(mov)
    mov.estado, mov.origen, mov.tipo_sin_documento, mov.nota = MovimientoBancario.IDENTIFICADO, 'manual', tipo, nota[:255]
    mov.save()


@transaction.atomic
def confirmar_traspaso(mov):
    otro = mov.pareja or MovimientoBancario.objects.filter(pareja=mov).first()
    for m in filter(None, [mov, otro]):
        m.estado, m.origen = MovimientoBancario.TRASPASO, 'manual'
        m.save(update_fields=['estado', 'origen'])


@transaction.atomic
def descartar_traspaso(mov):
    otro = mov.pareja or MovimientoBancario.objects.filter(pareja=mov).first()
    for m in filter(None, [mov, otro]):
        m.pareja = None
        m.estado = MovimientoBancario.PENDIENTE
        m.save(update_fields=['pareja', 'estado'])


@transaction.atomic
def deshacer(mov):
    """Vuelve el movimiento a pendiente. Los documentos que pagaba quedan por pagar."""
    for d in mov.documentos.all():
        if not d.movimientos.exclude(pk=mov.pk).exists():
            d.pagado, d.fecha_pago = False, None
            d.save(update_fields=['pagado', 'fecha_pago'])
    mov.documentos.clear()
    if mov.estado == MovimientoBancario.TRASPASO:
        otro = mov.pareja or MovimientoBancario.objects.filter(pareja=mov).first()
        if otro:
            otro.estado = MovimientoBancario.PENDIENTE
            otro.save(update_fields=['estado'])
    mov.estado, mov.origen, mov.tipo_sin_documento = MovimientoBancario.PENDIENTE, '', ''
    mov.save(update_fields=['estado', 'origen', 'tipo_sin_documento'])


# ── El cuadre del mes ───────────────────────────────────────────────────────

def _fin_de_mes(anio, mes):
    return date(anio + (mes == 12), 1 if mes == 12 else mes + 1, 1) - timedelta(days=1)


def cuadre(organization, anio, mes):
    movs = list(MovimientoBancario.objects.filter(organization=organization, fecha__year=anio,
                                                  fecha__month=mes).select_related('cuenta'))
    total = len(movs)
    auto = sum(1 for m in movs if m.estado != MovimientoBancario.PENDIENTE and m.origen == 'auto')
    manual = sum(1 for m in movs if m.estado != MovimientoBancario.PENDIENTE and m.origen == 'manual')
    pendientes = [m for m in movs if m.estado == MovimientoBancario.PENDIENTE]
    traspasos = [m for m in pendientes if m.pareja_id]
    por_identificar = [m for m in pendientes if m not in traspasos]
    # Lo anotado: documentos vencidos a fin de mes que deberían tener su movimiento.
    fin = min(_fin_de_mes(anio, mes), date.today())
    vencidos = DocumentoTributario.objects.filter(
        organization=organization, fecha_vencimiento__lte=fin,
        fecha_vencimiento__gte=date(anio, mes, 1) - timedelta(days=60),
    ).exclude(tipo_documento__in=c.TIPOS_QUE_RESTAN)
    sin_respaldo = [d for d in vencidos if not d.movimientos.exists()]
    cuentas = {m.cuenta_id for m in movs}
    cierre = CierreMes.objects.filter(organization=organization, anio=anio, mes=mes).first()
    return {
        'anio': anio, 'mes': mes,
        'porcentaje': round((auto + manual) * 100 / total, 1) if total else None,
        'movimientos': total, 'cuentas': len(cuentas),
        'cuadraron_solos': auto, 'los_cuadro_usted': manual, 'pendientes': len(pendientes),
        'por_identificar': {'cantidad': len(por_identificar), 'monto': sum(abs(m.monto) for m in por_identificar)},
        'posibles_traspasos': {'pares': max(1, len(traspasos) // 2) if traspasos else 0,
                               'monto': sum(abs(m.monto) for m in traspasos if m.monto < 0)},
        # Lo que la cartola todavía no explica: por identificar + posibles traspasos.
        'sin_explicar': (sum(abs(m.monto) for m in por_identificar)
                         + sum(abs(m.monto) for m in traspasos if m.monto < 0)),
        'anotado': {'registros': vencidos.count(), 'con_respaldo': vencidos.count() - len(sin_respaldo),
                    'sin_respaldo_monto': sum(abs(monto_a_pagar(d)) for d in sin_respaldo)},
        'cerrado': bool(cierre), 'cerrado_en': cierre.cerrado_en.isoformat() if cierre else None,
    }


def meses_con_movimientos(organization):
    return [(f.year, f.month) for f in MovimientoBancario.objects.filter(
        organization=organization).dates('fecha', 'month', order='DESC')]

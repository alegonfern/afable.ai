"""Los números del mes, calculados desde los documentos del SII ya cargados.

Todo va SIN IVA y antes del impuesto a la renta, como se mira una empresa por dentro:
- Ingresos: ventas (neto + exento).
- Gastos: compras (neto + exento) y honorarios (bruto).
- Ganancia = ingresos - gastos. Las notas de crédito restan.

El F29 es una PROVISIÓN ESTIMADA, no la declaración:
- IVA débito (ventas) - IVA crédito (compras). Si queda negativo es remanente a favor.
- PPM = tasa configurada × ingresos del mes.
- Retención de honorarios = lo retenido en las boletas del mes.
"""

from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.db.models import Q

from . import constantes as c
from .models import (ConfiguracionTributaria, DeclaracionF29, DocumentoTributario, Proyecto)

# El F29 vence el 20 del mes siguiente para quien factura electrónicamente (el 12 si no).
DIA_VENCIMIENTO_F29 = 20


def _docs(organization, **filtros):
    return DocumentoTributario.objects.filter(organization=organization, **filtros)


def _sin_iva(d):
    return d.signo * (d.monto_neto + d.monto_exento)


def _mes_clave(f):
    return (f.year, f.month)


def _meses_del_anio(anio):
    return [(anio, m) for m in range(1, 13)]


def resumen(organization, anio):
    """Ingresos, gastos y ganancia mes a mes del año, más los totales del año."""
    por_mes = defaultdict(lambda: {'ingresos': 0, 'gastos': 0})
    for d in _docs(organization, fecha__year=anio).only(
            'libro', 'tipo_documento', 'monto_neto', 'monto_exento', 'monto_total', 'fecha'):
        k = _mes_clave(d.fecha)
        if d.libro == c.LIBRO_VENTAS:
            por_mes[k]['ingresos'] += _sin_iva(d)
        elif d.libro == c.LIBRO_COMPRAS:
            por_mes[k]['gastos'] += _sin_iva(d)
        else:                                            # honorarios: el bruto es el gasto
            por_mes[k]['gastos'] += d.signo * d.monto_total
    meses = []
    for a, m in _meses_del_anio(anio):
        v = por_mes.get((a, m), {'ingresos': 0, 'gastos': 0})
        ganancia = v['ingresos'] - v['gastos']
        meses.append({
            'anio': a, 'mes': m, 'ingresos': v['ingresos'], 'gastos': v['gastos'],
            'ganancia': ganancia,
            'margen': round(ganancia * 100 / v['ingresos'], 1) if v['ingresos'] else None,
            'con_datos': (a, m) in por_mes,
        })
    ingresos = sum(x['ingresos'] for x in meses)
    gastos = sum(x['gastos'] for x in meses)
    return {
        'anio': anio, 'meses': meses,
        'ingresos': ingresos, 'gastos': gastos, 'ganancia': ingresos - gastos,
        'margen': round((ingresos - gastos) * 100 / ingresos, 1) if ingresos else None,
    }


def vencimiento_f29(anio, mes):
    a, m = (anio + 1, 1) if mes == 12 else (anio, mes + 1)
    return date(a, m, DIA_VENCIMIENTO_F29)


def f29(organization, anio):
    """La provisión del F29 de cada mes del año que tiene documentos."""
    cfg = ConfiguracionTributaria.de(organization)
    datos = defaultdict(lambda: {'debito': 0, 'credito': 0, 'ingresos': 0, 'retencion': 0})
    for d in _docs(organization, fecha__year=anio).only(
            'libro', 'tipo_documento', 'monto_neto', 'monto_exento', 'monto_iva', 'monto_retenido', 'fecha'):
        k = _mes_clave(d.fecha)
        if d.libro == c.LIBRO_VENTAS:
            datos[k]['debito'] += d.signo * d.monto_iva
            datos[k]['ingresos'] += _sin_iva(d)
        elif d.libro == c.LIBRO_COMPRAS:
            datos[k]['credito'] += d.signo * d.monto_iva
        else:
            datos[k]['retencion'] += d.monto_retenido
    pagos = {(x.anio, x.mes): x for x in DeclaracionF29.objects.filter(organization=organization, anio=anio)}
    tasa = cfg.tasa_ppm
    filas = []
    for k in sorted(datos):
        v = datos[k]
        iva_neto = v['debito'] - v['credito']
        ppm = int((Decimal(max(v['ingresos'], 0)) * tasa / 100).quantize(Decimal('1')))
        total = max(iva_neto, 0) + ppm + v['retencion']
        pago = pagos.get(k)
        filas.append({
            'anio': k[0], 'mes': k[1],
            'iva_debito': v['debito'], 'iva_credito': v['credito'], 'iva_neto': iva_neto,
            'remanente': -iva_neto if iva_neto < 0 else 0,
            'ppm': ppm, 'retencion': v['retencion'], 'estimado': total,
            'vence': vencimiento_f29(*k).isoformat(),
            'pagado': bool(pago and pago.pagado),
            'monto_pagado': pago.monto_pagado if pago else None,
            'fecha_pago': pago.fecha_pago.isoformat() if pago and pago.fecha_pago else None,
        })
    return {
        'anio': anio, 'meses': filas,
        'tasa_ppm': str(tasa), 'tasa_ppm_confirmada': cfg.tasa_ppm_confirmada,
        'dia_vencimiento': DIA_VENCIMIENTO_F29,
    }


def _rango(periodo, anio, mes):
    if periodo == 'mes':
        return Q(fecha__year=anio, fecha__month=mes)
    if periodo == 'anio':
        return Q(fecha__year=anio)
    return Q()


def por_categoria(organization, periodo='mes', anio=None, mes=None):
    """Gasto e ingreso por categoría (con IVA, notas de crédito restadas), con % y acumulado."""
    rango = _rango(periodo, anio, mes)
    gastos, ingresos = defaultdict(int), defaultdict(int)
    for d in _docs(organization).filter(rango).select_related('categoria').only(
            'libro', 'tipo_documento', 'monto_total', 'categoria__nombre'):
        nombre = d.categoria.nombre if d.categoria else 'Sin categoría'
        (ingresos if d.libro == c.LIBRO_VENTAS else gastos)[nombre] += d.signo * d.monto_total

    def tabla(montos):
        total = sum(montos.values())
        filas, acumulado = [], 0
        for nombre, monto in sorted(montos.items(), key=lambda x: -x[1]):
            pct = round(monto * 100 / total, 1) if total else 0
            acumulado += pct
            filas.append({'categoria': nombre, 'monto': monto, 'porcentaje': pct,
                          'acumulado': round(min(acumulado, 100), 1)})
        return {'total': total, 'filas': filas}

    return {'periodo': periodo, 'anio': anio, 'mes': mes,
            'gastos': tabla(gastos), 'ingresos': tabla(ingresos)}


def margen_por_proyecto(organization, anio=None):
    """Lo que cada proyecto vendió y gastó (sin IVA, según el % asignado) y su margen."""
    proyectos = {p.id: {'id': p.id, 'nombre': p.nombre, 'ingresos': 0, 'gastos': 0, 'documentos': 0}
                 for p in Proyecto.objects.filter(organization=organization)}
    qs = _docs(organization).prefetch_related('asignaciones')
    if anio:
        qs = qs.filter(fecha__year=anio)
    sin_asignar = {'ingresos': 0, 'gastos': 0}
    for d in qs:
        base = _sin_iva(d) if d.libro != c.LIBRO_HONORARIOS else d.signo * d.monto_total
        asign = list(d.asignaciones.all())
        cubierto = Decimal('0')
        for a in asign:
            p = proyectos.get(a.proyecto_id)
            if not p:
                continue
            parte = int(Decimal(base) * a.porcentaje / 100)
            p['ingresos' if d.libro == c.LIBRO_VENTAS else 'gastos'] += parte
            p['documentos'] += 1
            cubierto += a.porcentaje
        resto = int(Decimal(base) * (100 - cubierto) / 100)
        sin_asignar['ingresos' if d.libro == c.LIBRO_VENTAS else 'gastos'] += resto
    filas = []
    for p in proyectos.values():
        p['ganancia'] = p['ingresos'] - p['gastos']
        p['margen'] = round(p['ganancia'] * 100 / p['ingresos'], 1) if p['ingresos'] else None
        filas.append(p)
    filas.sort(key=lambda p: -p['ganancia'])
    return {'anio': anio, 'proyectos': filas, 'sin_asignar': sin_asignar}


def anios_con_datos(organization):
    return sorted({f.year for f in _docs(organization).dates('fecha', 'year')}, reverse=True)



def ventas(organization, anio):
    """Ventas del año sin IVA: mes a mes (monto, documentos, promedio por factura) y clientes,
    con cuánto pesa cada uno. Las notas de crédito restan al monto y no cuentan como factura."""
    por_mes = defaultdict(lambda: {'monto': 0, 'facturas': 0, 'notas_credito': 0})
    clientes = defaultdict(lambda: {'monto': 0, 'facturas': 0, 'ultima': None, 'rut': ''})
    for d in _docs(organization, libro=c.LIBRO_VENTAS, fecha__year=anio).only(
            'tipo_documento', 'monto_neto', 'monto_exento', 'fecha', 'razon_social', 'rut'):
        k = _mes_clave(d.fecha)
        monto = _sin_iva(d)
        por_mes[k]['monto'] += monto
        x = clientes[d.razon_social or d.rut]
        x['monto'] += monto
        x['rut'] = d.rut
        if d.signo < 0:
            por_mes[k]['notas_credito'] += 1
        else:
            por_mes[k]['facturas'] += 1
            x['facturas'] += 1
            x['ultima'] = max(x['ultima'] or d.fecha, d.fecha)
    meses = []
    for a, m in _meses_del_anio(anio):
        v = por_mes.get((a, m))
        meses.append({'mes': m, 'monto': v['monto'] if v else 0, 'facturas': v['facturas'] if v else 0,
                      'notas_credito': v['notas_credito'] if v else 0,
                      'promedio': (v['monto'] // v['facturas']) if v and v['facturas'] else None,
                      'con_datos': v is not None})
    total = sum(x['monto'] for x in clientes.values())
    lista = sorted(({'cliente': k, **v, 'ultima': v['ultima'].isoformat() if v['ultima'] else None,
                     'porcentaje': round(v['monto'] * 100 / total, 1) if total else 0}
                    for k, v in clientes.items()), key=lambda x: -x['monto'])
    facturas = sum(x['facturas'] for x in meses)
    return {
        'anio': anio, 'meses': meses, 'total': total, 'facturas': facturas,
        'promedio': total // facturas if facturas else None,
        'clientes': lista,
        # Cuánto depende la empresa de su cliente más grande y de los tres más grandes.
        'concentracion_top1': lista[0]['porcentaje'] if lista else 0,
        'concentracion_top3': round(sum(x['porcentaje'] for x in lista[:3]), 1),
    }

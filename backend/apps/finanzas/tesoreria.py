"""Finanzas: la plata de la empresa. Cuentas por cobrar y por pagar, caja y la cuenta del dueño.

Contabilidad dice lo que pasó; esto dice si hay plata y qué decidir con ella. Una empresa
puede tener utilidad y quedarse sin caja: lo que importa acá es lo que entra y sale de verdad.

- Por cobrar / por pagar: documentos sin pagar (las notas de crédito restan). Honorarios por
  el líquido, que es lo que se le transfiere al emisor.
- Disponible hoy: el último saldo de cada cuenta, según su cartola.
- Puede retirar: disponible - lo comprometido en 30 días - un mes de gasto de reserva. No se
  cuentan los cobros esperados: si se atrasan, el retiro ya se hizo.
"""

from collections import defaultdict
from datetime import date, timedelta

from . import calculos, constantes as c
from .conciliacion import monto_a_pagar
from .models import Cartola, CuentaBancaria, DocumentoTributario, MovimientoBancario

DIAS_HORIZONTE = 30


def _pendientes(organization, tipo):
    libros = [c.LIBRO_VENTAS] if tipo == 'cobrar' else [c.LIBRO_COMPRAS, c.LIBRO_HONORARIOS]
    return DocumentoTributario.objects.filter(organization=organization, libro__in=libros, pagado=False)


def cuentas(organization, tipo):
    """Lo que falta cobrar (tipo='cobrar') o pagar (tipo='pagar'), con antigüedad."""
    hoy = date.today()
    docs = list(_pendientes(organization, tipo).order_by('fecha_vencimiento', 'fecha'))
    filas, por_contraparte = [], defaultdict(lambda: {'monto': 0, 'documentos': 0, 'vencido': 0, 'dias_max': None})
    total = vencido = 0
    tramos = {'vencido_30': 0, 'vencido': 0, 'semana': 0, 'mes': 0, 'despues': 0}
    for d in docs:
        monto = monto_a_pagar(d)
        vence = d.fecha_vencimiento or d.fecha
        dias = (hoy - vence).days               # > 0: atrasado tantos días
        total += monto
        if dias > 0:
            vencido += monto
            tramos['vencido_30' if dias > 30 else 'vencido'] += monto
        elif -dias <= 7:
            tramos['semana'] += monto
        elif -dias <= 30:
            tramos['mes'] += monto
        else:
            tramos['despues'] += monto
        filas.append({'id': d.id, 'rut': d.rut, 'razon_social': d.razon_social, 'folio': d.folio,
                      'tipo_nombre': c.TIPOS_DTE.get(d.tipo_documento, d.tipo_documento),
                      'emision': d.fecha.isoformat(), 'vence': vence.isoformat(), 'dias': dias,
                      'monto': monto})
        x = por_contraparte[(d.rut, d.razon_social)]
        x['monto'] += monto
        x['documentos'] += 1
        if dias > 0:
            x['vencido'] += monto
            x['dias_max'] = max(x['dias_max'] or 0, dias)
    # Cuánto había al cierre del mes anterior, para comparar.
    fin_previo = hoy.replace(day=1) - timedelta(days=1)
    libros = [c.LIBRO_VENTAS] if tipo == 'cobrar' else [c.LIBRO_COMPRAS, c.LIBRO_HONORARIOS]
    previo = sum(monto_a_pagar(d) for d in DocumentoTributario.objects.filter(
        organization=organization, libro__in=libros, fecha__lte=fin_previo).exclude(
        pagado=True, fecha_pago__lte=fin_previo).exclude(pagado=True, fecha_pago__isnull=True))
    prioridad = sorted((f for f in filas if f['dias'] > 0), key=lambda f: -f['monto'])[:5]
    return {
        'tipo': tipo, 'total': total, 'vencido': vencido,
        'porcentaje_vencido': round(vencido * 100 / total) if total else 0,
        'cierre_mes_anterior': previo, 'tramos': tramos, 'prioridad': prioridad,
        'documentos': filas,
        'por_contraparte': sorted(
            [{'rut': k[0], 'razon_social': k[1], **v} for k, v in por_contraparte.items()],
            key=lambda x: -x['monto']),
    }


def _saldos(organization):
    salida = []
    for cuenta in CuentaBancaria.objects.filter(organization=organization):
        ultima = (Cartola.objects.filter(cuenta=cuenta, saldo_final__isnull=False)
                  .order_by('-hasta', '-id').first())
        salida.append({'id': cuenta.id, 'etiqueta': str(cuenta),
                       'saldo': ultima.saldo_final if ultima else None,
                       'al': ultima.hasta.isoformat() if ultima and ultima.hasta else None})
    return salida


def _gasto_mensual(organization):
    """Lo que sale del banco en un mes normal (sin traspasos ni retiros del dueño), promedio de
    los últimos 3 meses con cartola. Sin cartolas: los gastos del SII con IVA."""
    salidas = defaultdict(int)
    for m in MovimientoBancario.objects.filter(organization=organization, monto__lt=0).exclude(
            estado=MovimientoBancario.TRASPASO).exclude(tipo_sin_documento__in=['retiro_dueno', 'aporte_capital']):
        salidas[(m.fecha.year, m.fecha.month)] += -m.monto
    if salidas:
        ultimos = sorted(salidas)[-3:]
        return sum(salidas[k] for k in ultimos) // len(ultimos), 'banco'
    gastos = defaultdict(int)
    for d in DocumentoTributario.objects.filter(organization=organization).exclude(libro=c.LIBRO_VENTAS):
        gastos[(d.fecha.year, d.fecha.month)] += d.signo * d.monto_total
    if not gastos:
        return 0, 'sin_datos'
    ultimos = sorted(gastos)[-3:]
    return sum(gastos[k] for k in ultimos) // len(ultimos), 'documentos'


def caja(organization):
    hoy = date.today()
    limite = hoy + timedelta(days=DIAS_HORIZONTE)
    saldos = _saldos(organization)
    con_saldo = [s for s in saldos if s['saldo'] is not None]
    disponible = sum(s['saldo'] for s in con_saldo) if con_saldo else None

    por_pagar = sum(monto_a_pagar(d) for d in _pendientes(organization, 'pagar')
                    if (d.fecha_vencimiento or d.fecha) <= limite)
    por_cobrar = sum(monto_a_pagar(d) for d in _pendientes(organization, 'cobrar')
                     if (d.fecha_vencimiento or d.fecha) <= limite)
    f29 = calculos.f29(organization, hoy.year)['meses'] + (
        calculos.f29(organization, hoy.year - 1)['meses'] if hoy.month == 1 else [])
    impuestos = sum(x['estimado'] for x in f29 if not x['pagado'] and date.fromisoformat(x['vence']) <= limite)
    comprometido = por_pagar + impuestos
    gasto_mes, fuente_gasto = _gasto_mensual(organization)

    respuesta = {
        'disponible': disponible, 'cuentas': saldos,
        'entradas_esperadas': por_cobrar, 'salidas_comprometidas': comprometido,
        'detalle_salidas': {'proveedores': por_pagar, 'impuestos': impuestos},
        'gasto_mensual': gasto_mes, 'fuente_gasto': fuente_gasto, 'horizonte_dias': DIAS_HORIZONTE,
        'puede_retirar': None, 'meses_de_caja': None, 'saldo_30_dias': None,
    }
    if disponible is not None:
        respuesta['puede_retirar'] = max(0, disponible - comprometido - gasto_mes)
        respuesta['meses_de_caja'] = round(disponible / gasto_mes, 1) if gasto_mes else None
        respuesta['saldo_30_dias'] = disponible + por_cobrar - comprometido
    return respuesta


def cuenta_del_dueno(organization):
    tipos = ['retiro_dueno', 'aporte_capital', 'impuestos']
    movs = MovimientoBancario.objects.filter(organization=organization, estado=MovimientoBancario.IDENTIFICADO,
                                             tipo_sin_documento__in=tipos).order_by('-fecha')
    retiros = sum(-m.monto for m in movs if m.tipo_sin_documento == 'retiro_dueno')
    aportes = sum(m.monto for m in movs if m.tipo_sin_documento == 'aporte_capital')
    nombres = dict(MovimientoBancario.TIPOS_SIN_DOCUMENTO)
    return {
        'retiros': retiros, 'capital': aportes,
        'movimientos': [{'fecha': m.fecha.isoformat(), 'tipo': m.tipo_sin_documento,
                         'tipo_nombre': nombres[m.tipo_sin_documento], 'descripcion': m.descripcion,
                         'monto': m.monto} for m in movs[:10]],
    }

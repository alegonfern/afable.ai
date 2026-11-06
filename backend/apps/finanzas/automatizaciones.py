"""Las automatizaciones de cada módulo: lo que Afable hace solo, sin que nadie lo pida.

Son un catálogo fijo (la empresa las activa o no), no un constructor: cada una mira los datos
y, si hay algo que decir, avisa. Si no hay nada que decir, no avisa: un aviso que a veces no
dice nada se vuelve ruido.

Desde el 22-10-2026 cada una tiene:
- **Programación**: cada día, cada semana (qué día) o cada mes (qué día), y a qué hora. Sin
  elegir, la del catálogo (`programacion`). El proceso de automatizaciones (`run_automations`)
  corre las que tienen `proxima_ejecucion` vencida y calcula la siguiente.
- **Seguidores**: a quién avisa. Sin seguidores, a los administradores y editores.
- **Canales**: la campana siempre; correo y WhatsApp si se activan.

Otros módulos suman las suyas con `registrar` (Compras y Ventas, desde `apps.comercial`).
"Probar ahora" corre una sin esperar la programación y sin avisar a nadie.
"""

import logging
from datetime import date, datetime, timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from apps.notificaciones import whatsapp
from apps.notificaciones.avisos import avisar
from apps.notificaciones.models import TIPO_AGENTE

from . import calculos, tesoreria
from .models import AutomatizacionModulo, DocumentoTributario

logger = logging.getLogger(__name__)

LUNES = 0
DIAS = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
DIARIA, SEMANAL, MENSUAL = AutomatizacionModulo.DIARIA, AutomatizacionModulo.SEMANAL, AutomatizacionModulo.MENSUAL


def _prog(frecuencia, hora=8, dia_semana=LUNES, dia_mes=1):
    return {'frecuencia': frecuencia, 'hora': hora, 'dia_semana': dia_semana, 'dia_mes': dia_mes}


CATALOGO = [
    {'clave': 'f29_aviso', 'modulo': 'contabilidad',
     'nombre': 'Avisarme el F29 antes de que venza',
     'descripcion': 'Desde cinco días antes del vencimiento: cuánto apartar, con el desglose de IVA, PPM y retención. Avisa una vez por mes.',
     'programacion': _prog(DIARIA)},
    {'clave': 'rcv_recordatorio', 'modulo': 'contabilidad',
     'nombre': 'Recordarme cargar el Registro de Compras y Ventas',
     'descripcion': 'Si el mes anterior todavía no tiene documentos cargados.',
     'programacion': _prog(MENSUAL, dia_mes=3)},
    {'clave': 'cobros_vencidos', 'modulo': 'finanzas',
     'nombre': 'Avisarme los cobros vencidos',
     'descripcion': 'Quién le debe, cuánto y desde cuándo, con el más atrasado primero.',
     'programacion': _prog(SEMANAL)},
    {'clave': 'pagos_semana', 'modulo': 'finanzas',
     'nombre': 'Lo que hay que pagar esta semana',
     'descripcion': 'Proveedores y honorarios que vencen en los próximos 7 días.',
     'programacion': _prog(SEMANAL)},
    {'clave': 'caja_corta', 'modulo': 'finanzas',
     'nombre': 'Avisarme si la caja se va a quedar corta',
     'descripcion': 'Si el saldo proyectado a 30 días queda bajo cero. Avisa una vez y vuelve a avisar solo si se recupera y vuelve a caer.',
     'programacion': _prog(DIARIA)},
    {'clave': 'ventas_semana', 'modulo': 'ventas',
     'nombre': 'Resumen semanal de ventas',
     'descripcion': 'Lo vendido en los últimos 7 días comparado con los 7 anteriores, y los principales clientes.',
     'programacion': _prog(SEMANAL)},
]
POR_CLAVE = {a['clave']: a for a in CATALOGO}


def _clp(n):
    return f'${round(n):,}'.replace(',', '.')


def _hoy():
    return timezone.localdate()


# ── Cada automatización: devuelve None si no hay nada que decir, o (marca, título, detalle,
#    enlace). La marca evita repetir el mismo aviso: por mes o por estado en las alertas; por
#    día en los informes, que se mandan cada vez que les toca.

def _f29_aviso(org, hoy, forzar):
    filas = calculos.f29(org, hoy.year)['meses'] + calculos.f29(org, hoy.year - 1)['meses']
    for f in filas:
        vence = date.fromisoformat(f['vence'])
        if f['pagado'] or f['estimado'] <= 0:
            continue
        if forzar or vence - timedelta(days=5) <= hoy <= vence:
            meses = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
                     'septiembre', 'octubre', 'noviembre', 'diciembre']
            detalle = (f'Aparte {_clp(f["estimado"])} para el F29 de {meses[f["mes"] - 1]}: '
                       f'IVA {_clp(max(f["iva_neto"], 0))}, PPM {_clp(f["ppm"])}, retención {_clp(f["retencion"])}. '
                       f'Vence el {vence.strftime("%d-%m-%Y")}. Es una provisión estimada.')
            return f'f29-{f["anio"]}-{f["mes"]}', f'F29: aparte {_clp(f["estimado"])}', detalle, '/app/contabilidad/impuestos'
    return None


def _rcv_recordatorio(org, hoy, forzar):
    previo = hoy.replace(day=1) - timedelta(days=1)
    if DocumentoTributario.objects.filter(organization=org, fecha__year=previo.year, fecha__month=previo.month).exists():
        return None
    return (f'rcv-{previo.year}-{previo.month}', 'Falta cargar el mes anterior',
            f'No hay documentos de {previo.strftime("%m-%Y")}. Descargue el Registro de Compras y Ventas '
            'del SII y súbalo en Contabilidad › Documentos para tener el F29 y los números al día.',
            '/app/contabilidad/documentos')


def _cobros_vencidos(org, hoy, forzar):
    r = tesoreria.cuentas(org, 'cobrar')
    if r['vencido'] <= 0:
        return None
    lineas = '; '.join(f'{f["razon_social"]} {_clp(f["monto"])} ({f["dias"]} días)' for f in r['prioridad'][:5])
    return (f'cobros-{hoy.isoformat()}', f'Le deben {_clp(r["vencido"])} vencido',
            f'{r["porcentaje_vencido"]}% de lo por cobrar está vencido. Los más grandes: {lineas}.',
            '/app/finanzas/por-cobrar')


def _pagos_semana(org, hoy, forzar):
    r = tesoreria.cuentas(org, 'pagar')
    limite = hoy + timedelta(days=7)
    proximos = [f for f in r['documentos'] if date.fromisoformat(f['vence']) <= limite]
    if not proximos:
        return None
    total = sum(f['monto'] for f in proximos)
    lineas = '; '.join(f'{f["razon_social"]} {_clp(f["monto"])}' for f in sorted(proximos, key=lambda f: -f['monto'])[:5])
    return (f'pagos-{hoy.isoformat()}', f'Esta semana paga {_clp(total)}',
            f'{len(proximos)} documentos vencen hasta el {limite.strftime("%d-%m")}: {lineas}.',
            '/app/finanzas/por-pagar')


def _caja_corta(org, hoy, forzar):
    c = tesoreria.caja(org)
    if c['disponible'] is None:
        return None
    if c['saldo_30_dias'] >= 0 and not forzar:
        return ('ok', None, None, None)          # se recuperó: el próximo bajón vuelve a avisar
    if c['saldo_30_dias'] >= 0:
        return None
    return ('corta', 'La caja se va a quedar corta',
            f'Con lo que tiene hoy ({_clp(c["disponible"])}), lo que espera cobrar ({_clp(c["entradas_esperadas"])}) '
            f'y lo comprometido ({_clp(c["salidas_comprometidas"])}), en 30 días quedaría en {_clp(c["saldo_30_dias"])}.',
            '/app/finanzas/caja')


def _ventas_semana(org, hoy, forzar):
    inicio = hoy - timedelta(days=7)                    # los últimos 7 días, sin contar hoy
    previa = inicio - timedelta(days=7)

    def total(desde):
        docs = DocumentoTributario.objects.filter(organization=org, libro='ventas', fecha__gte=desde,
                                                  fecha__lt=desde + timedelta(days=7))
        suma, por = 0, {}
        for d in docs:
            v = d.signo * (d.monto_neto + d.monto_exento)
            suma += v
            por[d.razon_social] = por.get(d.razon_social, 0) + v
        return suma, por
    actual, clientes = total(inicio)
    anterior, _ = total(previa)
    if actual == 0 and anterior == 0:
        return None
    var = f' ({"+" if actual >= anterior else ""}{round((actual - anterior) * 100 / anterior)}% vs los 7 días anteriores)' if anterior else ''
    top = '; '.join(f'{n} {_clp(v)}' for n, v in sorted(clientes.items(), key=lambda x: -x[1])[:3])
    return (f'ventas-{hoy.isoformat()}', f'En 7 días vendió {_clp(actual)}',
            f'Ventas sin IVA del {inicio.strftime("%d-%m")} al {(hoy - timedelta(days=1)).strftime("%d-%m")}: '
            f'{_clp(actual)}{var}.' + (f' Principales clientes: {top}.' if top else ''),
            '/app/ventas')


FUNCIONES = {'f29_aviso': _f29_aviso, 'rcv_recordatorio': _rcv_recordatorio,
             'cobros_vencidos': _cobros_vencidos, 'pagos_semana': _pagos_semana,
             'caja_corta': _caja_corta, 'ventas_semana': _ventas_semana}


def registrar(catalogo, funciones):
    """Otro módulo suma sus automatizaciones al catálogo (lo llama su AppConfig.ready)."""
    for entrada in catalogo:
        if entrada['clave'] not in POR_CLAVE:
            CATALOGO.append(entrada)
            POR_CLAVE[entrada['clave']] = entrada
    FUNCIONES.update(funciones)


# ── Programación ──────────────────────────────────────────────────────────────

def programacion(auto):
    """La programación vigente: la elegida, o la del catálogo donde no se eligió."""
    base = POR_CLAVE.get(auto.clave, {}).get('programacion') or _prog(DIARIA)
    return {
        'frecuencia': auto.frecuencia or base['frecuencia'],
        'hora': base['hora'] if auto.hora is None else auto.hora,
        'dia_semana': base['dia_semana'] if auto.dia_semana is None else auto.dia_semana,
        'dia_mes': base['dia_mes'] if auto.dia_mes is None else auto.dia_mes,
    }


def describir(prog):
    hora = f'a las {prog["hora"]:02d}:00'
    if prog['frecuencia'] == SEMANAL:
        return f'Cada {DIAS[prog["dia_semana"]]} {hora}'
    if prog['frecuencia'] == MENSUAL:
        return f'El día {prog["dia_mes"]} de cada mes {hora}'
    return f'Cada día {hora}'


def siguiente(prog, desde):
    """La primera vez que le toca correr DESPUÉS de `desde` (hora local)."""
    desde = timezone.localtime(desde)
    tz = desde.tzinfo
    dia = desde.date()
    for _ in range(400):                        # alcanza para cualquier día del mes
        if (prog['frecuencia'] == DIARIA
                or (prog['frecuencia'] == SEMANAL and dia.weekday() == prog['dia_semana'])
                or (prog['frecuencia'] == MENSUAL and dia.day == prog['dia_mes'])):
            cuando = timezone.make_aware(datetime(dia.year, dia.month, dia.day, prog['hora']), tz)
            if cuando > desde:
                return cuando
        dia += timedelta(days=1)
    return desde + timedelta(days=1)


def reprogramar(auto, desde=None):
    auto.proxima_ejecucion = siguiente(programacion(auto), desde or timezone.now())


# ── Envío ─────────────────────────────────────────────────────────────────────

def destinatarios(auto):
    """Los seguidores que siguen en la empresa; sin seguidores, administradores y editores."""
    from apps.workspaces.models import Membership, ROLE_ADMIN, ROLE_EDITOR
    miembros = Membership.objects.filter(organization=auto.organization).select_related('user')
    if auto.pk and auto.seguidores.exists():
        ids = set(auto.seguidores.values_list('id', flat=True))
        return [m.user for m in miembros if m.user_id in ids]
    return [m.user for m in miembros.filter(role__in=[ROLE_ADMIN, ROLE_EDITOR])]


def _enviar(auto, titulo, detalle, enlace):
    gente = destinatarios(auto)
    avisar(gente, tipo=TIPO_AGENTE, titulo=titulo, detalle=detalle, enlace=enlace,
           organization=auto.organization)
    url = f'{getattr(settings, "FRONTEND_URL", "")}{enlace}'
    for u in gente:
        if auto.por_correo and u.email:
            try:
                send_mail(subject=f'Afable · {titulo}', message=f'{detalle}\n\n{url}',
                          from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'afable@localhost'),
                          recipient_list=[u.email], fail_silently=False)
            except Exception:
                logger.exception('automatización %s: no se pudo enviar el correo', auto.clave)
        if auto.por_whatsapp and getattr(u, 'telefono', ''):
            whatsapp.enviar(u.telefono, titulo, f'{detalle} {url}')


def ejecutar(auto, forzar=False, ahora=None):
    """Corre una automatización. Con `forzar` (Probar ahora) ignora la marca y no avisa a
    nadie ni la deja registrada. Devuelve {'aviso': bool, 'titulo', 'detalle'}."""
    org = auto.organization
    hoy = _hoy()
    ahora = ahora or timezone.now()
    try:
        r = FUNCIONES[auto.clave](org, hoy, forzar)
    except Exception as e:
        logger.exception('automatización %s falló', auto.clave)
        if not forzar:
            auto.ultimo_resultado = f'Error: {e}'[:500]
            auto.ultima_ejecucion = ahora
            auto.save(update_fields=['ultimo_resultado', 'ultima_ejecucion'])
        return {'aviso': False, 'titulo': None, 'detalle': f'No se pudo revisar: {e}'}

    if r is None or r[1] is None:
        if not forzar:
            auto.ultima_ejecucion = ahora
            auto.ultimo_resultado = 'Sin nada que avisar.'
            if r is not None:
                auto.marca = r[0]                      # el estado volvió a la normalidad
            auto.save(update_fields=['ultima_ejecucion', 'ultimo_resultado', 'marca'])
        return {'aviso': False, 'titulo': None, 'detalle': 'Hoy no hay nada que avisar.'}

    marca, titulo, detalle, enlace = r
    if not forzar and marca == auto.marca:
        auto.ultima_ejecucion = ahora
        auto.save(update_fields=['ultima_ejecucion'])
        return {'aviso': False, 'titulo': titulo, 'detalle': 'Ya se había avisado.'}

    if not forzar:
        _enviar(auto, titulo, detalle, enlace)
        auto.marca = marca
        auto.ultima_ejecucion = ahora
        auto.ultimo_resultado = f'{titulo}. {detalle}'[:500]
        auto.save(update_fields=['marca', 'ultima_ejecucion', 'ultimo_resultado'])
    return {'aviso': True, 'titulo': titulo, 'detalle': detalle, 'enlace': enlace}


def correr_pendientes(ahora=None):
    """Lo llama el proceso de automatizaciones en cada vuelta: corre las que les tocó."""
    ahora = ahora or timezone.now()
    corridas = 0
    for auto in AutomatizacionModulo.objects.filter(activa=True).select_related('organization'):
        if auto.clave not in FUNCIONES:
            continue
        if auto.proxima_ejecucion is None:
            # Recién activada o anterior a la programación: se agenda, no se corre de golpe.
            reprogramar(auto, ahora)
            auto.save(update_fields=['proxima_ejecucion'])
            continue
        if auto.proxima_ejecucion > ahora:
            continue
        ejecutar(auto, ahora=ahora)
        reprogramar(auto, ahora)
        auto.save(update_fields=['proxima_ejecucion'])
        corridas += 1
    return corridas

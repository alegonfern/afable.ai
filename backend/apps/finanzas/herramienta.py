"""La herramienta del chat para Finanzas: que el agente responda con los números de la empresa.

"¿Cuánto IVA pago este mes?", "¿quién me debe?", "¿cuánto puedo retirar?": el agente llama a
`consultar_finanzas` con la consulta que corresponde y responde con datos, no con estimaciones
propias. Devuelve resúmenes cortos (los modelos no necesitan cien filas para contestar).
"""

from datetime import date

from django.db.models import Q

from . import calculos, conciliacion, constantes as c, tesoreria
from .models import DocumentoTributario

CONSULTAS = ['resumen_mes', 'f29', 'por_cobrar', 'por_pagar', 'caja', 'gasto_por_categoria',
             'margen_proyectos', 'conciliacion', 'documentos', 'ventas']
MAX_DOCUMENTOS = 15
LIBROS = [clave for clave, _ in c.LIBROS]

ESPECIFICACION = {
    "name": "consultar_finanzas",
    "description": (
        "Consulta los números de la empresa calculados desde lo que cargó del SII (Registro de "
        "Compras y Ventas, boletas de honorarios) y sus cartolas bancarias. Úsala SIEMPRE que "
        "pregunten por ventas, gastos, ganancia, margen, IVA, F29, PPM, quién les debe, a quién "
        "le deben, caja, cuánto pueden retirar, gasto por categoría, proyectos o conciliación "
        "bancaria. Montos en pesos chilenos. Ingresos y gastos van SIN IVA. El F29 es una "
        "provisión estimada, no la declaración."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "consulta": {
                "type": "string", "enum": CONSULTAS,
                "description": (
                    "resumen_mes: ingresos, gastos, ganancia y margen del mes y del año · f29: "
                    "provisión del F29 por mes (IVA, PPM, retención, vencimiento, si está pagado) · "
                    "por_cobrar / por_pagar: pendientes, vencidos y los principales · caja: "
                    "disponible, cuánto puede retirar, meses de caja, saldo a 30 días · "
                    "gasto_por_categoria · margen_proyectos · conciliacion: cuánto está cuadrado "
                    "con el banco y qué falta · documentos: cuántos hay y cuáles (filtra por "
                    "libro, mes, contraparte, estado de pago) · ventas: lo vendido en el año por mes "
                    "y por cliente, y cuánto depende de su cliente más grande"
                ),
            },
            "libro": {"type": "string", "enum": LIBROS, "description": "solo para documentos"},
            "contraparte": {"type": "string", "description": "solo para documentos: parte del nombre o RUT"},
            "pendientes": {"type": "boolean", "description": "solo para documentos: true = solo los no pagados/cobrados"},
            "anio": {"type": "integer", "description": "año (por defecto el actual)"},
            "mes": {"type": "integer", "description": "mes 1-12 (por defecto el más reciente con datos)"},
        },
        "required": ["consulta"],
    },
}


def disponible_para(org):
    return DocumentoTributario.objects.filter(organization=org).exists()


def _mes_reciente(org, anio):
    ultimo = DocumentoTributario.objects.filter(organization=org, fecha__year=anio).order_by('-fecha').first()
    return ultimo.fecha.month if ultimo else date.today().month


def ejecutar(org, args):
    consulta = (args or {}).get('consulta')
    if consulta not in CONSULTAS:
        return {'error': f'consulta debe ser una de: {", ".join(CONSULTAS)}'}
    hoy = date.today()
    anio = int(args.get('anio') or hoy.year)
    mes = int(args.get('mes') or _mes_reciente(org, anio))

    if consulta == 'resumen_mes':
        r = calculos.resumen(org, anio)
        m = r['meses'][mes - 1]
        return {'anio': anio, 'mes': mes, 'mes_ingresos_sin_iva': m['ingresos'], 'mes_gastos_sin_iva': m['gastos'],
                'mes_ganancia': m['ganancia'], 'mes_margen_pct': m['margen'],
                'anio_ingresos': r['ingresos'], 'anio_gastos': r['gastos'], 'anio_ganancia': r['ganancia'],
                'meses_con_datos': [x['mes'] for x in r['meses'] if x['con_datos']]}
    if consulta == 'f29':
        r = calculos.f29(org, anio)
        return {'nota': 'Provisión estimada, no la declaración.', 'tasa_ppm_pct': r['tasa_ppm'],
                'tasa_ppm_confirmada': r['tasa_ppm_confirmada'], 'meses': r['meses']}
    if consulta in ('por_cobrar', 'por_pagar'):
        r = tesoreria.cuentas(org, 'cobrar' if consulta == 'por_cobrar' else 'pagar')
        return {'total': r['total'], 'vencido': r['vencido'], 'porcentaje_vencido': r['porcentaje_vencido'],
                'tramos': r['tramos'], 'mas_atrasados': r['prioridad'],
                'principales_contrapartes': r['por_contraparte'][:8]}
    if consulta == 'caja':
        r = tesoreria.caja(org)
        if r['disponible'] is None:
            r['nota'] = 'Sin cartolas cargadas: no se conoce el saldo. Que suba la cartola en Contabilidad › Conciliación.'
        return r
    if consulta == 'gasto_por_categoria':
        r = calculos.por_categoria(org, 'mes' if args.get('mes') else 'anio', anio, mes)
        return {'periodo': r['periodo'], 'gastos': r['gastos'], 'ingresos': r['ingresos']}
    if consulta == 'documentos':
        return _documentos(org, args, anio)
    if consulta == 'ventas':
        r = calculos.ventas(org, anio)
        r['clientes'] = r['clientes'][:10]
        return r
    if consulta == 'margen_proyectos':
        return calculos.margen_por_proyecto(org, anio)
    r = conciliacion.cuadre(org, anio, mes)
    return {k: r[k] for k in ('anio', 'mes', 'porcentaje', 'movimientos', 'cuadraron_solos',
                              'los_cuadro_usted', 'pendientes', 'por_identificar', 'posibles_traspasos',
                              'sin_explicar', 'anotado', 'cerrado')}


def _documentos(org, args, anio):
    """Cuántos documentos hay y los más recientes, con los filtros que pidan. El mes solo
    filtra si lo piden: "¿cuántas facturas de compra hay?" es del año, no del último mes."""
    qs = DocumentoTributario.objects.filter(organization=org, fecha__year=anio).select_related('categoria')
    if args.get('libro') in LIBROS:
        qs = qs.filter(libro=args['libro'])
    if args.get('mes'):
        qs = qs.filter(fecha__month=int(args['mes']))
    if args.get('contraparte'):
        t = str(args['contraparte']).strip()
        qs = qs.filter(Q(razon_social__icontains=t) | Q(rut__icontains=t))
    if args.get('pendientes'):
        qs = qs.filter(pagado=False)
    docs = list(qs.order_by('-fecha', '-folio'))
    por_tipo = {}
    for d in docs:
        nombre = c.TIPOS_DTE.get(d.tipo_documento, d.tipo_documento)
        por_tipo[nombre] = por_tipo.get(nombre, 0) + 1
    return {
        'anio': anio, 'filtros': {k: args[k] for k in ('libro', 'mes', 'contraparte', 'pendientes') if args.get(k)},
        'cantidad': len(docs), 'por_tipo': por_tipo,
        'total_con_iva': sum(d.signo * d.monto_total for d in docs),
        'sin_categoria': sum(1 for d in docs if not d.categoria_id),
        'pendientes_de_pago': sum(1 for d in docs if not d.pagado),
        'detalle_de_los_mas_recientes': len(docs[:MAX_DOCUMENTOS]),
        'mas_recientes': [{
            'fecha': d.fecha.isoformat(), 'libro': d.libro, 'tipo': c.TIPOS_DTE.get(d.tipo_documento, d.tipo_documento),
            'folio': d.folio, 'contraparte': d.razon_social or d.rut, 'total': d.signo * d.monto_total,
            'categoria': d.categoria.nombre if d.categoria else None, 'pagado': d.pagado,
        } for d in docs[:MAX_DOCUMENTOS]],
    }

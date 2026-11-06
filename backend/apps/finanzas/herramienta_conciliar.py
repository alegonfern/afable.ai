"""La herramienta del chat para CONCILIAR el banco (25-10-2026): "¿qué me falta conciliar?",
"ese abono de $4.998.000 es la factura 1026 de Café Central", "el cargo del seguro es un gasto
sin factura", "sí, es un traspaso entre mis cuentas".

`consultar_finanzas` solo lee el cuadre; esta lo resuelve, con las mismas funciones que usa la
pantalla de Conciliación (`conciliacion.py`), así las reglas son las mismas: un mes cerrado no
se toca, y lo que cambia algo se muestra primero y se hace solo con el sí del usuario
(`confirmado: true`). Escribir pide rol de editor.
"""
from datetime import date

from . import conciliacion
from .models import CierreMes, DocumentoTributario, MovimientoBancario

ACCIONES_QUE_CAMBIAN = ['conciliar', 'identificar', 'traspaso', 'no_es_traspaso', 'deshacer']
TIPOS = [clave for clave, _ in MovimientoBancario.TIPOS_SIN_DOCUMENTO]
NOMBRE_TIPO = dict(MovimientoBancario.TIPOS_SIN_DOCUMENTO)
MAX_FILAS = 10

ESPECIFICACION = {
    "name": "conciliar_banco",
    "description": (
        "Conciliación bancaria: ver los movimientos del banco que faltan por explicar (con las "
        "facturas que podrían ser) y RESOLVERLOS: conciliar un movimiento con su o sus documentos, "
        "identificar un cargo o abono sin documento (comisión, remuneraciones, impuestos, retiro del "
        "dueño, aporte, préstamo, otro), confirmar o descartar un traspaso entre cuentas propias, "
        "deshacer, o volver a cruzar automáticamente lo que es claro. Para conciliar, identificar, "
        "traspaso, no_es_traspaso o deshacer: llama primero SIN confirmado, muéstrale al usuario lo "
        "que va a pasar, y solo si dice que sí vuelve a llamar con confirmado=true."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "accion": {
                "type": "string", "enum": ['pendientes', 'cruzar'] + ACCIONES_QUE_CAMBIAN,
                "description": (
                    "pendientes (lo que falta, con candidatos; usa anio y mes si los dan) · cruzar "
                    "(concilia solo lo claro) · conciliar (movimiento + documentos) · identificar "
                    "(movimiento + tipo, nota opcional) · traspaso · no_es_traspaso · deshacer (movimiento)"
                ),
            },
            "movimiento": {"type": "integer", "description": "id del movimiento (viene en pendientes)"},
            "documentos": {"type": "array", "items": {"type": "integer"},
                           "description": "ids de los documentos que paga el movimiento (vienen en candidatos)"},
            "tipo": {"type": "string", "enum": TIPOS, "description": "para identificar"},
            "nota": {"type": "string", "description": "para identificar: detalle opcional"},
            "anio": {"type": "integer"},
            "mes": {"type": "integer", "description": "1-12"},
            "confirmado": {"type": "boolean", "description": "true solo después de que el usuario dijo que sí"},
        },
        "required": ["accion"],
    },
}


def _clp(n):
    return f'{"-" if n < 0 else ""}${abs(round(n)):,}'.replace(',', '.')


def _doc(d, diferencia=None, nombre=None):
    r = {'id': d.id, 'folio': d.folio, 'razon_social': d.razon_social, 'fecha': d.fecha.isoformat(),
         'libro': d.libro, 'monto': conciliacion.monto_a_pagar(d)}
    if diferencia is not None:
        r['diferencia'] = diferencia
        r['nombre_en_la_glosa'] = bool(nombre)
    return r


def _mov(m, con_candidatos=False):
    r = {'id': m.id, 'fecha': m.fecha.isoformat(), 'descripcion': m.descripcion, 'monto': m.monto,
         'cuenta': str(m.cuenta), 'estado': m.estado}
    pareja = m.pareja or MovimientoBancario.objects.filter(pareja=m).first()
    if pareja:
        r['posible_traspaso_con'] = {'id': pareja.id, 'cuenta': str(pareja.cuenta), 'monto': pareja.monto}
    if con_candidatos and m.estado == MovimientoBancario.PENDIENTE and not pareja:
        tolerancia = max(1000, abs(m.monto) * 5 // 100)
        r['candidatos'] = [_doc(d, dif, nom) for d, dif, nom in conciliacion.candidatos(m)
                           if dif <= tolerancia or nom][:4]
    return r


def _puede_escribir(org, usuario):
    from apps.workspaces.models import ROLE_ORDER, Membership
    m = Membership.objects.filter(organization=org, user=usuario).first() if usuario else None
    return m is not None and ROLE_ORDER.index(m.role) >= ROLE_ORDER.index('editor')


def _mes_con_pendientes(org):
    p = (MovimientoBancario.objects.filter(organization=org, estado=MovimientoBancario.PENDIENTE)
         .order_by('-fecha').first())
    if p:
        return p.fecha.year, p.fecha.month
    meses = conciliacion.meses_con_movimientos(org)
    return meses[0] if meses else (date.today().year, date.today().month)


def ejecutar(org, args, usuario=None):
    args = args or {}
    accion = args.get('accion')

    if accion == 'pendientes':
        anio, mes = ((int(args['anio']), int(args['mes'])) if args.get('anio') and args.get('mes')
                     else _mes_con_pendientes(org))
        qs = (MovimientoBancario.objects.filter(organization=org, estado=MovimientoBancario.PENDIENTE,
                                                fecha__year=anio, fecha__month=mes)
              .select_related('cuenta', 'pareja__cuenta').order_by('fecha', 'id'))
        cuadre = conciliacion.cuadre(org, anio, mes)
        return {'anio': anio, 'mes': mes, 'porcentaje_cuadrado': cuadre['porcentaje'],
                'pendientes': [_mov(m, con_candidatos=True) for m in qs[:MAX_FILAS]],
                'cantidad': qs.count(), 'enlace': '/app/contabilidad/conciliacion'}

    if accion not in ['cruzar'] + ACCIONES_QUE_CAMBIAN:
        return {'error': 'Acción no válida.'}
    if not _puede_escribir(org, usuario):
        return {'error': 'Para conciliar hace falta ser editor de la empresa.'}

    if accion == 'cruzar':
        cruzados = conciliacion.cruzar(org)
        anio, mes = _mes_con_pendientes(org)
        cuadre = conciliacion.cuadre(org, anio, mes)
        return {'cruzados': cruzados, 'anio': anio, 'mes': mes, 'porcentaje_cuadrado': cuadre['porcentaje'],
                'quedan_pendientes': cuadre['pendientes'], 'enlace': '/app/contabilidad/conciliacion'}

    m = (MovimientoBancario.objects.filter(organization=org, pk=args.get('movimiento'))
         .select_related('cuenta').first())
    if not m:
        return {'error': f'No existe el movimiento {args.get("movimiento")}. Pide primero los pendientes.'}
    if CierreMes.objects.filter(organization=org, anio=m.fecha.year, mes=m.fecha.month).exists():
        return {'error': 'Ese mes está cerrado. Hay que reabrirlo en Contabilidad › Conciliación para cambiarlo.'}
    quien = f'{m.descripcion} ({_clp(m.monto)}, {m.fecha.strftime("%d-%m")})'

    if accion == 'conciliar':
        docs = list(DocumentoTributario.objects.filter(organization=org, id__in=args.get('documentos') or []))
        if not docs:
            return {'error': 'Faltan los documentos: elige entre los candidatos del movimiento.'}
        suma = sum(conciliacion.monto_a_pagar(d) for d in docs)
        diferencia = abs(m.monto) - abs(suma)
        plan = (f'Conciliar {quien} con ' + ', '.join(f'folio {d.folio} de {d.razon_social} ({_clp(conciliacion.monto_a_pagar(d))})' for d in docs)
                + (f'. Queda una diferencia de {_clp(abs(diferencia))} ({"menos" if diferencia < 0 else "más"} que los documentos)'
                   if diferencia else '') + '. Los documentos quedan pagados.')
        hacer = lambda: conciliacion.conciliar_manual(m, docs)
    elif accion == 'identificar':
        tipo = args.get('tipo')
        if tipo not in TIPOS:
            return {'error': f'Indica el tipo: {", ".join(TIPOS)}.'}
        plan = f'Marcar {quien} como «{NOMBRE_TIPO[tipo]}», sin documento' + (f': {args["nota"]}' if args.get('nota') else '') + '.'
        hacer = lambda: conciliacion.identificar(m, tipo, args.get('nota') or '')
    elif accion == 'traspaso':
        plan = f'Marcar {quien} y su contraparte como traspaso entre cuentas propias.'
        hacer = lambda: conciliacion.confirmar_traspaso(m)
    elif accion == 'no_es_traspaso':
        plan = f'Descartar el traspaso sugerido para {quien}: vuelve a quedar por explicar.'
        hacer = lambda: conciliacion.descartar_traspaso(m)
    else:
        plan = f'Deshacer lo hecho con {quien}: vuelve a pendiente y sus documentos quedan por pagar.'
        hacer = lambda: conciliacion.deshacer(m)

    if not args.get('confirmado'):
        return {'requiere_confirmacion': True, 'se_hara': plan,
                'instruccion': 'Muéstrale esto al usuario y pregúntale si confirma. Solo si dice que sí, vuelve a llamar con confirmado=true.'}
    hacer()
    m.refresh_from_db()
    cuadre = conciliacion.cuadre(org, m.fecha.year, m.fecha.month)
    return {'hecho': plan, 'estado': m.estado, 'porcentaje_cuadrado': cuadre['porcentaje'],
            'quedan_pendientes': cuadre['pendientes'], 'enlace': '/app/contabilidad/conciliacion'}

"""La herramienta del chat para Compras y Ventas: consultar y OPERAR desde el chat.

"Cotícele 10 sacos de cemento a Constructora Andes", "¿qué órdenes faltan por facturar?",
"confirma la OV-0012", "llegó todo lo de la OC-0003". Pasa por `operaciones` y `facturacion`, los
mismos que usa la pantalla, así las reglas son las mismas.

Escribir pide rol de editor. Crear una cotización deja un BORRADOR (no compromete nada, como en
Odoo). Confirmar, cancelar y registrar entregas cambian cosas que otros ven: la primera llamada
devuelve lo que se va a hacer y el agente tiene que pedir el sí del usuario antes de repetirla
con `confirmado: true`.
"""

from decimal import Decimal

from django.db import transaction
from django.db.models import Q

from apps.finanzas.models import Contacto

from . import emision, facturacion, operaciones as op
from .models import CLP, COMPRA, VENTA, ConfiguracionComercial, Pedido, Producto, stock

CONSULTAS = ['resumen', 'pedidos', 'pedido', 'por_facturar', 'productos', 'stock', 'contactos', 'reporte']
ACCIONES = ['crear_cotizacion', 'confirmar', 'cancelar', 'registrar_entrega', 'crear_contacto', 'crear_producto',
            'duplicar', 'registrar_pago', 'enviar_correo', 'reponer_stock',
            # 25-10-2026: emitir la factura electrónica y recibir la del proveedor.
            'facturar', 'facturar_directo', 'registrar_factura_proveedor']
MAX_FILAS = 15

ESPECIFICACION = {
    "name": "compras_ventas",
    "description": (
        "Compras y Ventas de la empresa (cotizaciones, órdenes de venta y de compra, entregas, "
        "recepciones, productos, stock, clientes y proveedores, facturas electrónicas de venta y "
        "facturas de proveedor). Úsala para CONSULTAR (accion = una de las consultas) o para HACER "
        "cosas (accion = una de las acciones). FACTURAR: 'facturar' emite la factura electrónica de "
        "una orden de venta (numero); 'facturar_directo' factura lo que pida el usuario sin orden "
        "previa (contacto + lineas: se crea la orden y se factura). RECIBIR: "
        "'registrar_factura_proveedor' anota en el Libro de Compras la factura de un proveedor con "
        "los datos que dé o que leas del PDF o XML adjunto (rut, contacto, folio, fecha, neto, iva, "
        "total, categoria si la sabes, numero de la orden de compra si corresponde). Para confirmar, "
        "cancelar, registrar una entrega, facturar o registrar una factura de proveedor: llama "
        "primero SIN confirmado, muéstrale al usuario lo que va a pasar, y solo si dice que sí vuelve "
        "a llamar con confirmado=true. Crear una cotización no necesita confirmación (queda en "
        "borrador). Montos sin IVA salvo que diga 'total'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "accion": {
                "type": "string", "enum": CONSULTAS + ACCIONES,
                "description": (
                    "Consultas: resumen (embudo: cotizaciones abiertas, por entregar, por facturar) · "
                    "pedidos (lista; filtra con tipo, vista, contacto) · pedido (detalle de uno, por numero) · "
                    "por_facturar · productos · stock · contactos · reporte (tipo, por = producto|contacto|mes, "
                    "desde, hasta: ventas con margen o compras). Acciones: crear_cotizacion (tipo, "
                    "contacto, lineas, moneda) · confirmar · cancelar · registrar_entrega (numero; entrega o "
                    "recibe todo lo pendiente) · crear_contacto (contacto = nombre, rut, rol) · crear_producto · "
                    "duplicar (numero; deja una cotización nueva igual) · registrar_pago (numero, monto con IVA, "
                    "medio: el cobro de una OV o el pago de una OC) · enviar_correo (numero; le manda el PDF al "
                    "contacto) · reponer_stock (arma las solicitudes de compra de lo que está bajo el mínimo)"
                ),
            },
            "tipo": {"type": "string", "enum": [VENTA, COMPRA], "description": "venta o compra"},
            "vista": {"type": "string", "enum": ["cotizaciones", "ordenes"], "description": "solo para pedidos"},
            "numero": {"type": "string", "description": "número del pedido, p. ej. OV-0012 u OC-0003"},
            "contacto": {"type": "string", "description": "nombre o RUT del cliente o proveedor"},
            "rut": {"type": "string", "description": "solo para crear_contacto"},
            "rol": {"type": "string", "enum": ["cliente", "proveedor"], "description": "para contactos y crear_contacto"},
            "busqueda": {"type": "string", "description": "texto a buscar en productos o contactos"},
            "lineas": {
                "type": "array", "description": "para crear_cotizacion",
                "items": {"type": "object", "properties": {
                    "producto": {"type": "string", "description": "nombre o código del producto (opcional)"},
                    "descripcion": {"type": "string"},
                    "cantidad": {"type": "number"},
                    "precio_unitario": {"type": "number", "description": "sin IVA; si no se da, el del producto"},
                }},
            },
            "moneda": {"type": "string", "enum": ["CLP", "USD", "UF"]},
            "nombre": {"type": "string", "description": "para crear_producto"},
            "precio": {"type": "number", "description": "para crear_producto: precio de venta sin IVA"},
            "monto": {"type": "number", "description": "para registrar_pago: en pesos, con IVA"},
            "medio": {"type": "string", "enum": ["transferencia", "efectivo", "tarjeta", "cheque", "otro"]},
            "por": {"type": "string", "enum": ["producto", "contacto", "mes"], "description": "para reporte"},
            "desde": {"type": "string", "description": "para reporte: AAAA-MM-DD (por defecto, el 1 de enero)"},
            "hasta": {"type": "string", "description": "para reporte: AAAA-MM-DD (por defecto, hoy)"},
            "que": {"type": "string", "enum": ["vendido", "entregado"],
                    "description": "para facturar: lo vendido o lo entregado (solo cuando el usuario ya lo eligió)"},
            "folio": {"type": "string", "description": "para registrar_factura_proveedor"},
            "fecha": {"type": "string", "description": "para registrar_factura_proveedor: AAAA-MM-DD"},
            "neto": {"type": "number", "description": "para registrar_factura_proveedor"},
            "iva": {"type": "number", "description": "para registrar_factura_proveedor"},
            "total": {"type": "number", "description": "para registrar_factura_proveedor"},
            "categoria": {"type": "string", "description": "para registrar_factura_proveedor: categoría de gasto"},
            "tipo_documento": {"type": "string", "description": "para registrar_factura_proveedor: 33 factura, 34 exenta (por defecto 33)"},
            "confirmado": {"type": "boolean", "description": "true solo después de que el usuario dijo que sí"},
        },
        "required": ["accion"],
    },
}


def _clp(n):
    return f'${round(n):,}'.replace(',', '.')


def _contacto(org, texto, rol=None):
    texto = str(texto or '').strip()
    if not texto:
        return None, 'Falta el cliente o proveedor.'
    qs = Contacto.objects.filter(organization=org)
    if rol == 'cliente':
        qs = qs.filter(es_cliente=True)
    elif rol == 'proveedor':
        qs = qs.filter(es_proveedor=True)
    exacto = qs.filter(Q(rut__iexact=texto) | Q(razon_social__iexact=texto)).first()
    if exacto:
        return exacto, None
    parecidos = list(qs.filter(Q(razon_social__icontains=texto) | Q(rut__icontains=texto))[:5])
    if len(parecidos) == 1:
        return parecidos[0], None
    if not parecidos:
        return None, f'No encuentro a «{texto}». ¿Lo creo como contacto nuevo? (necesito el RUT)'
    return None, 'Hay varios parecidos: ' + ', '.join(c.razon_social for c in parecidos) + '. ¿Cuál?'


def _producto(org, texto):
    texto = str(texto or '').strip()
    if not texto:
        return None
    qs = Producto.objects.filter(organization=org, activo=True)
    return (qs.filter(Q(codigo__iexact=texto) | Q(nombre__iexact=texto)).first()
            or (lambda xs: xs[0] if len(xs) == 1 else None)(list(qs.filter(nombre__icontains=texto)[:2])))


def _pedido_por_numero(org, numero):
    return Pedido.objects.filter(organization=org, numero__iexact=str(numero or '').strip()).select_related('contacto').first()


def _fila(p, cfg):
    e = facturacion.estado(p, cfg)
    return {'numero': p.numero, 'contacto': p.contacto.razon_social, 'fecha': p.fecha.isoformat(),
            'etapa': e['etapa'], 'neto_clp': p.base_clp, 'moneda': p.moneda,
            'por_facturar_clp': e['por_facturar_clp'], 'entregado_pct': e['entregado_pct'],
            'enlace': f'/app/{"ventas" if p.tipo == VENTA else "compras"}/ordenes/{p.id}'}


def _emitida(doc, p):
    return {'factura_emitida': {'id': doc.id, 'folio': doc.folio, 'fecha': doc.fecha.isoformat(),
                                'cliente': doc.razon_social, 'rut': doc.rut, 'neto': doc.monto_neto,
                                'iva': doc.monto_iva, 'total': doc.monto_total},
            'pedido': p.numero, 'etapa': facturacion.etapa(p), 'enlace': f'/app/ventas/ordenes/{p.id}',
            'nota': 'Emitida y aceptada. El PDF se descarga desde la tarjeta o desde la orden.'}


def _registrar_factura_proveedor(org, args, usuario):
    """La factura de un proveedor, al Libro de Compras: la IA la lee (del PDF, del XML o de lo que
    le dicten) y aquí se anota como lo haría la carga del Registro de Compras, con su categoría y,
    si se indica, amarrada a su orden de compra. Si después se carga el RCV, no se duplica: el
    documento se reconoce por RUT, tipo y folio."""
    from datetime import date, timedelta
    from apps.finanzas import constantes as fc
    from apps.finanzas.models import Categoria, Contraparte, DocumentoTributario
    from .views import _normalizar_rut
    rut = _normalizar_rut(args.get('rut'))
    folio = str(args.get('folio') or '').strip()
    if not rut or not folio:
        return {'error': 'Faltan el RUT del proveedor y el folio de la factura.'}
    tipo_doc = str(args.get('tipo_documento') or '33')
    try:
        fecha = date.fromisoformat(str(args.get('fecha') or date.today().isoformat()))
        neto = int(round(float(args.get('neto') or 0)))
        iva = int(round(float(args.get('iva') if args.get('iva') is not None else (neto * 0.19 if tipo_doc == '33' else 0))))
        total = int(round(float(args.get('total') or (neto + iva))))
    except (TypeError, ValueError):
        return {'error': 'Fecha o montos no válidos (fecha AAAA-MM-DD, montos en pesos).'}
    if total <= 0:
        return {'error': 'Falta el monto de la factura.'}
    if DocumentoTributario.objects.filter(organization=org, libro=fc.LIBRO_COMPRAS, tipo_documento=tipo_doc,
                                          rut=rut, folio=folio).exists():
        return {'error': f'La factura {folio} de ese proveedor ya está en el Libro de Compras.'}
    contacto = Contacto.objects.filter(organization=org, rut=rut).first()
    nombre = (contacto.razon_social if contacto else str(args.get('contacto') or '').strip()) or rut
    categoria = None
    if args.get('categoria'):
        categoria = (Categoria.objects.filter(organization=org, nombre__iexact=args['categoria']).first()
                     or Categoria.objects.filter(organization=org, nombre__icontains=args['categoria']).first())
    cp = Contraparte.objects.filter(organization=org, libro=fc.LIBRO_COMPRAS, rut=rut).first()
    if categoria is None and cp and cp.regla_activa:
        categoria = cp.categoria
    oc = _pedido_por_numero(org, args.get('numero')) if args.get('numero') else None
    if args.get('numero') and (oc is None or oc.tipo != COMPRA):
        return {'error': f'No existe la orden de compra {args.get("numero")}.'}

    plan = (f'Registrar en el Libro de Compras la factura {folio} de {nombre} ({rut}) del {fecha.strftime("%d-%m-%Y")}: '
            f'{_clp(neto)} neto + {_clp(iva)} IVA = {_clp(total)}'
            + (f', en la categoría «{categoria.nombre}»' if categoria else ', sin categoría (queda por revisar)')
            + (f', amarrada a {oc.numero}' if oc else '') + '.')
    if not args.get('confirmado'):
        return {'requiere_confirmacion': True, 'se_hara': plan,
                'instruccion': 'Muéstrale esto al usuario y pregúntale si confirma. Solo si dice que sí, vuelve a llamar con confirmado=true.'}
    if contacto is None:
        contacto = Contacto.objects.create(organization=org, rut=rut, razon_social=nombre[:255], es_proveedor=True)
    elif not contacto.es_proveedor:
        contacto.es_proveedor = True
        contacto.save(update_fields=['es_proveedor'])
    if cp is None:
        cp = Contraparte.objects.create(organization=org, libro=fc.LIBRO_COMPRAS, rut=rut, razon_social=nombre[:255],
                                        contacto=contacto)
    doc = DocumentoTributario.objects.create(
        organization=org, libro=fc.LIBRO_COMPRAS, tipo_documento=tipo_doc, folio=folio, rut=rut, razon_social=nombre[:255],
        fecha=fecha, fecha_vencimiento=fecha + timedelta(days=cp.plazo), monto_neto=neto if tipo_doc == '33' else 0,
        monto_exento=0 if tipo_doc == '33' else neto, monto_iva=iva, monto_total=total, contraparte=cp, categoria=categoria,
        estado=DocumentoTributario.CONFIRMADO if categoria else DocumentoTributario.POR_REVISAR,
    )
    if oc:
        facturacion.vincular(oc, doc, usuario=usuario)
    return {'registrada': {'id': doc.id, 'folio': folio, 'proveedor': nombre, 'rut': rut, 'fecha': fecha.isoformat(),
                           'neto': neto, 'iva': iva, 'total': total, 'categoria': categoria.nombre if categoria else None,
                           'orden': oc.numero if oc else None},
            'enlace': '/app/contabilidad/documentos'}


def _puede_escribir(org, usuario):
    from apps.workspaces.models import ROLE_ORDER, Membership
    m = Membership.objects.filter(organization=org, user=usuario).first() if usuario else None
    return m is not None and ROLE_ORDER.index(m.role) >= ROLE_ORDER.index('editor')


def ejecutar(org, args, usuario=None):
    accion = args.get('accion')
    cfg = ConfiguracionComercial.de(org)
    tipo = args.get('tipo') if args.get('tipo') in (VENTA, COMPRA) else None
    try:
        if accion in ACCIONES:
            if not _puede_escribir(org, usuario):
                return {'error': 'Para hacer cambios en compras y ventas hace falta ser editor de la empresa.'}
            with transaction.atomic():
                return _accion(org, accion, args, tipo, cfg, usuario)
        return _consulta(org, accion, args, tipo, cfg)
    except op.ErrorComercial as e:
        return {'error': str(e)}


def _consulta(org, accion, args, tipo, cfg):
    if accion == 'resumen':
        out = {}
        for t in ([tipo] if tipo else [VENTA, COMPRA]):
            filas = facturacion.por_facturar(org, t)
            abiertas = Pedido.objects.filter(organization=org, tipo=t, estado__in=[Pedido.BORRADOR, Pedido.ENVIADO])
            out[t] = {'cotizaciones_abiertas': abiertas.count(),
                      'cotizado_clp': sum(p.base_clp for p in abiertas),
                      'ordenes_por_facturar': len(filas),
                      'por_facturar_clp': sum(e['por_facturar_clp'] for _, e in filas)}
        return out
    if accion == 'pedidos':
        qs = Pedido.objects.filter(organization=org).select_related('contacto').prefetch_related('lineas')
        if tipo:
            qs = qs.filter(tipo=tipo)
        if args.get('vista') == 'cotizaciones':
            qs = qs.filter(estado__in=[Pedido.BORRADOR, Pedido.ENVIADO])
        elif args.get('vista') == 'ordenes':
            qs = qs.filter(estado=Pedido.CONFIRMADO)
        if args.get('contacto'):
            t = str(args['contacto'])
            qs = qs.filter(Q(contacto__razon_social__icontains=t) | Q(contacto__rut__icontains=t))
        total = qs.count()
        return {'cantidad': total, 'mostrados': min(total, MAX_FILAS), 'pedidos': [_fila(p, cfg) for p in qs[:MAX_FILAS]]}
    if accion == 'pedido':
        p = _pedido_por_numero(org, args.get('numero'))
        if not p:
            return {'error': f'No existe el pedido {args.get("numero")}.'}
        e = facturacion.estado(p, cfg)
        return {**_fila(p, cfg), 'diferencias': e['diferencias'], 'facturado_clp': e['facturado_clp'],
                'total': str(p.total), 'pagado_clp': op.pagado(p),
                'por_pagar_clp': max(p.a_pesos(p.total) - op.pagado(p), 0) if p.es_orden else 0, 'lineas': [
                    {'descripcion': l.descripcion, 'cantidad': str(l.cantidad.normalize()), 'precio': str(l.precio_unitario.normalize()),
                     'entregado': str(l.cantidad_entregada.normalize())} for l in p.lineas.all()]}
    if accion == 'por_facturar':
        out = []
        for t in ([tipo] if tipo else [VENTA, COMPRA]):
            out += [{**_fila(p, cfg), 'diferencias': e['diferencias']} for p, e in facturacion.por_facturar(org, t)]
        return {'cantidad': len(out), 'pedidos': out[:MAX_FILAS]}
    if accion in ('productos', 'stock'):
        qs = Producto.objects.filter(organization=org, activo=True)
        if accion == 'stock':
            qs = qs.filter(tipo=Producto.ALMACENABLE)
        if args.get('busqueda'):
            qs = qs.filter(Q(nombre__icontains=args['busqueda']) | Q(codigo__icontains=args['busqueda']))
        hay = {}
        for (pid, _), c in stock(org).items():
            hay[pid] = hay.get(pid, Decimal('0')) + c
        return {'inventario': cfg.get_nivel_inventario_display(), 'productos': [{
            'nombre': p.nombre, 'codigo': p.codigo, 'tipo': p.tipo, 'precio_venta': str(p.precio_venta.normalize()),
            'costo': str(p.costo.normalize()), 'unidad': p.unidad,
            **({'stock': str(hay.get(p.id, Decimal('0')).normalize()), 'stock_minimo': str(p.stock_minimo.normalize())}
               if p.lleva_stock and cfg.con_inventario else {}),
        } for p in qs[:MAX_FILAS]]}
    if accion == 'contactos':
        qs = Contacto.objects.filter(organization=org)
        if args.get('rol') == 'cliente':
            qs = qs.filter(es_cliente=True)
        elif args.get('rol') == 'proveedor':
            qs = qs.filter(es_proveedor=True)
        if args.get('busqueda'):
            qs = qs.filter(Q(razon_social__icontains=args['busqueda']) | Q(rut__icontains=args['busqueda']))
        return {'cantidad': qs.count(), 'contactos': [
            {'nombre': c.razon_social, 'rut': c.rut, 'cliente': c.es_cliente, 'proveedor': c.es_proveedor,
             'email': c.email} for c in qs[:MAX_FILAS]]}
    if accion == 'reporte':
        from datetime import date

        from django.utils import timezone

        from . import reportes
        hoy = timezone.localdate()
        try:
            desde = date.fromisoformat(args.get('desde') or hoy.replace(month=1, day=1).isoformat())
            hasta = date.fromisoformat(args.get('hasta') or hoy.isoformat())
        except ValueError:
            return {'error': 'Fecha no válida (use AAAA-MM-DD).'}
        por = args.get('por') if args.get('por') in ('producto', 'contacto', 'mes') else 'producto'
        datos = reportes.generar(org, tipo or VENTA, desde, hasta, por)
        return {'desde': desde.isoformat(), 'hasta': hasta.isoformat(), 'total': datos['total'],
                'filas': datos['filas'][:MAX_FILAS], 'cantidad': len(datos['filas']),
                'enlace': f'/app/{"compras" if tipo == COMPRA else "ventas"}/reportes'}
    return {'error': 'Consulta no válida.'}


def _accion(org, accion, args, tipo, cfg, usuario):
    if accion == 'crear_contacto':
        nombre = str(args.get('contacto') or args.get('nombre') or '').strip()
        if not nombre:
            return {'error': 'Falta el nombre.'}
        from .views import _normalizar_rut
        rut = _normalizar_rut(args.get('rut'))
        if rut and Contacto.objects.filter(organization=org, rut=rut).exists():
            return {'error': 'Ya existe un contacto con ese RUT.'}
        c = Contacto.objects.create(organization=org, rut=rut, razon_social=nombre[:255],
                                    es_cliente=args.get('rol') != 'proveedor', es_proveedor=args.get('rol') == 'proveedor')
        return {'creado': c.razon_social, 'rut': c.rut, 'enlace': f'/app/{"compras/proveedores" if c.es_proveedor else "ventas/clientes"}'}

    if accion == 'crear_producto':
        nombre = str(args.get('nombre') or '').strip()
        if not nombre:
            return {'error': 'Falta el nombre del producto.'}
        p = Producto.objects.create(organization=org, nombre=nombre[:200],
                                    precio_venta=op.decimal(args.get('precio') or 0, 'El precio', 0))
        return {'creado': p.nombre, 'precio_venta': str(p.precio_venta.normalize()), 'enlace': '/app/ventas/productos'}

    if accion == 'crear_cotizacion':
        if not tipo:
            return {'error': 'Indique si es de venta o de compra.'}
        contacto, error = _contacto(org, args.get('contacto'))
        if error:
            return {'error': error}
        lineas = []
        for l in args.get('lineas') or []:
            prod = _producto(org, l.get('producto'))
            lineas.append({'producto': prod.id if prod else None,
                           'descripcion': l.get('descripcion') or (prod.nombre if prod else l.get('producto')),
                           'cantidad': l.get('cantidad', 1), 'precio_unitario': l.get('precio_unitario')})
        if not lineas:
            return {'error': 'Faltan las líneas: qué productos o servicios y cuántos.'}
        p = op.crear_pedido(org, tipo, contacto, usuario, **({'moneda': args['moneda']} if args.get('moneda') else {}))
        if p.moneda != CLP:
            from . import cambio
            v = cambio.valor(p.moneda, p.fecha)
            if v:
                p.tipo_cambio = v
                p.save(update_fields=['tipo_cambio'])
        op.guardar_lineas(p, lineas)
        return {'creada': p.numero, 'etapa': facturacion.etapa(p), 'contacto': contacto.razon_social,
                'neto': str(p.neto), 'iva': str(p.iva), 'total': str(p.total), 'moneda': p.moneda,
                'enlace': f'/app/{"ventas" if tipo == VENTA else "compras"}/ordenes/{p.id}',
                'nota': 'Quedó en borrador: se puede revisar, descargar en PDF y enviar desde la pantalla.'}

    if accion == 'facturar_directo':
        contacto, error = _contacto(org, args.get('contacto'), 'cliente')
        if error:
            return {'error': error}
        if not contacto.rut:
            return {'error': f'{contacto.razon_social} no tiene RUT en su ficha: agréguelo para facturarle.'}
        lineas = []
        for l in args.get('lineas') or []:
            prod = _producto(org, l.get('producto'))
            precio = l.get('precio_unitario')
            if precio is None and prod is None:
                return {'error': f'Falta el precio de «{l.get("descripcion") or l.get("producto")}».'}
            if precio is None:
                precio = op.precio_para(prod, contacto, VENTA)
            lineas.append({'producto': prod.id if prod else None,
                           'descripcion': l.get('descripcion') or (prod.nombre if prod else l.get('producto')),
                           'cantidad': l.get('cantidad', 1), 'precio_unitario': precio})
        if not lineas:
            return {'error': 'Faltan las líneas: qué se factura, cuánto y a qué precio.'}
        if not args.get('confirmado'):
            neto = sum(Decimal(str(l['cantidad'])) * Decimal(str(l['precio_unitario'])) for l in lineas)
            detalle = '; '.join(f'{l["cantidad"]} × {l["descripcion"]}' for l in lineas)
            return {'requiere_confirmacion': True,
                    'se_hara': (f'Emitir una factura electrónica a {contacto.razon_social} ({contacto.rut}) por {detalle}: '
                                f'{_clp(neto)} neto + IVA = {_clp(round(neto * Decimal("1.19")))}. Queda su orden de venta en Ventas.'),
                    'instruccion': 'Muéstrale esto al usuario y pregúntale si confirma. Solo si dice que sí, vuelve a llamar con confirmado=true.'}
        p = op.crear_pedido(org, VENTA, contacto, usuario)
        op.guardar_lineas(p, lineas)
        op.confirmar(p)
        return _emitida(emision.emitir(p, monto=p.base_clp, usuario=usuario), p)

    if accion == 'registrar_factura_proveedor':
        return _registrar_factura_proveedor(org, args, usuario)

    if accion == 'reponer_stock':
        bajos = op.productos_bajo_minimo(org)
        if not cfg.con_inventario or not bajos:
            return {'error': 'No hay productos bajo el stock mínimo (o el inventario está desactivado).'}
        plan = 'Armar solicitudes de compra (en borrador) para: ' + '; '.join(
            f'{x.nombre} (hay {hay.normalize()}, mínimo {x.stock_minimo.normalize()})' for x, hay in bajos[:MAX_FILAS]) + '.'
        if not args.get('confirmado'):
            return {'requiere_confirmacion': True, 'se_hara': plan,
                    'instruccion': 'Muéstrale esto al usuario y pregúntale si confirma. Solo si dice que sí, vuelve a llamar con confirmado=true.'}
        creadas, sin = op.reponer_stock(org, usuario)
        return {'creadas': [f'{x.numero} a {x.contacto.razon_social}' for x in creadas],
                'sin_proveedor': [x.nombre for x in sin], 'enlace': '/app/compras/cotizaciones',
                'nota': 'Quedaron en borrador para revisar y enviar. A los productos sin proveedor hay que agregarles uno con precio en su ficha.'}

    p = _pedido_por_numero(org, args.get('numero'))
    if not p:
        return {'error': f'No existe el pedido {args.get("numero")}.'}
    venta = p.tipo == VENTA
    if accion == 'duplicar':
        copia = op.duplicar(p, usuario)
        return {'creada': copia.numero, 'copia_de': p.numero, 'etapa': facturacion.etapa(copia),
                'enlace': f'/app/{"ventas" if venta else "compras"}/cotizaciones/{copia.id}'}
    if accion == 'confirmar':
        plan = (f'Confirmar {p.numero} de {p.contacto.razon_social} por {_clp(p.base_clp)} sin IVA: pasa a ser orden de '
                f'{"venta" if venta else "compra"}. Mientras no tenga entregas ni facturas puede volver a cotización.')
        hacer = lambda: op.confirmar(p)
    elif accion == 'cancelar':
        plan = f'Cancelar {p.numero} de {p.contacto.razon_social}.'
        hacer = lambda: op.cancelar(p)
    elif accion == 'registrar_entrega':
        pendientes = [l for l in p.lineas.all() if l.pendiente_entrega > 0]
        if not pendientes:
            return {'error': f'{p.numero} no tiene nada pendiente.'}
        detalle = '; '.join(f'{l.pendiente_entrega.normalize()} {l.unidad} de {l.descripcion}' for l in pendientes)
        plan = f'Registrar {"la entrega" if venta else "la recepción"} de todo lo pendiente de {p.numero}: {detalle}.'
        hacer = lambda: op.registrar_entrega(p, {}, usuario)
    elif accion == 'registrar_pago':
        falta = max(p.a_pesos(p.total) - op.pagado(p), 0)
        monto = args.get('monto') or falta
        plan = (f'Registrar {"el cobro" if venta else "el pago"} de {_clp(monto)} de {p.numero} '
                f'({p.contacto.razon_social}) por {args.get("medio") or "transferencia"}; quedarían {_clp(max(falta - int(monto), 0))} pendientes.')
        hacer = lambda: op.registrar_pago(p, monto, usuario, medio=args.get('medio') or 'transferencia')
    elif accion == 'facturar':
        if not venta:
            return {'error': 'Las facturas de compra las emite el proveedor: regístrela con registrar_factura_proveedor.'}
        if p.estado != Pedido.CONFIRMADO:
            emision.emitir(p)  # explica que primero hay que confirmarla
        montos = emision.opciones(p)
        que = args.get('que')
        if que not in ('vendido', 'entregado'):
            if montos['vendido'] <= 0:
                emision.emitir(p)  # ya facturada completa
            if 0 < montos['entregado'] != montos['vendido']:
                # Se entregó una parte: facturar lo vendido o lo entregado lo decide la persona.
                return {'requiere_eleccion': True, 'opciones': [
                            {'texto': f'Facturar lo vendido ({_clp(montos["vendido"])})', 'respuesta': f'Factura lo vendido de {p.numero}'},
                            {'texto': f'Facturar lo entregado ({_clp(montos["entregado"])})', 'respuesta': f'Factura lo entregado de {p.numero}'}],
                        'pregunta': (f'De {p.numero} quedan {_clp(montos["vendido"])} vendidos por facturar y se ha entregado '
                                     f'{_clp(montos["entregado"])}. ¿Qué factura?'),
                        'instruccion': 'Pregúntale cuál quiere (los botones ya se ven). Cuando elija, vuelve a llamar con que=vendido o que=entregado.'}
            que = 'vendido'
        monto = montos[que]
        if monto <= 0:
            emision.emitir(p, que=que)  # explica por qué no hay qué facturar
        sin_entregar = que == 'vendido' and montos['entregado'] == 0 and facturacion.entregado_clp(p) == 0
        plan = (f'Emitir la factura electrónica de {p.numero} a {p.contacto.razon_social} por lo {que}: {_clp(monto)} neto + IVA = '
                f'{_clp(round(monto * 1.19))}.' + (' Todavía no se entrega nada de esta orden.' if sin_entregar else ''))
        if not args.get('confirmado'):
            return {'requiere_confirmacion': True, 'se_hara': plan,
                    'instruccion': 'Muéstrale esto al usuario y pregúntale si confirma. Solo si dice que sí, vuelve a llamar con confirmado=true.'}
        return _emitida(emision.emitir(p, usuario=usuario, que=que), p)
    elif accion == 'enviar_correo':
        if not p.contacto.email:
            return {'error': f'{p.contacto.razon_social} no tiene correo en su ficha: agréguelo primero.'}
        plan = f'Enviar {p.numero} en PDF a {p.contacto.razon_social} ({p.contacto.email}).'

        def hacer():
            from . import correo
            correo.enviar(p, p.contacto.email, responder_a=usuario.email if usuario else None)
            op.marcar_enviado(p)
    else:
        return {'error': 'Acción no válida.'}
    if not args.get('confirmado'):
        return {'requiere_confirmacion': True, 'se_hara': plan,
                'instruccion': 'Muéstrale esto al usuario y pregúntale si confirma. Solo si dice que sí, vuelve a llamar con confirmado=true.'}
    hacer()
    p.refresh_from_db()
    return {'hecho': plan, 'etapa': facturacion.etapa(p, **{k: facturacion.estado(p, cfg)[k] for k in ('entrega', 'factura')}),
            'enlace': f'/app/{"ventas" if venta else "compras"}/ordenes/{p.id}'}

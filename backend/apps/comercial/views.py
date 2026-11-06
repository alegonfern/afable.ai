"""Compras y Ventas: `/api/v1/workspaces/<slug>/comercial/...`. Ver es de cualquier miembro;
crear, confirmar, entregar y vincular es de editor para arriba (como Finanzas)."""

from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.finanzas.models import Contacto, Contraparte, DocumentoTributario
from apps.workspaces.permissions import IsEditor, IsMember

from . import cambio, correo, emision, facturacion, operaciones as op, pdf, planillas, reportes
from .models import (CERO, COMPRA, MONEDAS, NIVELES_INVENTARIO, VENTA, Bodega, ConfiguracionComercial,
                     Entrega, MovimientoStock, PagoPedido, Pedido, PrecioContacto, Producto, stock)

MAX_LISTA = 300


class _Base(APIView):
    def get_permissions(self):
        if self.request.method in ('GET', 'HEAD', 'OPTIONS'):
            return [IsAuthenticated(), IsMember()]
        return [IsAuthenticated(), IsEditor()]

    def handle_exception(self, exc):
        if isinstance(exc, op.ErrorComercial):
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return super().handle_exception(exc)


def _error(mensaje, codigo=status.HTTP_400_BAD_REQUEST):
    return Response({'detail': mensaje}, status=codigo)


def _num(d):
    """Decimal → texto sin ceros de más ("12.5", "3"), que el frontend muestra con coma."""
    if d is None:
        return None
    return format(Decimal(d).normalize(), 'f')


# ── Configuración ─────────────────────────────────────────────────────────────

def _config(cfg):
    return {
        'nivel_inventario': cfg.nivel_inventario, 'niveles': [{'valor': v, 'nombre': n} for v, n in NIVELES_INVENTARIO],
        'facturar_ventas': cfg.facturar_ventas, 'facturar_compras': cfg.facturar_compras,
        'validez_cotizacion_dias': cfg.validez_cotizacion_dias, 'tolerancia_pct': _num(cfg.tolerancia_pct),
        'dias_sin_respuesta': cfg.dias_sin_respuesta, 'condiciones_venta': cfg.condiciones_venta,
        'emision_disponible': emision.disponible(cfg.organization),
        'emisor': cfg.emisor, 'emisor_faltan': cfg.emisor_faltan,
        'monedas': [{'valor': v, 'nombre': n} for v, n in MONEDAS],
    }


class ConfiguracionView(_Base):
    def get(self, request, slug):
        return Response(_config(ConfiguracionComercial.de(request.empresa)))

    def put(self, request, slug):
        cfg = ConfiguracionComercial.de(request.empresa)
        d = request.data
        if 'nivel_inventario' in d:
            if d['nivel_inventario'] not in dict(NIVELES_INVENTARIO):
                return _error('Nivel de inventario no válido.')
            cfg.nivel_inventario = d['nivel_inventario']
            if cfg.con_inventario:
                Bodega.principal_de(request.empresa)
        for campo in ('facturar_ventas', 'facturar_compras'):
            if campo in d:
                if d[campo] not in dict(ConfiguracionComercial.POLITICAS):
                    return _error('Política no válida.')
                setattr(cfg, campo, d[campo])
        for campo, maximo in (('validez_cotizacion_dias', 365), ('dias_sin_respuesta', 90)):
            if campo in d:
                n = int(op.decimal(d[campo], 'Los días', 1))
                if n > maximo:
                    return _error(f'Los días no pueden pasar de {maximo}.')
                setattr(cfg, campo, n)
        if 'tolerancia_pct' in d:
            t = op.decimal(d['tolerancia_pct'], 'La tolerancia', 0)
            if t > 50:
                return _error('La tolerancia no puede pasar de 50%.')
            cfg.tolerancia_pct = t
        if 'condiciones_venta' in d:
            cfg.condiciones_venta = str(d['condiciones_venta'] or '')[:5000]
        if isinstance(d.get('emisor'), dict):
            e = d['emisor']
            if 'rut' in e:
                rut = _normalizar_rut(e['rut'])
                if e['rut'] and not rut_valido(rut):
                    return _error('Ese RUT no es válido: revise el dígito verificador.')
                request.empresa.rut = rut
                request.empresa.save(update_fields=['rut'])
            for campo, largo in (('razon_social', 255), ('giro', 255), ('direccion', 255), ('comuna', 80), ('ciudad', 80)):
                if campo in e:
                    setattr(cfg, f'emisor_{campo}', str(e[campo] or '').strip()[:largo])
        cfg.save()
        return Response(_config(cfg))


# ── Contactos (la ficha única) ────────────────────────────────────────────────

CAMPOS_CONTACTO = ['rut', 'razon_social', 'giro', 'direccion', 'comuna', 'ciudad', 'email', 'telefono',
                   'persona_contacto', 'notas']


def _contacto(c, stats=None):
    datos = {k: getattr(c, k) for k in CAMPOS_CONTACTO}
    datos.update({'id': c.id, 'es_cliente': c.es_cliente, 'es_proveedor': c.es_proveedor, 'activo': c.activo})
    if stats is not None:
        datos.update(stats)
    return datos


def rut_valido(rut):
    """El dígito verificador del RUT chileno (módulo 11)."""
    cuerpo, _, dv = str(rut or '').partition('-')
    if not cuerpo.isdigit() or len(dv) != 1:
        return False
    suma, factor = 0, 2
    for d in reversed(cuerpo):
        suma += int(d) * factor
        factor = 2 if factor == 7 else factor + 1
    resto = 11 - suma % 11
    return dv.upper() == {11: '0', 10: 'K'}.get(resto, str(resto))


def _normalizar_rut(rut):
    limpio = ''.join(ch for ch in str(rut or '').upper() if ch.isdigit() or ch == 'K')
    if len(limpio) < 2:
        return ''
    return f'{limpio[:-1]}-{limpio[-1]}'


class ContactosView(_Base):
    def get(self, request, slug):
        qs = Contacto.objects.filter(organization=request.empresa)
        archivados = request.query_params.get('archivados')
        if archivados == 'solo':
            qs = qs.filter(activo=False)
        elif archivados != 'todos':
            qs = qs.filter(activo=True)
        rol = request.query_params.get('rol')
        if rol == 'cliente':
            qs = qs.filter(es_cliente=True)
        elif rol == 'proveedor':
            qs = qs.filter(es_proveedor=True)
        q = (request.query_params.get('q') or '').strip()
        if q:
            qs = qs.filter(Q(razon_social__icontains=q) | Q(rut__icontains=q))
        contactos = list(qs[:MAX_LISTA])
        libros = {'cliente': ['ventas'], 'proveedor': ['compras', 'honorarios']}.get(rol, ['ventas', 'compras', 'honorarios'])
        stats = {}
        for d in DocumentoTributario.objects.filter(organization=request.empresa, libro__in=libros,
                                                    contraparte__contacto__in=contactos).only(
                'contraparte__contacto_id', 'monto_total', 'tipo_documento', 'pagado', 'contraparte'):
            s = stats.setdefault(d.contraparte.contacto_id, {'documentos': 0, 'total': 0, 'pendiente': 0})
            s['documentos'] += 1
            s['total'] += d.signo * d.monto_total
            if not d.pagado:
                s['pendiente'] += d.signo * d.monto_total
        vacio = {'documentos': 0, 'total': 0, 'pendiente': 0}
        return Response([_contacto(c, stats.get(c.id, vacio)) for c in contactos])

    def post(self, request, slug):
        d = request.data
        nombre = str(d.get('razon_social') or '').strip()[:255]
        if not nombre:
            return _error('Falta el nombre o razón social.')
        rut = _normalizar_rut(d.get('rut'))
        if rut and Contacto.objects.filter(organization=request.empresa, rut=rut).exists():
            return _error('Ya existe un contacto con ese RUT.')
        c = Contacto(organization=request.empresa, rut=rut, razon_social=nombre)
        _aplicar_contacto(c, d)
        c.save()
        return Response(_contacto(c), status=status.HTTP_201_CREATED)


def _aplicar_contacto(c, d):
    for campo in CAMPOS_CONTACTO:
        if campo in d and campo not in ('rut', 'razon_social'):
            setattr(c, campo, str(d[campo] or '')[:Contacto._meta.get_field(campo).max_length or 5000])
    if d.get('razon_social'):
        c.razon_social = str(d['razon_social']).strip()[:255]
    for campo in ('es_cliente', 'es_proveedor', 'activo'):
        if campo in d:
            setattr(c, campo, bool(d[campo]))


class ContactoView(_Base):
    def _obj(self, request, pk):
        return Contacto.objects.filter(organization=request.empresa, pk=pk).first()

    def get(self, request, slug, pk):
        c = self._obj(request, pk)
        if not c:
            return _error('No existe.', status.HTTP_404_NOT_FOUND)
        roles = []
        for r in c.roles.select_related('categoria'):
            docs = DocumentoTributario.objects.filter(contraparte=r)
            roles.append({'id': r.id, 'libro': r.libro, 'plazo_dias': r.plazo_dias, 'plazo_por_defecto': r.plazo,
                          'regla_activa': r.regla_activa, 'categoria': r.categoria_id,
                          'categoria_nombre': r.categoria.nombre if r.categoria else None,
                          'documentos': docs.count(),
                          'pendiente': sum(x.signo * x.monto_total for x in docs.filter(pagado=False))})
        pedidos = [{'id': p.id, 'numero': p.numero, 'tipo': p.tipo, 'fecha': p.fecha.isoformat(),
                    'etapa': facturacion.etapa(p), 'total': _num(p.total), 'moneda': p.moneda}
                   for p in c.pedidos.order_by('-fecha')[:20]]
        return Response({**_contacto(c), 'roles': roles, 'pedidos': pedidos})

    def patch(self, request, slug, pk):
        c = self._obj(request, pk)
        if not c:
            return _error('No existe.', status.HTTP_404_NOT_FOUND)
        if 'rut' in request.data:
            rut = _normalizar_rut(request.data['rut'])
            if rut != c.rut:
                if c.roles.exists():
                    return _error('El RUT viene del SII y ya tiene documentos: no se puede cambiar.')
                if rut and Contacto.objects.filter(organization=request.empresa, rut=rut).exclude(pk=c.pk).exists():
                    return _error('Ya existe un contacto con ese RUT.')
                c.rut = rut
        _aplicar_contacto(c, request.data)
        c.save()
        return Response(_contacto(c))


# ── Productos y bodegas ───────────────────────────────────────────────────────

def _producto(p, existencias=None):
    datos = {
        'id': p.id, 'codigo': p.codigo, 'nombre': p.nombre, 'descripcion': p.descripcion, 'tipo': p.tipo,
        'unidad': p.unidad, 'precio_venta': _num(p.precio_venta), 'costo': _num(p.costo), 'exento': p.exento,
        'se_vende': p.se_vende, 'se_compra': p.se_compra, 'stock_minimo': _num(p.stock_minimo),
        'cantidad_reorden': _num(p.cantidad_reorden), 'stock_maximo': _num(p.stock_maximo),
        'familia': p.familia, 'codigo_barras': p.codigo_barras, 'ubicacion': p.ubicacion,
        'categoria_venta': p.categoria_venta_id, 'categoria_compra': p.categoria_compra_id, 'activo': p.activo,
    }
    if existencias is not None:
        por_bodega = {b: c for (pid, b), c in existencias.items() if pid == p.id}
        datos['stock'] = _num(sum(por_bodega.values(), CERO))
        datos['stock_por_bodega'] = {str(b): _num(c) for b, c in por_bodega.items()}
    return datos


def _aplicar_producto(p, d, org):
    from apps.finanzas.models import Categoria
    if 'nombre' in d:
        p.nombre = str(d['nombre'] or '').strip()[:200]
    if not p.nombre:
        raise op.ErrorComercial('Falta el nombre del producto.')
    if 'codigo' in d:
        codigo = str(d['codigo'] or '').strip()[:40]
        if codigo and Producto.objects.filter(organization=org, codigo=codigo).exclude(pk=p.pk).exists():
            raise op.ErrorComercial('Ya existe un producto con ese código.')
        p.codigo = codigo
    if 'tipo' in d:
        if d['tipo'] not in dict(Producto.TIPOS):
            raise op.ErrorComercial('Tipo de producto no válido.')
        p.tipo = d['tipo']
    for campo, largo in (('descripcion', 5000), ('unidad', 20), ('familia', 80), ('codigo_barras', 40),
                         ('ubicacion', 40)):
        if campo in d:
            setattr(p, campo, str(d[campo] or '')[:largo])
    for campo, nombre in (('precio_venta', 'El precio'), ('costo', 'El costo'), ('stock_minimo', 'El stock mínimo'),
                         ('cantidad_reorden', 'La cantidad para reponer'), ('stock_maximo', 'El stock máximo')):
        if campo in d and d[campo] not in (None, ''):
            setattr(p, campo, op.decimal(d[campo], nombre, 0))
    for campo in ('exento', 'se_vende', 'se_compra', 'activo'):
        if campo in d:
            setattr(p, campo, bool(d[campo]))
    for campo in ('categoria_venta', 'categoria_compra'):
        if campo in d:
            cid = d[campo]
            cat = Categoria.objects.filter(organization=org, pk=cid).first() if cid else None
            if cid and cat is None:
                raise op.ErrorComercial('La categoría no existe.')
            setattr(p, campo, cat)


class ProductosView(_Base):
    def get(self, request, slug):
        qs = Producto.objects.filter(organization=request.empresa)
        if request.query_params.get('activos') == '1':
            qs = qs.filter(activo=True)
        uso = request.query_params.get('uso')
        if uso == VENTA:
            qs = qs.filter(se_vende=True)
        elif uso == COMPRA:
            qs = qs.filter(se_compra=True)
        q = (request.query_params.get('q') or '').strip()
        if q:
            qs = qs.filter(Q(nombre__icontains=q) | Q(codigo__icontains=q))
        existencias = stock(request.empresa)
        return Response([_producto(p, existencias) for p in qs[:MAX_LISTA]])

    def post(self, request, slug):
        p = Producto(organization=request.empresa)
        _aplicar_producto(p, request.data, request.empresa)
        p.save()
        return Response(_producto(p, {}), status=status.HTTP_201_CREATED)


class ProductoView(_Base):
    def patch(self, request, slug, pk):
        p = Producto.objects.filter(organization=request.empresa, pk=pk).first()
        if not p:
            return _error('No existe.', status.HTTP_404_NOT_FOUND)
        _aplicar_producto(p, request.data, request.empresa)
        p.save()
        return Response(_producto(p, stock(request.empresa, producto=p)))


def _bodega(b):
    return {'id': b.id, 'nombre': b.nombre, 'codigo': b.codigo, 'direccion': b.direccion,
            'principal': b.principal, 'activa': b.activa}


class BodegasView(_Base):
    def get(self, request, slug):
        if ConfiguracionComercial.de(request.empresa).con_inventario:
            Bodega.principal_de(request.empresa)
        return Response([_bodega(b) for b in Bodega.objects.filter(organization=request.empresa)])

    def post(self, request, slug):
        nombre = str(request.data.get('nombre') or '').strip()[:80]
        if not nombre:
            return _error('Falta el nombre de la bodega.')
        principal_existe = Bodega.objects.filter(organization=request.empresa, principal=True).exists()
        b = Bodega.objects.create(organization=request.empresa, nombre=nombre,
                                  codigo=str(request.data.get('codigo') or '')[:10],
                                  direccion=str(request.data.get('direccion') or '')[:255],
                                  principal=not principal_existe)
        return Response(_bodega(b), status=status.HTTP_201_CREATED)


class BodegaView(_Base):
    def patch(self, request, slug, pk):
        b = Bodega.objects.filter(organization=request.empresa, pk=pk).first()
        if not b:
            return _error('No existe.', status.HTTP_404_NOT_FOUND)
        d = request.data
        for campo, largo in (('nombre', 80), ('codigo', 10), ('direccion', 255)):
            if campo in d:
                setattr(b, campo, str(d[campo] or '')[:largo])
        if 'activa' in d:
            if not d['activa'] and b.principal:
                return _error('La bodega principal no se puede desactivar: marque otra como principal primero.')
            b.activa = bool(d['activa'])
        if d.get('principal'):
            Bodega.objects.filter(organization=request.empresa, principal=True).exclude(pk=b.pk).update(principal=False)
            b.principal, b.activa = True, True
        b.save()
        return Response(_bodega(b))


# ── Stock ─────────────────────────────────────────────────────────────────────

class StockView(_Base):
    def get(self, request, slug):
        org = request.empresa
        existencias = stock(org)
        productos = []
        valor_total = 0
        for p in Producto.objects.filter(organization=org, tipo=Producto.ALMACENABLE):
            datos = _producto(p, existencias)
            costo = op.costo_promedio(org, p)
            valor = int(round(max(Decimal(datos['stock']), CERO) * costo))
            datos.update({'costo_promedio': _num(costo), 'valor': valor})
            valor_total += valor
            productos.append(datos)
        return Response({
            'bodegas': [_bodega(b) for b in Bodega.objects.filter(organization=org)],
            'productos': productos, 'valor_total': valor_total,
        })


class ReponerView(_Base):
    """Arma ahora las solicitudes de compra para lo que está bajo el mínimo."""

    def post(self, request, slug):
        creadas, sin_proveedor = op.reponer_stock(request.empresa, request.user)
        return Response({
            'solicitudes': [{'id': x.id, 'numero': x.numero, 'proveedor': x.contacto.razon_social} for x in creadas],
            'sin_proveedor': [x.nombre for x in sin_proveedor],
        })


# ── Precios por cliente y por proveedor ───────────────────────────────────────

def _precio(x):
    return {'id': x.id, 'producto': x.producto_id, 'contacto': x.contacto_id, 'contacto_nombre': x.contacto.razon_social,
            'tipo': x.tipo, 'precio': _num(x.precio), 'codigo_contacto': x.codigo_contacto, 'preferido': x.preferido}


class PreciosView(_Base):
    def get(self, request, slug):
        qs = PrecioContacto.objects.filter(organization=request.empresa).select_related('contacto')
        for campo in ('producto', 'contacto', 'tipo'):
            if request.query_params.get(campo):
                qs = qs.filter(**{campo: request.query_params[campo]})
        return Response([_precio(x) for x in qs])

    def post(self, request, slug):
        d = request.data
        org = request.empresa
        producto = Producto.objects.filter(organization=org, pk=d.get('producto')).first()
        contacto = Contacto.objects.filter(organization=org, pk=d.get('contacto')).first()
        if not producto or not contacto:
            return _error('Elija el producto y el contacto.')
        if d.get('tipo') not in (VENTA, COMPRA):
            return _error('Indique si es precio de venta o de compra.')
        precio = op.decimal(d.get('precio'), 'El precio', 0)
        x, _ = PrecioContacto.objects.update_or_create(
            organization=org, producto=producto, contacto=contacto, tipo=d['tipo'],
            defaults={'precio': precio, 'codigo_contacto': str(d.get('codigo_contacto') or '')[:40],
                      'preferido': bool(d.get('preferido'))})
        if x.preferido:
            PrecioContacto.objects.filter(producto=producto, tipo=x.tipo).exclude(pk=x.pk).update(preferido=False)
        marca = 'es_cliente' if x.tipo == VENTA else 'es_proveedor'
        if not getattr(contacto, marca):
            setattr(contacto, marca, True)
            contacto.save(update_fields=[marca])
        return Response(_precio(x), status=status.HTTP_201_CREATED)


class PrecioView(_Base):
    def delete(self, request, slug, pk):
        PrecioContacto.objects.filter(organization=request.empresa, pk=pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AjusteView(_Base):
    def post(self, request, slug):
        p = Producto.objects.filter(organization=request.empresa, pk=request.data.get('producto')).first()
        if not p:
            return _error('El producto no existe.')
        m = op.ajustar_stock(request.empresa, p, request.data.get('cantidad'), request.data.get('bodega'),
                             request.user, request.data.get('motivo'))
        return Response({'ajustado': m is not None, 'producto': _producto(p, stock(request.empresa, producto=p))})


class TraspasoView(_Base):
    def post(self, request, slug):
        p = Producto.objects.filter(organization=request.empresa, pk=request.data.get('producto')).first()
        if not p:
            return _error('El producto no existe.')
        op.traspasar(request.empresa, p, request.data.get('origen'), request.data.get('destino'),
                     request.data.get('cantidad'), request.user)
        return Response({'producto': _producto(p, stock(request.empresa, producto=p))})


class MovimientosView(_Base):
    def get(self, request, slug):
        qs = MovimientoStock.objects.filter(organization=request.empresa).select_related('producto', 'bodega')
        if request.query_params.get('producto'):
            qs = qs.filter(producto_id=request.query_params['producto'])
        return Response([{
            'id': m.id, 'fecha': m.fecha.isoformat(), 'producto': m.producto.nombre, 'producto_id': m.producto_id,
            'bodega': m.bodega.nombre, 'cantidad': _num(m.cantidad), 'tipo': m.get_tipo_display(),
            'referencia': m.referencia, 'costo_unitario': _num(m.costo_unitario),
        } for m in qs[:MAX_LISTA]])


# ── Pedidos ───────────────────────────────────────────────────────────────────

def _linea(l):
    return {
        'id': l.id, 'producto': l.producto_id, 'producto_nombre': l.producto.nombre if l.producto_id else None,
        'lleva_stock': bool(l.producto_id and l.producto.lleva_stock),
        'descripcion': l.descripcion, 'cantidad': _num(l.cantidad), 'unidad': l.unidad,
        'precio_unitario': _num(l.precio_unitario), 'descuento_pct': _num(l.descuento_pct), 'exento': l.exento,
        'subtotal': _num(l.subtotal), 'cantidad_entregada': _num(l.cantidad_entregada),
        'pendiente': _num(l.pendiente_entrega),
    }


def _pedido(p, cfg, detalle=False):
    e = facturacion.estado(p, cfg)
    datos = {
        'id': p.id, 'tipo': p.tipo, 'numero': p.numero, 'estado': p.estado, 'etapa': e['etapa'],
        'contacto': p.contacto_id, 'contacto_nombre': p.contacto.razon_social, 'contacto_rut': p.contacto.rut,
        'fecha': p.fecha.isoformat(), 'fecha_compromiso': p.fecha_compromiso.isoformat() if p.fecha_compromiso else None,
        'valida_hasta': p.valida_hasta.isoformat() if p.valida_hasta else None,
        'moneda': p.moneda, 'tipo_cambio': _num(p.tipo_cambio),
        'neto': _num(p.neto), 'exento': _num(p.exento), 'iva': _num(p.iva), 'total': _num(p.total),
        'total_clp': p.a_pesos(p.total), **{k: e[k] for k in ('entrega', 'factura', 'entregado_pct', 'entregado_clp',
                                                              'facturado_clp', 'base_clp', 'por_facturar_clp', 'diferencias')},
        'pagado_clp': op.pagado(p), 'por_pagar_clp': max(p.a_pesos(p.total) - op.pagado(p), 0) if p.es_orden else 0,
        'origen': p.origen,
    }
    if detalle:
        datos.update({
            'proyecto': p.proyecto_id, 'bodega': p.bodega_id, 'plazo_dias': p.plazo_dias,
            'referencia': p.referencia, 'notas': p.notas, 'condiciones': p.condiciones,
            'contacto_email': p.contacto.email,
            'lineas': [_linea(l) for l in p.lineas.select_related('producto')],
            'entregas': [_entrega(x, guias=_emite_guias(p.organization))
                         for x in p.entregas.prefetch_related('lineas__linea').select_related('bodega')],
            'facturas': [{'documento': v.documento_id, 'folio': v.documento.folio,
                          'tipo_documento': v.documento.tipo_documento, 'fecha': v.documento.fecha.isoformat(),
                          'monto': v.monto, 'total_documento': facturacion.base_documento(v.documento),
                          'origen': v.origen, 'emitida': v.documento.emitido_en_afable}
                         for v in p.facturas.select_related('documento')],
            'pagos': [{'id': x.id, 'fecha': x.fecha.isoformat(), 'monto': x.monto, 'medio': x.medio,
                       'medio_nombre': x.get_medio_display(), 'referencia': x.referencia, 'notas': x.notas}
                      for x in p.pagos.all()],
            'editable': op.editable(p), 'emision_disponible': emision.disponible(p.organization),
            # Lo que se puede facturar de cada forma, para el menú "Emitir factura".
            'facturable': emision.opciones(p) if p.tipo == VENTA and p.estado == Pedido.CONFIRMADO else None,
            'con_inventario': cfg.con_inventario,
        })
    return datos


def _entrega(x, guias=False):
    """`guias`: la empresa emite guías de despacho electrónicas con el facturador nativo (apps/dte)."""
    guia = None
    if x.folio_guia:
        from apps.dte.comercial import guia_de
        guia = guia_de(x)
    return {
        'id': x.id, 'numero': x.numero, 'fecha': x.fecha.isoformat(), 'estado': x.estado, 'tipo': x.tipo,
        'bodega': x.bodega.nombre if x.bodega_id else None, 'folio_guia': x.folio_guia, 'notas': x.notas,
        'pedido': x.pedido_id, 'pedido_numero': x.pedido.numero, 'contacto_nombre': x.pedido.contacto.razon_social,
        'lineas': [{'descripcion': le.linea.descripcion, 'cantidad': _num(le.cantidad), 'unidad': le.linea.unidad}
                   for le in x.lineas.all()],
        # La guía electrónica: si se puede emitir ahora y, si ya se emitió, su documento (para el PDF).
        'guia_disponible': bool(guias and x.pedido.tipo == VENTA and x.estado == Entrega.HECHA and not x.folio_guia),
        'guia_documento': guia.id if guia else None,
    }


# Los filtros de las listas, con los nombres de las secciones del menú.
FILTROS = {
    'cotizaciones': Q(estado__in=[Pedido.BORRADOR, Pedido.ENVIADO]),
    'ordenes': Q(estado=Pedido.CONFIRMADO),
    'canceladas': Q(estado=Pedido.CANCELADO),
}


class PedidosView(_Base):
    def get(self, request, slug):
        tipo = request.query_params.get('tipo')
        if tipo not in (VENTA, COMPRA):
            return _error('Indique el tipo: venta o compra.')
        qs = (Pedido.objects.filter(organization=request.empresa, tipo=tipo)
              .select_related('contacto').prefetch_related('lineas'))
        filtro = FILTROS.get(request.query_params.get('vista'))
        if filtro is not None:
            qs = qs.filter(filtro)
        if request.query_params.get('contacto'):
            qs = qs.filter(contacto_id=request.query_params['contacto'])
        q = (request.query_params.get('q') or '').strip()
        if q:
            qs = qs.filter(Q(numero__icontains=q) | Q(contacto__razon_social__icontains=q) | Q(referencia__icontains=q))
        for param, campo in (('desde', 'fecha__gte'), ('hasta', 'fecha__lte')):
            if request.query_params.get(param):
                try:
                    qs = qs.filter(**{campo: date.fromisoformat(request.query_params[param])})
                except ValueError:
                    return _error('Fecha no válida.')
        cfg = ConfiguracionComercial.de(request.empresa)
        filas = [_pedido(p, cfg) for p in qs[:MAX_LISTA]]
        etapa = request.query_params.get('etapa')
        if etapa:
            filas = [f for f in filas if f['etapa'] == etapa]
        return Response(filas)

    @transaction.atomic
    def post(self, request, slug):
        tipo = request.data.get('tipo')
        contacto = Contacto.objects.filter(organization=request.empresa, pk=request.data.get('contacto')).first()
        if contacto is None:
            return _error('Elija un cliente.' if tipo == VENTA else 'Elija un proveedor.')
        datos = {k: v for k, v in request.data.items() if k not in ('tipo', 'contacto', 'lineas')}
        p = op.crear_pedido(request.empresa, tipo, contacto, request.user, **datos)
        if request.data.get('lineas'):
            op.guardar_lineas(p, request.data['lineas'])
        return Response(_pedido(p, ConfiguracionComercial.de(request.empresa), detalle=True), status=status.HTTP_201_CREATED)


class PedidoView(_Base):
    def _obj(self, request, pk):
        return Pedido.objects.filter(organization=request.empresa, pk=pk).select_related('contacto').first()

    def get(self, request, slug, pk):
        p = self._obj(request, pk)
        if not p:
            return _error('No existe.', status.HTTP_404_NOT_FOUND)
        return Response(_pedido(p, ConfiguracionComercial.de(request.empresa), detalle=True))

    @transaction.atomic
    def patch(self, request, slug, pk):
        p = self._obj(request, pk)
        if not p:
            return _error('No existe.', status.HTTP_404_NOT_FOUND)
        d = request.data
        # De una orden confirmada solo se cambia lo que no altera montos ni cantidades.
        libres = {'fecha_compromiso', 'referencia', 'notas', 'proyecto', 'bodega'}
        if not op.editable(p) and set(d) - libres - {'lineas'}:
            return _error('La orden ya está confirmada: vuélvala a borrador para cambiar eso.')
        moneda_antes = p.moneda
        op.aplicar_datos(p, d)
        p.save()
        if 'lineas' in d:
            op.guardar_lineas(p, d['lineas'])
        elif p.moneda != moneda_antes:
            p.recalcular()
        return Response(_pedido(p, ConfiguracionComercial.de(request.empresa), detalle=True))

    def delete(self, request, slug, pk):
        p = self._obj(request, pk)
        if not p:
            return _error('No existe.', status.HTTP_404_NOT_FOUND)
        if p.estado != Pedido.BORRADOR:
            return _error('Solo se borra una cotización en borrador. Lo demás se cancela.')
        p.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AccionView(_Base):
    ACCIONES = {'enviar': op.marcar_enviado, 'confirmar': op.confirmar, 'cancelar': op.cancelar,
                'borrador': op.volver_a_borrador}

    @transaction.atomic
    def post(self, request, slug, pk):
        p = Pedido.objects.filter(organization=request.empresa, pk=pk).select_related('contacto').first()
        if not p:
            return _error('No existe.', status.HTTP_404_NOT_FOUND)
        accion = request.data.get('accion')
        if accion == 'duplicar':
            copia = op.duplicar(p, request.user)
            return Response(_pedido(copia, ConfiguracionComercial.de(request.empresa), detalle=True),
                            status=status.HTTP_201_CREATED)
        if accion == 'emitir':
            emision.emitir(p, usuario=request.user, que=request.data.get('que'))
        elif accion in self.ACCIONES:
            self.ACCIONES[accion](p)
        else:
            return _error('Acción no válida.')
        return Response(_pedido(p, ConfiguracionComercial.de(request.empresa), detalle=True))


class EntregasView(_Base):
    def get(self, request, slug):
        qs = Entrega.objects.filter(organization=request.empresa).select_related(
            'pedido__contacto', 'bodega').prefetch_related('lineas__linea')
        tipo = request.query_params.get('tipo')
        if tipo in (VENTA, COMPRA):
            qs = qs.filter(pedido__tipo=tipo)
        guias = _emite_guias(request.empresa)
        return Response([_entrega(x, guias=guias) for x in qs[:MAX_LISTA]])


def _emite_guias(org):
    from apps.dte.comercial import guia_disponible
    return guia_disponible(org)


class GuiaView(_Base):
    """Emite la guía de despacho electrónica (52) de una entrega con el facturador nativo.
    Transporte opcional: {patente, rut_transportista, direccion_destino, comuna_destino}."""

    def post(self, request, slug, pk, entrega):
        from apps.dte.comercial import emitir_guia
        x = Entrega.objects.filter(organization=request.empresa, pedido_id=pk, pk=entrega).select_related('pedido').first()
        if not x:
            return _error('No existe.', status.HTTP_404_NOT_FOUND)
        transporte = {k: str(request.data.get(k) or '').strip() for k in
                      ('patente', 'rut_transportista', 'direccion_destino', 'comuna_destino', 'ciudad_destino')}
        with transaction.atomic():
            emitir_guia(x, request.user, transporte)
        p = Pedido.objects.get(pk=pk)
        return Response(_pedido(p, ConfiguracionComercial.de(request.empresa), detalle=True))


class EntregarView(_Base):
    def post(self, request, slug, pk):
        p = Pedido.objects.filter(organization=request.empresa, pk=pk).first()
        if not p:
            return _error('No existe.', status.HTTP_404_NOT_FOUND)
        d = request.data
        op.registrar_entrega(p, d.get('cantidades') or {}, request.user, fecha=d.get('fecha'),
                             bodega=d.get('bodega'), folio_guia=d.get('folio_guia', ''), notas=d.get('notas', ''))
        p.refresh_from_db()
        return Response(_pedido(p, ConfiguracionComercial.de(request.empresa), detalle=True))


class DevolverView(_Base):
    def post(self, request, slug, pk):
        p = Pedido.objects.filter(organization=request.empresa, pk=pk).first()
        if not p:
            return _error('No existe.', status.HTTP_404_NOT_FOUND)
        d = request.data
        op.registrar_devolucion(p, d.get('cantidades') or {}, request.user, fecha=d.get('fecha'),
                                bodega=d.get('bodega'), notas=d.get('notas', ''))
        p.refresh_from_db()
        return Response(_pedido(p, ConfiguracionComercial.de(request.empresa), detalle=True))


class PagosView(_Base):
    def post(self, request, slug, pk):
        p = Pedido.objects.filter(organization=request.empresa, pk=pk).select_related('contacto').first()
        if not p:
            return _error('No existe.', status.HTTP_404_NOT_FOUND)
        d = request.data
        op.registrar_pago(p, d.get('monto'), request.user, fecha=d.get('fecha'),
                          medio=d.get('medio') or PagoPedido.TRANSFERENCIA, referencia=d.get('referencia', ''),
                          notas=d.get('notas', ''))
        return Response(_pedido(p, ConfiguracionComercial.de(request.empresa), detalle=True))


class PagoView(_Base):
    def delete(self, request, slug, pk, pago):
        x = PagoPedido.objects.filter(pedido__organization=request.empresa, pedido_id=pk, pk=pago).first()
        if not x:
            return _error('No existe.', status.HTTP_404_NOT_FOUND)
        op.borrar_pago(x)
        p = Pedido.objects.get(pk=pk)
        return Response(_pedido(p, ConfiguracionComercial.de(request.empresa), detalle=True))


class AnularEntregaView(_Base):
    def post(self, request, slug, pk):
        x = Entrega.objects.filter(organization=request.empresa, pk=pk).first()
        if not x:
            return _error('No existe.', status.HTTP_404_NOT_FOUND)
        op.anular_entrega(x, request.user)
        return Response(_pedido(x.pedido, ConfiguracionComercial.de(request.empresa), detalle=True))


class FacturasPedidoView(_Base):
    """Las facturas del SII que podrían ser de este pedido, y vincular o desvincular una."""

    def _obj(self, request, pk):
        return Pedido.objects.filter(organization=request.empresa, pk=pk).select_related('contacto').first()

    def get(self, request, slug, pk):
        p = self._obj(request, pk)
        if not p:
            return _error('No existe.', status.HTTP_404_NOT_FOUND)
        return Response([{
            'documento': c['documento'].id, 'folio': c['documento'].folio,
            'tipo_documento': c['documento'].tipo_documento, 'fecha': c['documento'].fecha.isoformat(),
            'total_documento': facturacion.base_documento(c['documento']), 'disponible': c['disponible'],
            'diferencia': c['diferencia'],
        } for c in facturacion.candidatos(p)])

    @transaction.atomic
    def post(self, request, slug, pk):
        p = self._obj(request, pk)
        if not p:
            return _error('No existe.', status.HTTP_404_NOT_FOUND)
        doc = DocumentoTributario.objects.filter(organization=request.empresa, pk=request.data.get('documento')).first()
        if not doc:
            return _error('La factura no existe.')
        monto = request.data.get('monto')
        facturacion.vincular(p, doc, int(op.decimal(monto, 'El monto')) if monto not in (None, '') else None, request.user)
        return Response(_pedido(p, ConfiguracionComercial.de(request.empresa), detalle=True))

    def delete(self, request, slug, pk):
        p = self._obj(request, pk)
        if not p:
            return _error('No existe.', status.HTTP_404_NOT_FOUND)
        facturacion.desvincular(p, request.query_params.get('documento'))
        return Response(_pedido(p, ConfiguracionComercial.de(request.empresa), detalle=True))


class PorFacturarView(_Base):
    def get(self, request, slug):
        tipo = request.query_params.get('tipo')
        if tipo not in (VENTA, COMPRA):
            return _error('Indique el tipo: venta o compra.')
        cfg = ConfiguracionComercial.de(request.empresa)
        return Response({
            'politica': cfg.facturar_ventas if tipo == VENTA else cfg.facturar_compras,
            'pedidos': [_pedido(p, cfg) for p, _ in facturacion.por_facturar(request.empresa, tipo)],
        })


class PdfView(_Base):
    def get(self, request, slug, pk):
        p = Pedido.objects.filter(organization=request.empresa, pk=pk).select_related('contacto', 'organization').first()
        if not p:
            return _error('No existe.', status.HTTP_404_NOT_FOUND)
        r = HttpResponse(pdf.generar(p), content_type='application/pdf')
        r['Content-Disposition'] = f'inline; filename="{p.numero}.pdf"'
        return r


class FacturaPdfView(_Base):
    """El PDF de una factura emitida desde Afable: el del facturador nativo (apps/dte/pdf.py) si la
    emitió él; si no, el del simulado (pdf_factura.py)."""

    def get(self, request, slug, pk):
        from apps.finanzas.models import DocumentoTributario
        from . import pdf_factura
        d = DocumentoTributario.objects.filter(organization=request.empresa, pk=pk, emitido_en_afable=True).first()
        if not d:
            return _error('No existe.', status.HTTP_404_NOT_FOUND)
        emitido = getattr(d, 'emitido', None)
        if emitido is not None:
            from apps.dte import pdf as pdf_dte
            contenido = pdf_dte.generar(emitido, cedible=request.query_params.get('cedible') in ('1', 'true'))
        else:
            contenido = pdf_factura.generar(d)
        r = HttpResponse(contenido, content_type='application/pdf')
        r['Content-Disposition'] = f'inline; filename="Factura-{d.folio}.pdf"'
        return r


class EnviarCorreoView(_Base):
    def post(self, request, slug, pk):
        p = Pedido.objects.filter(organization=request.empresa, pk=pk).select_related('contacto', 'organization').first()
        if not p:
            return _error('No existe.', status.HTTP_404_NOT_FOUND)
        para = str(request.data.get('para') or p.contacto.email or '').strip()
        if not para or '@' not in para:
            return _error('Falta el correo del destinatario.')
        try:
            correo.enviar(p, para, str(request.data.get('mensaje') or '').strip(), request.user.email or None)
        except Exception:
            return _error('No se pudo enviar el correo. Revise la dirección o intente más tarde.', status.HTTP_502_BAD_GATEWAY)
        op.marcar_enviado(p)
        return Response(_pedido(p, ConfiguracionComercial.de(request.empresa), detalle=True))


class ResumenView(_Base):
    """Los números del embudo para el Resumen de Ventas o de Compras."""

    def get(self, request, slug):
        tipo = request.query_params.get('tipo')
        if tipo not in (VENTA, COMPRA):
            return _error('Indique el tipo: venta o compra.')
        cfg = ConfiguracionComercial.de(request.empresa)
        abiertas = cotizado = por_entregar = 0
        por_entregar_n = 0
        for p in (Pedido.objects.filter(organization=request.empresa, tipo=tipo)
                  .exclude(estado=Pedido.CANCELADO).prefetch_related('lineas')):
            if p.estado in (Pedido.BORRADOR, Pedido.ENVIADO):
                abiertas += 1
                cotizado += p.base_clp
            elif any(l.pendiente_entrega > 0 for l in p.lineas.all()):
                por_entregar_n += 1
                por_entregar += p.a_pesos(sum((l.subtotal - l.subtotal_entregado for l in p.lineas.all()), CERO))
        filas = facturacion.por_facturar(request.empresa, tipo)
        mes = timezone.localdate().replace(day=1)
        confirmadas_mes = Pedido.objects.filter(organization=request.empresa, tipo=tipo, estado=Pedido.CONFIRMADO,
                                                confirmado_en__date__gte=mes)
        enviadas = Pedido.objects.filter(organization=request.empresa, tipo=tipo, enviado_en__isnull=False)
        ganadas = enviadas.filter(estado=Pedido.CONFIRMADO).count()
        cerradas = enviadas.filter(estado__in=[Pedido.CONFIRMADO, Pedido.CANCELADO]).count()
        return Response({
            'cotizaciones_abiertas': abiertas, 'cotizado_clp': cotizado,
            'por_entregar': por_entregar_n, 'por_entregar_clp': por_entregar,
            'por_facturar': len([1 for _, e in filas if e['por_facturar_clp'] > 0]),
            'por_facturar_clp': sum(e['por_facturar_clp'] for _, e in filas),
            'con_diferencias': len([1 for _, e in filas if e['diferencias']]),
            'confirmadas_mes': confirmadas_mes.count(),
            'confirmado_mes_clp': sum(p.base_clp for p in confirmadas_mes),
            'tasa_cierre': round(ganadas * 100 / cerradas) if cerradas else None,
        })


class TipoCambioView(_Base):
    def get(self, request, slug):
        moneda = request.query_params.get('moneda')
        try:
            fecha = date.fromisoformat(request.query_params.get('fecha') or timezone.localdate().isoformat())
        except ValueError:
            return _error('Fecha no válida.')
        v = cambio.valor(moneda, fecha)
        if v is None:
            return _error('No se pudo obtener el tipo de cambio: escríbalo a mano.', status.HTTP_404_NOT_FOUND)
        return Response({'moneda': moneda, 'fecha': fecha.isoformat(), 'valor': _num(v)})


# ── Reportes ──────────────────────────────────────────────────────────────────

def _periodo(request):
    hoy = timezone.localdate()
    try:
        desde = date.fromisoformat(request.query_params.get('desde') or hoy.replace(month=1, day=1).isoformat())
        hasta = date.fromisoformat(request.query_params.get('hasta') or hoy.isoformat())
    except ValueError:
        raise op.ErrorComercial('Fecha no válida.')
    return desde, hasta


class ReportesView(_Base):
    def get(self, request, slug):
        tipo = request.query_params.get('tipo')
        por = request.query_params.get('por') or 'producto'
        if tipo not in (VENTA, COMPRA) or por not in ('producto', 'contacto', 'mes'):
            return _error('Reporte no válido.')
        desde, hasta = _periodo(request)
        return Response({'desde': desde.isoformat(), 'hasta': hasta.isoformat(),
                         **reportes.generar(request.empresa, tipo, desde, hasta, por)})


# ── Exportar e importar ───────────────────────────────────────────────────────

def _xlsx(nombre, contenido):
    r = HttpResponse(contenido, content_type=planillas.XLSX)
    r['Content-Disposition'] = f'attachment; filename="{nombre}.xlsx"'
    return r


class ExportarView(_Base):
    def get(self, request, slug, que):
        org = request.empresa
        tipo = request.query_params.get('tipo')
        if que == 'pedidos':
            if tipo not in (VENTA, COMPRA):
                return _error('Indique el tipo: venta o compra.')
            vista = request.query_params.get('vista')
            qs = Pedido.objects.filter(organization=org, tipo=tipo).select_related('contacto').prefetch_related('lineas')
            if FILTROS.get(vista) is not None:
                qs = qs.filter(FILTROS[vista])
            cfg = ConfiguracionComercial.de(org)
            filas = []
            for x in qs[:5000]:
                d = _pedido(x, cfg)
                filas.append([x.numero, x.fecha, x.contacto.razon_social, x.contacto.rut, d['etapa'], x.moneda,
                              x.neto, x.iva, x.total, d['total_clp'], d['entregado_pct'], d['facturado_clp'],
                              d['pagado_clp']])
            cols = ['Número', 'Fecha', 'Cliente' if tipo == VENTA else 'Proveedor', 'RUT', 'Etapa', 'Moneda',
                    'Neto', 'IVA', 'Total', 'Total en pesos', 'Entregado %' if tipo == VENTA else 'Recibido %',
                    'Facturado (sin IVA)', 'Cobrado' if tipo == VENTA else 'Pagado']
            nombre = ('Ventas' if tipo == VENTA else 'Compras') + (f' - {vista}' if vista else '')
            return _xlsx(nombre, planillas.libro(nombre, cols, filas))
        if que == 'contactos':
            qs = Contacto.objects.filter(organization=org)
            if request.query_params.get('rol') == 'cliente':
                qs = qs.filter(es_cliente=True)
            elif request.query_params.get('rol') == 'proveedor':
                qs = qs.filter(es_proveedor=True)
            filas = [[x.rut, x.razon_social, x.giro, x.direccion, x.comuna, x.ciudad, x.email, x.telefono,
                      x.persona_contacto, 'Sí' if x.es_cliente else 'No', 'Sí' if x.es_proveedor else 'No',
                      'No' if x.activo else 'Sí'] for x in qs]
            return _xlsx('Contactos', planillas.libro('Contactos', planillas.COLUMNAS_CONTACTOS + ['Archivado'], filas))
        if que == 'productos':
            existencias = stock(org)
            filas = []
            for x in Producto.objects.filter(organization=org):
                cant = sum((c for (pid, _), c in existencias.items() if pid == x.id), CERO)
                filas.append([x.codigo, x.nombre, x.get_tipo_display(), x.unidad, x.precio_venta, x.costo,
                              x.stock_minimo, 'Sí' if x.exento else 'No', cant if x.lleva_stock else None])
            return _xlsx('Productos', planillas.libro('Productos', planillas.COLUMNAS_PRODUCTOS + ['Stock'], filas))
        if que == 'reporte':
            por = request.query_params.get('por') or 'producto'
            if tipo not in (VENTA, COMPRA) or por not in ('producto', 'contacto', 'mes'):
                return _error('Reporte no válido.')
            desde, hasta = _periodo(request)
            cols, filas = reportes.a_planilla(reportes.generar(org, tipo, desde, hasta, por), tipo, por)
            nombre = f'{"Ventas" if tipo == VENTA else "Compras"} por {por} {desde.isoformat()} a {hasta.isoformat()}'
            return _xlsx(nombre, planillas.libro('Reporte', cols, filas))
        return _error('No existe.', status.HTTP_404_NOT_FOUND)


class ImportarView(_Base):
    def get(self, request, slug, que):
        if que not in ('productos', 'contactos'):
            return _error('No existe.', status.HTTP_404_NOT_FOUND)
        return _xlsx(f'Plantilla {que}', planillas.plantilla(que))

    @transaction.atomic
    def post(self, request, slug, que):
        archivo = request.FILES.get('file')
        if not archivo:
            return _error('Falta el archivo.')
        if que == 'productos':
            return Response(planillas.importar_productos(request.empresa, archivo))
        if que == 'contactos':
            return Response(planillas.importar_contactos(request.empresa, archivo, _normalizar_rut))
        return _error('No existe.', status.HTTP_404_NOT_FOUND)

"""Inventario: `/api/v1/workspaces/<slug>/comercial/inventario/...` (26-10-2026).

Ver es de cualquier miembro; registrar entradas, salidas, tomas de inventario y cargas, de editor
para arriba (como el resto de Compras y Ventas). La lógica está en inventario.py.
"""
from django.db import transaction
from rest_framework import status
from rest_framework.response import Response

from . import inventario as inv
from .models import ConteoInventario
from .views import _Base, _error, _xlsx


def _conteo(request, pk):
    return ConteoInventario.objects.filter(organization=request.empresa, pk=pk).select_related('bodega').first()


class ResumenView(_Base):
    def get(self, request, slug):
        return Response(inv.resumen(request.empresa, request.query_params.get('bodega') or None))


class StockView(_Base):
    def get(self, request, slug):
        qp = request.query_params
        return Response(inv.vista_stock(request.empresa, qp.get('bodega') or None, qp.get('familia') or None,
                                        qp.get('estado') or None, (qp.get('q') or '').strip() or None))


class EntradaView(_Base):
    def post(self, request, slug):
        d = request.data
        m = inv.entrada_manual(request.empresa, d.get('producto'), d.get('bodega'), d.get('cantidad'),
                               d.get('costo_unitario'), d.get('motivo') or '', d.get('referencia') or '',
                               d.get('fecha'), request.user)
        return Response({'ok': True, 'movimiento_id': m.id}, status=status.HTTP_201_CREATED)


class SalidaView(_Base):
    def post(self, request, slug):
        d = request.data
        m = inv.salida_manual(request.empresa, d.get('producto'), d.get('bodega'), d.get('cantidad'),
                              d.get('motivo') or '', d.get('referencia') or '', d.get('fecha'), request.user)
        return Response({'ok': True, 'movimiento_id': m.id}, status=status.HTTP_201_CREATED)


class KardexView(_Base):
    def get(self, request, slug, producto):
        qp = request.query_params
        return Response(inv.kardex(request.empresa, producto, qp.get('bodega') or None, qp.get('desde'), qp.get('hasta')))


class MovimientosView(_Base):
    def get(self, request, slug):
        qp = request.query_params
        return Response(inv.movimientos(request.empresa, qp.get('tipo'), qp.get('motivo'), qp.get('producto'),
                                        qp.get('bodega'), qp.get('desde'), qp.get('hasta'), (qp.get('q') or '').strip()))


class ValorizacionView(_Base):
    def get(self, request, slug):
        return Response(inv.valorizacion(request.empresa, request.query_params.get('fecha')))


class RotacionView(_Base):
    def get(self, request, slug):
        try:
            dias = int(request.query_params.get('dias') or 90)
        except ValueError:
            return _error('Los días deben ser un número.')
        return Response(inv.rotacion(request.empresa, dias))


class ConteosView(_Base):
    def get(self, request, slug):
        return Response(inv.conteos(request.empresa))

    def post(self, request, slug):
        d = request.data
        c = inv.crear_conteo(request.empresa, d.get('bodega'), d.get('familia') or '', bool(d.get('solo_con_stock')),
                             d.get('productos') or None, request.user, d.get('notas') or '')
        return Response(inv.detalle_conteo(c), status=status.HTTP_201_CREATED)


class ConteoView(_Base):
    def get(self, request, slug, pk):
        c = _conteo(request, pk)
        if c is None:
            return _error('No existe.', status.HTTP_404_NOT_FOUND)
        return Response(inv.detalle_conteo(c))


class ConteoLineasView(_Base):
    @transaction.atomic
    def patch(self, request, slug, pk):
        c = _conteo(request, pk)
        if c is None:
            return _error('No existe.', status.HTTP_404_NOT_FOUND)
        inv.registrar_contadas(c, request.data.get('lineas'))
        return Response(inv.detalle_conteo(c))


class ConteoAplicarView(_Base):
    def post(self, request, slug, pk):
        c = _conteo(request, pk)
        if c is None:
            return _error('No existe.', status.HTTP_404_NOT_FOUND)
        inv.aplicar_conteo(c, request.user)
        return Response(inv.detalle_conteo(c))


class ConteoCancelarView(_Base):
    def post(self, request, slug, pk):
        c = _conteo(request, pk)
        if c is None:
            return _error('No existe.', status.HTTP_404_NOT_FOUND)
        inv.cancelar_conteo(c)
        return Response(inv.detalle_conteo(c))


class ConteoPlanillaView(_Base):
    def get(self, request, slug, pk):
        c = _conteo(request, pk)
        if c is None:
            return _error('No existe.', status.HTTP_404_NOT_FOUND)
        return _xlsx(f'Toma de inventario {c.numero}', inv.planilla_conteo(c))

    @transaction.atomic
    def post(self, request, slug, pk):
        c = _conteo(request, pk)
        if c is None:
            return _error('No existe.', status.HTTP_404_NOT_FOUND)
        archivo = request.FILES.get('archivo') or request.FILES.get('file')
        if not archivo:
            return _error('Falta el archivo.')
        errores = inv.importar_planilla_conteo(c, archivo)
        return Response({**inv.detalle_conteo(c), 'errores': errores})


class PlantillaInicialView(_Base):
    def get(self, request, slug):
        return _xlsx('Plantilla stock inicial', inv.plantilla_inicial())


class ImportarInicialView(_Base):
    def post(self, request, slug):
        archivo = request.FILES.get('archivo') or request.FILES.get('file')
        if not archivo:
            return _error('Falta el archivo.')
        return Response(inv.importar_inicial(request.empresa, archivo, request.user))


class ExportarView(_Base):
    def get(self, request, slug, que, producto=None):
        org, qp = request.empresa, request.query_params
        if que == 'stock':
            return _xlsx('Stock', inv.exportar_stock(org, qp.get('bodega') or None))
        if que == 'kardex' and producto:
            nombre, contenido = inv.exportar_kardex(org, producto, qp.get('bodega') or None, qp.get('desde'), qp.get('hasta'))
            return _xlsx(f'Kardex {nombre}', contenido)
        if que == 'valorizacion':
            fecha, contenido = inv.exportar_valorizacion(org, qp.get('fecha'))
            return _xlsx(f'Valorización al {fecha}', contenido)
        return _error('No existe.', status.HTTP_404_NOT_FOUND)

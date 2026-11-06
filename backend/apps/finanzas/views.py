"""API de Finanzas: `/api/v1/workspaces/<slug>/finanzas/...` (el slug es el de la Empresa).

Ver es de cualquier miembro; cargar, clasificar y configurar es de editor para arriba.
"""

from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import transaction
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.notificaciones import whatsapp
from apps.workspaces.permissions import IsEditor, IsMember

from . import automatizaciones, calculos, clasificador, conciliacion, constantes as c, tesoreria
from .importador import ArchivoNoReconocido, aplicar_regla, confirmar, previsualizar
from .models import (Asignacion, AutomatizacionModulo, Carga, Categoria, CierreMes, ConfiguracionTributaria, Contraparte,
                     CuentaBancaria, DeclaracionF29, DocumentoTributario, MovimientoBancario,
                     Proyecto)

MAX_ARCHIVO_MB = 10
MAX_DOCUMENTOS = 1000


class _Base(APIView):
    """Leer: miembro. Escribir: editor."""

    def get_permissions(self):
        if self.request.method in ('GET', 'HEAD', 'OPTIONS'):
            return [IsAuthenticated(), IsMember()]
        return [IsAuthenticated(), IsEditor()]


# ── Serialización ────────────────────────────────────────────────────────────

def _config(cfg):
    return {
        'regimen': cfg.regimen,
        'regimenes': [{'valor': v, 'nombre': n, 'ppm_sugerida': str(c.PPM_SUGERIDA[v])}
                      for v, n in c.REGIMENES],
        'tasa_ppm': str(cfg.tasa_ppm),
        'tasa_ppm_confirmada': cfg.tasa_ppm_confirmada,
        'iva': str(c.IVA * 100),
        'retencion_honorarios': {str(a): str(t) for a, t in c.RETENCION_HONORARIOS.items()},
    }


def _categoria(cat):
    return {'id': cat.id, 'nombre': cat.nombre, 'tipo': cat.tipo,
            'cuenta_codigo': cat.cuenta_codigo, 'cuenta_nombre': cat.cuenta_nombre}


def _proyecto(p):
    return {'id': p.id, 'nombre': p.nombre, 'activo': p.activo}


def _carga(carga):
    datos = {
        'id': carga.id, 'libro': carga.libro, 'nombre_archivo': carga.nombre_archivo,
        'estado': carga.estado, 'filas': carga.filas, 'nuevos': carga.nuevos,
        'duplicados': carga.duplicados, 'errores': carga.errores, 'ya_estaban': carga.ya_estaban,
        'creada_en': carga.creada_en.isoformat(),
    }
    if carga.estado == Carga.BORRADOR:
        filas = carga.filas_previas
        firma = lambda f: -1 if f['tipo_documento'] in c.TIPOS_QUE_RESTAN else 1
        datos['filas_previas'] = [{**f, 'signo': firma(f),
                                   'tipo_nombre': c.TIPOS_DTE.get(f['tipo_documento'], f['tipo_documento'])}
                                  for f in filas]
        datos['resumen'] = {
            'neto': sum(firma(f) * f['monto_neto'] for f in filas),
            'iva': sum(firma(f) * f['monto_iva'] for f in filas),
            'total': sum(firma(f) * f['monto_total'] for f in filas),
            'sin_categoria': sum(1 for f in filas if not f['categoria']),
            'sin_proyecto': sum(1 for f in filas if not f['proyecto']),
            'quedaran_pagadas': sum(1 for f in filas if f['pagado']),
            'contrapartes_nuevas': sorted({f['razon_social'] or f['rut'] for f in filas
                                           if f['contraparte_nueva']}),
        }
    return datos


def _documento(d):
    return {
        'id': d.id, 'libro': d.libro, 'tipo_documento': d.tipo_documento,
        'tipo_nombre': c.TIPOS_DTE.get(d.tipo_documento, d.tipo_documento),
        'folio': d.folio, 'rut': d.rut, 'razon_social': d.razon_social,
        'fecha': d.fecha.isoformat(),
        'monto_exento': d.monto_exento, 'monto_neto': d.monto_neto, 'monto_iva': d.monto_iva,
        'monto_total': d.monto_total, 'monto_retenido': d.monto_retenido, 'signo': d.signo,
        'contraparte': d.contraparte_id,
        'fecha_vencimiento': d.fecha_vencimiento.isoformat() if d.fecha_vencimiento else None,
        'pagado': d.pagado, 'fecha_pago': d.fecha_pago.isoformat() if d.fecha_pago else None,
        'categoria': d.categoria_id,
        'categoria_nombre': d.categoria.nombre if d.categoria else None,
        'medio_pago': d.medio_pago, 'estado': d.estado,
        'origen_clasificacion': d.origen_clasificacion,
        'asignaciones': [{'proyecto': a.proyecto_id, 'proyecto_nombre': a.proyecto.nombre,
                          'porcentaje': str(a.porcentaje)} for a in d.asignaciones.all()],
    }


def _error(mensaje, codigo=status.HTTP_400_BAD_REQUEST):
    return Response({'detail': mensaje}, status=codigo)


# ── Configuración tributaria ─────────────────────────────────────────────────

class ConfiguracionView(_Base):
    def get(self, request, slug):
        return Response(_config(ConfiguracionTributaria.de(request.empresa)))

    def put(self, request, slug):
        cfg = ConfiguracionTributaria.de(request.empresa)
        regimen = request.data.get('regimen', cfg.regimen)
        if regimen not in c.PPM_SUGERIDA:
            return _error('Régimen no válido.')
        cambio_regimen = regimen != cfg.regimen
        cfg.regimen = regimen
        if 'tasa_ppm' in request.data:
            try:
                tasa = Decimal(str(request.data['tasa_ppm']).replace(',', '.'))
            except InvalidOperation:
                return _error('La tasa de PPM debe ser un número.')
            if not (Decimal('0') <= tasa <= Decimal('20')):
                return _error('La tasa de PPM debe estar entre 0% y 20%.')
            cfg.tasa_ppm = tasa
            cfg.tasa_ppm_confirmada = True
        elif cambio_regimen:
            # Cambió el régimen sin decir tasa: se propone la sugerida y queda sin confirmar.
            cfg.tasa_ppm = c.PPM_SUGERIDA[regimen]
            cfg.tasa_ppm_confirmada = False
        cfg.save()
        return Response(_config(cfg))


# ── Categorías y proyectos ───────────────────────────────────────────────────

class CategoriasView(_Base):
    def get(self, request, slug):
        Categoria.asegurar_iniciales(request.empresa)
        return Response([_categoria(x) for x in Categoria.objects.filter(organization=request.empresa)])

    def post(self, request, slug):
        nombre = (request.data.get('nombre') or '').strip()[:80]
        tipo = request.data.get('tipo')
        if not nombre or tipo not in ('ingreso', 'gasto'):
            return _error('Indique el nombre y si es de ingreso o de gasto.')
        cat, _ = Categoria.objects.get_or_create(organization=request.empresa, nombre=nombre,
                                                 defaults={'tipo': tipo})
        return Response(_categoria(cat), status=status.HTTP_201_CREATED)


class CategoriaView(_Base):
    """Asociar una categoría a su cuenta contable."""

    def patch(self, request, slug, pk):
        cat = Categoria.objects.filter(organization=request.empresa, pk=pk).first()
        if not cat:
            return _error('No existe.', status.HTTP_404_NOT_FOUND)
        if 'cuenta_codigo' in request.data:
            cat.cuenta_codigo = str(request.data['cuenta_codigo'] or '').strip()[:20]
        if 'cuenta_nombre' in request.data:
            cat.cuenta_nombre = str(request.data['cuenta_nombre'] or '').strip()[:120]
        cat.save(update_fields=['cuenta_codigo', 'cuenta_nombre'])
        return Response(_categoria(cat))


class ProyectosView(_Base):
    def get(self, request, slug):
        return Response([_proyecto(p) for p in Proyecto.objects.filter(organization=request.empresa)])

    def post(self, request, slug):
        nombre = (request.data.get('nombre') or '').strip()[:120]
        if not nombre:
            return _error('Indique el nombre del proyecto.')
        p, _ = Proyecto.objects.get_or_create(organization=request.empresa, nombre=nombre)
        return Response(_proyecto(p), status=status.HTTP_201_CREATED)


# ── Cargas del SII ───────────────────────────────────────────────────────────

class CargasView(_Base):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request, slug):
        return Response([_carga(x) for x in Carga.objects.filter(organization=request.empresa)[:50]])

    def post(self, request, slug):
        archivo = request.data.get('file')
        if not archivo:
            return _error('Adjunte el archivo descargado del SII.')
        if archivo.size > MAX_ARCHIVO_MB * 1024 * 1024:
            return _error(f'El archivo supera los {MAX_ARCHIVO_MB} MB.')
        libro = request.data.get('libro') or None
        if libro and libro not in dict(c.LIBROS):
            return _error('Libro no válido.')
        Categoria.asegurar_iniciales(request.empresa)
        try:
            carga = previsualizar(request.empresa, archivo.read(), archivo.name, libro=libro,
                                  usuario=request.user)
        except ArchivoNoReconocido as e:
            return _error(str(e))
        return Response(_carga(carga), status=status.HTTP_201_CREATED)


def _borrador(request, pk):
    return Carga.objects.filter(organization=request.empresa, pk=pk, estado=Carga.BORRADOR).first()


class CargaView(_Base):
    """La carga en revisión: verla o cancelarla (no deja nada)."""

    def get(self, request, slug, pk):
        carga = Carga.objects.filter(organization=request.empresa, pk=pk).first()
        if not carga:
            return _error('No existe.', status.HTTP_404_NOT_FOUND)
        return Response(_carga(carga))

    def delete(self, request, slug, pk):
        carga = _borrador(request, pk)
        if not carga:
            return _error('No hay una carga en revisión con ese número.', status.HTTP_404_NOT_FOUND)
        carga.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SugerirCargaView(_Base):
    """La IA propone categoría para las filas de la carga que quedaron sin proponer."""

    def post(self, request, slug, pk):
        carga = _borrador(request, pk)
        if not carga:
            return _error('No hay una carga en revisión con ese número.', status.HTTP_404_NOT_FOUND)
        sugeridos = clasificador.sugerir_en_carga(carga)
        carga.refresh_from_db()
        return Response({**_carga(carga), 'sugeridos': sugeridos})


class ConfirmarCargaView(_Base):
    """Importa la carga con lo decidido en la revisión: {"decisiones": {n: {...}}}."""

    def post(self, request, slug, pk):
        carga = _borrador(request, pk)
        if not carga:
            return _error('No hay una carga en revisión con ese número.', status.HTTP_404_NOT_FOUND)
        decisiones = request.data.get('decisiones') or {}
        categorias = set(Categoria.objects.filter(organization=request.empresa).values_list('id', flat=True))
        proyectos = set(Proyecto.objects.filter(organization=request.empresa).values_list('id', flat=True))
        for d in decisiones.values():
            if d.get('categoria') not in (None, '') and d['categoria'] not in categorias:
                return _error('Una de las categorías no existe.')
            if d.get('proyecto') not in (None, '') and d['proyecto'] not in proyectos:
                return _error('Uno de los proyectos no existe.')
        carga = confirmar(carga, decisiones)
        return Response(_carga(carga))


# ── Documentos ───────────────────────────────────────────────────────────────

def _documentos_de(request):
    qs = (DocumentoTributario.objects.filter(organization=request.empresa)
          .select_related('categoria').prefetch_related('asignaciones__proyecto'))
    libro = request.query_params.get('libro')
    if libro:
        qs = qs.filter(libro=libro)
    estado = request.query_params.get('estado')
    if estado:
        qs = qs.filter(estado=estado)
    mes = request.query_params.get('mes')                    # AAAA-MM
    if mes:
        try:
            anio, m = (int(x) for x in mes.split('-'))
            qs = qs.filter(fecha__year=anio, fecha__month=m)
        except ValueError:
            pass
    return qs


class DocumentosView(_Base):
    def get(self, request, slug):
        qs = _documentos_de(request)
        total = qs.count()
        return Response({
            'total': total,
            'por_revisar': qs.filter(estado=DocumentoTributario.POR_REVISAR).count(),
            'documentos': [_documento(d) for d in qs[:MAX_DOCUMENTOS]],
        })


def _validar_categoria(org, valor):
    if valor in (None, ''):
        return None
    return Categoria.objects.filter(organization=org, id=valor).first() or False


def _validar_reparto(org, reparto):
    """[{proyecto, porcentaje}] → lista limpia, o un mensaje de error."""
    limpio, suma = [], Decimal('0')
    for r in reparto or []:
        proyecto = Proyecto.objects.filter(organization=org, id=r.get('proyecto')).first()
        if not proyecto:
            return None, 'Uno de los proyectos no existe.'
        try:
            pct = Decimal(str(r.get('porcentaje')))
        except InvalidOperation:
            return None, 'Los porcentajes deben ser números.'
        if pct <= 0:
            return None, 'Cada porcentaje debe ser mayor que 0.'
        suma += pct
        limpio.append({'proyecto': proyecto.id, 'porcentaje': str(pct)})
    if suma > 100:
        return None, f'El reparto suma {suma}%: no puede pasar de 100%.'
    return limpio, None


class DocumentoView(_Base):
    @transaction.atomic
    def patch(self, request, slug, pk):
        d = DocumentoTributario.objects.filter(organization=request.empresa, pk=pk).first()
        if not d:
            return _error('No existe.', status.HTTP_404_NOT_FOUND)
        data = request.data
        if 'categoria' in data:
            cat = _validar_categoria(request.empresa, data['categoria'])
            if cat is False:
                return _error('La categoría no existe.')
            d.categoria = cat
            d.origen_clasificacion = ''                     # la puso una persona
        if 'medio_pago' in data:
            d.medio_pago = (data['medio_pago'] or '')[:40]
        if 'estado' in data:
            if data['estado'] not in dict(DocumentoTributario.ESTADOS):
                return _error('Estado no válido.')
            d.estado = data['estado']
        if 'pagado' in data:
            d.pagado = bool(data['pagado'])
            d.fecha_pago = date.today() if d.pagado else None
        reparto = None
        if 'asignaciones' in data:
            reparto, err = _validar_reparto(request.empresa, data['asignaciones'])
            if err:
                return _error(err)
            d.asignaciones.all().delete()
            Asignacion.objects.bulk_create([
                Asignacion(documento=d, proyecto_id=r['proyecto'], porcentaje=r['porcentaje'])
                for r in reparto
            ])
        d.save()

        aplicados = 0
        if data.get('crear_regla'):
            # "Siempre así para este proveedor": la regla se guarda y se aplica hacia atrás.
            ficha, _ = Contraparte.objects.update_or_create(
                organization=request.empresa, libro=d.libro, rut=d.rut,
                defaults={'razon_social': d.razon_social, 'regla_activa': True,
                          'categoria': d.categoria, 'medio_pago': d.medio_pago,
                          'reparto': reparto if reparto is not None else [
                              {'proyecto': a.proyecto_id, 'porcentaje': str(a.porcentaje)}
                              for a in d.asignaciones.all()]},
            )
            if d.contraparte_id != ficha.id:
                d.contraparte = ficha
                d.save(update_fields=['contraparte'])
            for otro in DocumentoTributario.objects.filter(
                    organization=request.empresa, libro=d.libro, rut=d.rut).exclude(pk=d.pk):
                aplicar_regla(otro, ficha)
                aplicados += 1
        d.refresh_from_db()
        return Response({**_documento(d), 'regla_aplicada_a': aplicados})


class LoteView(_Base):
    """Clasificar o confirmar varios documentos de una vez."""

    @transaction.atomic
    def post(self, request, slug):
        ids = request.data.get('ids') or []
        qs = DocumentoTributario.objects.filter(organization=request.empresa, id__in=ids)
        cambios = {}
        if 'categoria' in request.data:
            cat = _validar_categoria(request.empresa, request.data['categoria'])
            if cat is False:
                return _error('La categoría no existe.')
            cambios.update(categoria=cat, origen_clasificacion='')
        if 'medio_pago' in request.data:
            cambios['medio_pago'] = (request.data['medio_pago'] or '')[:40]
        if request.data.get('confirmar'):
            cambios['estado'] = DocumentoTributario.CONFIRMADO
        if 'pagado' in request.data:
            cambios['pagado'] = bool(request.data['pagado'])
            cambios['fecha_pago'] = date.today() if cambios['pagado'] else None
        if not cambios:
            return _error('No hay nada que cambiar.')
        actualizados = qs.update(**cambios)
        return Response({'actualizados': actualizados})


class SugerirView(_Base):
    """La IA propone la categoría de lo que está sin clasificar."""

    def post(self, request, slug):
        Categoria.asegurar_iniciales(request.empresa)
        sugeridos = clasificador.sugerir(request.empresa)
        return Response({'sugeridos': sugeridos})


def _ficha(x, stats):
    return {
        'id': x.id, 'libro': x.libro, 'rut': x.rut, 'razon_social': x.razon_social,
        'plazo_dias': x.plazo_dias, 'plazo': x.plazo, 'plazo_por_defecto': c.PLAZO_PAGO_POR_DEFECTO,
        'regla_activa': x.regla_activa, 'categoria': x.categoria_id,
        'categoria_nombre': x.categoria.nombre if x.categoria else None,
        'medio_pago': x.medio_pago, 'reparto': x.reparto, **stats,
    }


class ContrapartesView(_Base):
    """Las fichas de proveedores (compras, honorarios) o clientes (ventas), con sus números."""

    def get(self, request, slug):
        qs = Contraparte.objects.filter(organization=request.empresa).select_related('categoria')
        libros = request.query_params.getlist('libro')
        if libros:
            qs = qs.filter(libro__in=libros)
        stats = {}
        for d in DocumentoTributario.objects.filter(organization=request.empresa,
                                                    contraparte__in=qs).only(
                'contraparte_id', 'monto_total', 'tipo_documento', 'pagado'):
            s_ = stats.setdefault(d.contraparte_id, {'documentos': 0, 'total': 0, 'pendiente': 0})
            s_['documentos'] += 1
            s_['total'] += d.signo * d.monto_total
            if not d.pagado:
                s_['pendiente'] += d.signo * d.monto_total
        vacio = {'documentos': 0, 'total': 0, 'pendiente': 0}
        return Response([_ficha(x, stats.get(x.id, vacio)) for x in qs])


class ContraparteView(_Base):
    """Editar la ficha: el plazo habitual de pago y la regla de clasificación."""

    def patch(self, request, slug, pk):
        x = Contraparte.objects.filter(organization=request.empresa, pk=pk).first()
        if not x:
            return _error('No existe.', status.HTTP_404_NOT_FOUND)
        data = request.data
        if 'plazo_dias' in data:
            if data['plazo_dias'] in (None, ''):
                x.plazo_dias = None
            else:
                try:
                    x.plazo_dias = int(data['plazo_dias'])
                except (TypeError, ValueError):
                    return _error('El plazo debe ser un número de días.')
                if not 0 <= x.plazo_dias <= 365:
                    return _error('El plazo debe estar entre 0 y 365 días.')
        if 'categoria' in data:
            cat = _validar_categoria(request.empresa, data['categoria'])
            if cat is False:
                return _error('La categoría no existe.')
            x.categoria = cat
        if 'regla_activa' in data:
            x.regla_activa = bool(data['regla_activa'])
        x.save()
        return Response(_ficha(x, {'documentos': x.documentos.count(), 'total': 0, 'pendiente': 0}))


# ── Los números (etapa 2) ────────────────────────────────────────────────────

def _anio(request):
    try:
        return int(request.query_params.get('anio') or date.today().year)
    except ValueError:
        return date.today().year


class ResumenView(_Base):
    def get(self, request, slug):
        anio = _anio(request)
        return Response({**calculos.resumen(request.empresa, anio),
                         'anios': calculos.anios_con_datos(request.empresa)})


class ImpuestosView(_Base):
    def get(self, request, slug):
        return Response(calculos.f29(request.empresa, _anio(request)))


class DeclaracionView(_Base):
    """Marcar el F29 de un mes como pagado (o deshacerlo)."""

    def patch(self, request, slug, anio, mes):
        if not 1 <= mes <= 12:
            return _error('Mes no válido.')
        dec, _ = DeclaracionF29.objects.get_or_create(organization=request.empresa, anio=anio, mes=mes)
        dec.pagado = bool(request.data.get('pagado', True))
        if dec.pagado:
            try:
                dec.monto_pagado = int(request.data['monto_pagado']) if request.data.get('monto_pagado') not in (None, '') else None
            except (TypeError, ValueError):
                return _error('El monto pagado debe ser un número.')
            try:
                dec.fecha_pago = date.fromisoformat(request.data['fecha_pago']) if request.data.get('fecha_pago') else date.today()
            except ValueError:
                return _error('Fecha no válida.')
        else:
            dec.monto_pagado, dec.fecha_pago = None, None
        dec.save()
        return Response(calculos.f29(request.empresa, anio))


class PorCategoriaView(_Base):
    def get(self, request, slug):
        periodo = request.query_params.get('periodo', 'mes')
        if periodo not in ('mes', 'anio', 'todo'):
            periodo = 'mes'
        anio = _anio(request)
        try:
            mes = int(request.query_params.get('mes') or date.today().month)
        except ValueError:
            mes = date.today().month
        return Response(calculos.por_categoria(request.empresa, periodo, anio, mes))


class MargenProyectosView(_Base):
    def get(self, request, slug):
        anio = request.query_params.get('anio')
        return Response(calculos.margen_por_proyecto(request.empresa, int(anio) if anio else None))


# ── Conciliación ("El cuadre") ───────────────────────────────────────────────

TIPOS_SD = dict(MovimientoBancario.TIPOS_SIN_DOCUMENTO)


def _cuenta(x):
    ultima = x.cartolas.exclude(saldo_final__isnull=True).order_by('-hasta').first()
    return {'id': x.id, 'banco': x.banco, 'nombre': x.nombre, 'numero': x.numero,
            'etiqueta': str(x), 'saldo': ultima.saldo_final if ultima else None,
            'saldo_al': ultima.hasta.isoformat() if ultima and ultima.hasta else None,
            'movimientos': x.movimientos.count()}


def _doc_corto(d, diferencia=None, nombre=None):
    r = {'id': d.id, 'libro': d.libro, 'folio': d.folio, 'razon_social': d.razon_social,
         'fecha': d.fecha.isoformat(), 'monto': conciliacion.monto_a_pagar(d),
         'tipo_nombre': c.TIPOS_DTE.get(d.tipo_documento, d.tipo_documento)}
    if diferencia is not None:
        r.update(diferencia=diferencia, nombre_coincide=nombre)
    return r


def _movimiento(m, con_candidatos=False):
    pareja = m.pareja
    r = {
        'id': m.id, 'cuenta': m.cuenta_id, 'cuenta_etiqueta': str(m.cuenta), 'fecha': m.fecha.isoformat(),
        'descripcion': m.descripcion, 'monto': m.monto, 'estado': m.estado, 'origen': m.origen,
        'tipo_sin_documento': m.tipo_sin_documento, 'tipo_nombre': TIPOS_SD.get(m.tipo_sin_documento, ''),
        'nota': m.nota,
        'documentos': [_doc_corto(d) for d in m.documentos.all()],
        'pareja': {'id': pareja.id, 'cuenta_etiqueta': str(pareja.cuenta), 'fecha': pareja.fecha.isoformat(),
                   'monto': pareja.monto} if pareja else None,
    }
    if con_candidatos and m.estado == MovimientoBancario.PENDIENTE and not pareja:
        # Solo lo plausible: monto parecido (±5%) o el nombre de la contraparte en la glosa.
        # Proponer facturas que no tienen nada que ver hace más difícil decidir.
        tolerancia = max(1000, abs(m.monto) * 5 // 100)
        r['candidatos'] = [_doc_corto(d, dif, nom) for d, dif, nom in conciliacion.candidatos(m)
                           if dif <= tolerancia or nom][:6]
    return r


class CuentasView(_Base):
    def get(self, request, slug):
        return Response([_cuenta(x) for x in CuentaBancaria.objects.filter(organization=request.empresa)])

    def post(self, request, slug):
        banco = (request.data.get('banco') or '').strip()[:80]
        if not banco:
            return _error('Indique el banco.')
        x = CuentaBancaria.objects.create(organization=request.empresa, banco=banco,
                                          nombre=(request.data.get('nombre') or '').strip()[:80],
                                          numero=(request.data.get('numero') or '').strip()[:40])
        return Response(_cuenta(x), status=status.HTTP_201_CREATED)


class CartolasView(_Base):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, slug):
        cuenta = CuentaBancaria.objects.filter(organization=request.empresa, pk=request.data.get('cuenta')).first()
        if not cuenta:
            return _error('Elija la cuenta a la que corresponde la cartola.')
        archivo = request.data.get('file')
        if not archivo:
            return _error('Adjunte la cartola descargada del banco.')
        if archivo.size > MAX_ARCHIVO_MB * 1024 * 1024:
            return _error(f'El archivo supera los {MAX_ARCHIVO_MB} MB.')
        try:
            cartola = conciliacion.cargar_cartola(cuenta, archivo.read(), archivo.name, request.user)
        except conciliacion.CartolaNoReconocida as e:
            return _error(str(e))
        return Response({
            'id': cartola.id, 'cuenta': _cuenta(cuenta), 'nuevos': cartola.nuevos,
            'duplicados': cartola.duplicados, 'errores': cartola.errores,
            'desde': cartola.desde.isoformat() if cartola.desde else None,
            'hasta': cartola.hasta.isoformat() if cartola.hasta else None,
        }, status=status.HTTP_201_CREATED)


def _mes(request):
    hoy = date.today()
    try:
        return int(request.query_params.get('anio') or hoy.year), int(request.query_params.get('mes') or hoy.month)
    except ValueError:
        return hoy.year, hoy.month


class CuadreView(_Base):
    def get(self, request, slug):
        meses = conciliacion.meses_con_movimientos(request.empresa)
        if request.query_params.get('anio'):
            anio, mes = _mes(request)
        elif meses:
            # Abre donde hay trabajo: el mes más reciente con pendientes; si no hay, el último.
            pendiente = (MovimientoBancario.objects.filter(organization=request.empresa,
                                                           estado=MovimientoBancario.PENDIENTE)
                         .order_by('-fecha').first())
            anio, mes = (pendiente.fecha.year, pendiente.fecha.month) if pendiente else meses[0]
        else:
            anio, mes = _mes(request)
        return Response({**conciliacion.cuadre(request.empresa, anio, mes),
                         'meses': [{'anio': a, 'mes': m} for a, m in meses]})


class MovimientosView(_Base):
    def get(self, request, slug):
        anio, mes = _mes(request)
        qs = (MovimientoBancario.objects.filter(organization=request.empresa, fecha__year=anio, fecha__month=mes)
              .select_related('cuenta', 'pareja__cuenta').prefetch_related('documentos'))
        filtro = request.query_params.get('ver')
        if filtro == 'pendientes':
            qs = qs.filter(estado=MovimientoBancario.PENDIENTE)
        return Response([_movimiento(m, con_candidatos=True) for m in qs])


class MovimientoView(_Base):
    """Resolver un movimiento: conciliar, identificar, confirmar o descartar traspaso, deshacer."""

    def post(self, request, slug, pk, accion):
        m = MovimientoBancario.objects.filter(organization=request.empresa, pk=pk).first()
        if not m:
            return _error('No existe.', status.HTTP_404_NOT_FOUND)
        if CierreMes.objects.filter(organization=request.empresa, anio=m.fecha.year, mes=m.fecha.month).exists():
            return _error('Ese mes está cerrado. Reábralo para cambiar el cuadre.')
        if accion == 'conciliar':
            docs = list(DocumentoTributario.objects.filter(organization=request.empresa,
                                                           id__in=request.data.get('documentos') or []))
            if not docs:
                return _error('Elija el o los documentos que paga este movimiento.')
            conciliacion.conciliar_manual(m, docs)
        elif accion == 'identificar':
            tipo = request.data.get('tipo')
            if tipo not in TIPOS_SD:
                return _error('Tipo no válido.')
            conciliacion.identificar(m, tipo, request.data.get('nota') or '')
        elif accion == 'traspaso':
            conciliacion.confirmar_traspaso(m)
        elif accion == 'no-es-traspaso':
            conciliacion.descartar_traspaso(m)
        elif accion == 'deshacer':
            conciliacion.deshacer(m)
        else:
            return _error('Acción no válida.', status.HTTP_404_NOT_FOUND)
        m.refresh_from_db()
        return Response(_movimiento(m, con_candidatos=True))


class CierreView(_Base):
    def get(self, request, slug):
        return Response([{'anio': x.anio, 'mes': x.mes, 'porcentaje': str(x.porcentaje),
                          'resumen': x.resumen, 'cerrado_en': x.cerrado_en.isoformat()}
                         for x in CierreMes.objects.filter(organization=request.empresa)])

    def post(self, request, slug):
        anio, mes = int(request.data.get('anio')), int(request.data.get('mes'))
        resumen = conciliacion.cuadre(request.empresa, anio, mes)
        if resumen['movimientos'] == 0:
            return _error('No hay movimientos en ese mes.')
        CierreMes.objects.update_or_create(
            organization=request.empresa, anio=anio, mes=mes,
            defaults={'porcentaje': resumen['porcentaje'] or 0, 'resumen': resumen, 'cerrado_por': request.user})
        return Response(conciliacion.cuadre(request.empresa, anio, mes))

    def delete(self, request, slug):
        anio, mes = _mes(request)
        CierreMes.objects.filter(organization=request.empresa, anio=anio, mes=mes).delete()
        return Response(conciliacion.cuadre(request.empresa, anio, mes))


# ── Finanzas: la plata (etapa 3) ─────────────────────────────────────────────

class CuentasPorView(_Base):
    """/cuentas-por/cobrar/ o /cuentas-por/pagar/."""

    def get(self, request, slug, tipo):
        if tipo not in ('cobrar', 'pagar'):
            return _error('No existe.', status.HTTP_404_NOT_FOUND)
        return Response(tesoreria.cuentas(request.empresa, tipo))


class CajaView(_Base):
    def get(self, request, slug):
        return Response(tesoreria.caja(request.empresa))


class CuentaDuenoView(_Base):
    def get(self, request, slug):
        return Response(tesoreria.cuenta_del_dueno(request.empresa))


# ── Automatizaciones de cada módulo ──────────────────────────────────────────

def _auto(entrada, x):
    x = x or AutomatizacionModulo(clave=entrada['clave'], activa=False)
    prog = automatizaciones.programacion(x)
    return {
        **{k: v for k, v in entrada.items() if k != 'programacion'},
        'activa': bool(x.activa), 'por_correo': x.por_correo, 'por_whatsapp': x.por_whatsapp,
        'programacion': prog, 'cuando': automatizaciones.describir(prog),
        'proxima_ejecucion': x.proxima_ejecucion.isoformat() if x.activa and x.proxima_ejecucion else None,
        'seguidores': list(x.seguidores.values_list('id', flat=True)) if x.pk else [],
        'whatsapp_configurado': whatsapp.configurado(),
        'ultima_ejecucion': x.ultima_ejecucion.isoformat() if x.ultima_ejecucion else None,
        'ultimo_resultado': x.ultimo_resultado,
    }


def _entero(valor, minimo, maximo, nombre):
    try:
        n = int(valor)
    except (TypeError, ValueError):
        raise ValueError(f'{nombre}: tiene que ser un número.')
    if not minimo <= n <= maximo:
        raise ValueError(f'{nombre}: tiene que estar entre {minimo} y {maximo}.')
    return n


class ActividadAgenteView(_Base):
    """Lo que hizo hoy el agente de un módulo (actividad.py), para su vista "Agente"."""

    def get(self, request, slug, modulo):
        from . import actividad
        if modulo not in actividad.MODULOS:
            return _error('Módulo no válido.', status.HTTP_404_NOT_FOUND)
        return Response(actividad.de_hoy(request.empresa, modulo))


class AutomatizacionesView(_Base):
    def get(self, request, slug):
        modulo = request.query_params.get('modulo')
        guardadas = {x.clave: x for x in AutomatizacionModulo.objects.filter(organization=request.empresa)
                     .prefetch_related('seguidores')}
        return Response([_auto(a, guardadas.get(a['clave'])) for a in automatizaciones.CATALOGO
                         if not modulo or a['modulo'] == modulo])


class AutomatizacionView(_Base):
    @transaction.atomic
    def patch(self, request, slug, clave):
        if clave not in automatizaciones.POR_CLAVE:
            return _error('No existe.', status.HTTP_404_NOT_FOUND)
        x, _ = AutomatizacionModulo.objects.get_or_create(organization=request.empresa, clave=clave,
                                                          defaults={'activa': False})
        data = request.data
        for campo in ('activa', 'por_correo', 'por_whatsapp'):
            if campo in data:
                setattr(x, campo, bool(data[campo]))
        try:
            if 'frecuencia' in data:
                if data['frecuencia'] not in dict(AutomatizacionModulo.FRECUENCIAS):
                    return _error('Frecuencia no válida.')
                x.frecuencia = data['frecuencia']
            if 'hora' in data:
                x.hora = _entero(data['hora'], 0, 23, 'La hora')
            if 'dia_semana' in data:
                x.dia_semana = _entero(data['dia_semana'], 0, 6, 'El día de la semana')
            if 'dia_mes' in data:
                # Hasta el 28: todos los meses lo tienen.
                x.dia_mes = _entero(data['dia_mes'], 1, 28, 'El día del mes')
        except ValueError as e:
            return _error(str(e))
        if 'seguidores' in data:
            from apps.workspaces.models import Membership
            pedidos = {int(i) for i in (data['seguidores'] or []) if str(i).isdigit()}
            validos = set(Membership.objects.filter(organization=request.empresa, user_id__in=pedidos)
                          .values_list('user_id', flat=True))
            if pedidos - validos:
                return _error('Solo pueden seguirla personas de la empresa.')
            x.seguidores.set(validos)
        automatizaciones.reprogramar(x)
        x.save()
        return Response(_auto(automatizaciones.POR_CLAVE[clave], x))

    def post(self, request, slug, clave):
        """Probar ahora: corre sin esperar el calendario y sin avisar a nadie."""
        if clave not in automatizaciones.POR_CLAVE:
            return _error('No existe.', status.HTTP_404_NOT_FOUND)
        x = (AutomatizacionModulo.objects.filter(organization=request.empresa, clave=clave).first()
             or AutomatizacionModulo(organization=request.empresa, clave=clave))
        return Response(automatizaciones.ejecutar(x, forzar=True))



class VentasView(_Base):
    def get(self, request, slug):
        anio = _anio(request)
        return Response({**calculos.ventas(request.empresa, anio),
                         'anios': calculos.anios_con_datos(request.empresa)})

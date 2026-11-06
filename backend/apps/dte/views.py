"""Facturación electrónica: `/api/v1/workspaces/<slug>/dte/...`.

Ver el estado y la bitácora es de cualquier miembro; el certificado, los folios, la configuración y
encender o apagar el facturador son del administrador de la empresa (llevan llaves privadas y
deciden qué se le manda al SII a nombre de la empresa).
"""
from datetime import date

from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.workspaces.permissions import IsAdmin, IsEditor, IsMember

from . import motor, servicio, sii
from .models import Caf, ConfiguracionDTE, DocumentoEmitido, EnvioSII
from .nucleo import ErrorDTE
from .nucleo import rut as ruts
from .nucleo.documento import TIPOS

MAX_LISTA = 200
MAX_ARCHIVO = 512 * 1024


class _Base(APIView):
    """GET para miembros; lo demás, para administradores. Todo, solo si el facturador está
    habilitado para la empresa (servicio.disponible), salvo el estado que lo informa."""
    rol_escritura = IsAdmin
    siempre_visible = False

    def get_permissions(self):
        if self.request.method in ('GET', 'HEAD', 'OPTIONS'):
            return [IsAuthenticated(), IsMember()]
        return [IsAuthenticated(), self.rol_escritura()]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not self.siempre_visible and not servicio.disponible(request.empresa):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('El facturador electrónico de Afable todavía no está habilitado para esta empresa.')

    def handle_exception(self, exc):
        if isinstance(exc, ErrorDTE):
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return super().handle_exception(exc)


def _config(cfg):
    return {
        'camino': cfg.camino, 'ambiente': cfg.ambiente, 'activo': cfg.activo, 'actecos': cfg.actecos,
        'telefono': cfg.telefono, 'correo_emisor': cfg.correo_emisor, 'sucursal': cfg.sucursal,
        'codigo_sucursal': cfg.codigo_sucursal, 'oficina_sii': cfg.oficina_sii, 'resolucion_numero': cfg.resolucion_numero,
        'resolucion_fecha': cfg.resolucion_fecha, 'certificacion_fecha': cfg.certificacion_fecha,
        'correo_intercambio': cfg.correo_intercambio, 'enviar_a_clientes': cfg.enviar_a_clientes,
        'imap_servidor': cfg.imap_servidor, 'imap_puerto': cfg.imap_puerto, 'imap_usuario': cfg.imap_usuario,
        'imap_tiene_clave': bool(cfg._imap_clave), 'imap_revisado_en': cfg.imap_revisado_en, 'imap_error': cfg.imap_error,
    }


def _caf(c):
    return {'id': c.id, 'tipo': c.tipo, 'nombre': TIPOS.get(c.tipo, str(c.tipo)), 'ambiente': c.ambiente,
            'desde': c.desde, 'hasta': c.hasta, 'siguiente': c.siguiente, 'disponibles': c.disponibles,
            'fecha_autorizacion': c.fecha_autorizacion, 'creado_en': c.creado_en}


def _documento(x):
    return {'id': x.id, 'tipo': x.tipo, 'nombre': TIPOS.get(x.tipo, str(x.tipo)), 'folio': x.folio,
            'fecha': x.fecha, 'ambiente': x.ambiente, 'receptor_rut': x.receptor_rut,
            'receptor_razon_social': x.receptor_razon_social, 'monto_total': x.monto_total,
            'estado': x.estado, 'estado_nombre': x.get_estado_display(), 'detalle_estado': x.detalle_estado,
            'envio': x.envio_id, 'trackid': x.envio.trackid if x.envio_id else '',
            'documento_tributario': x.documento_tributario_id, 'creado_en': x.creado_en}


def _envio(e):
    return {'id': e.id, 'ambiente': e.ambiente, 'estado': e.estado, 'estado_nombre': e.get_estado_display(),
            'trackid': e.trackid, 'estado_sii': e.estado_sii, 'glosa': e.glosa, 'resumen': e.resumen,
            'error': e.error, 'intentos': e.intentos, 'siguiente_intento': e.siguiente_intento,
            'respuesta': e.respuesta, 'creado_en': e.creado_en, 'actualizado_en': e.actualizado_en,
            'documentos': [_documento(x) for x in e.documentos.all()]}


def _fecha(valor, nombre):
    if not valor:
        return None
    try:
        return date.fromisoformat(str(valor)[:10])
    except ValueError:
        raise ErrorDTE(f'{nombre} no es una fecha válida.')


class EstadoView(_Base):
    siempre_visible = True

    def get(self, request, slug):
        org = request.empresa
        e = servicio.estado(org, request.query_params.get('ambiente') or None)
        if e['disponible']:
            e['configuracion'] = _config(ConfiguracionDTE.de(org))
        return Response(e)


class ConfiguracionView(_Base):
    def get(self, request, slug):
        return Response(_config(ConfiguracionDTE.de(request.empresa)))

    def put(self, request, slug):
        cfg = ConfiguracionDTE.de(request.empresa)
        d = request.data
        if 'camino' in d:
            if d['camino'] not in dict(ConfiguracionDTE.CAMINOS):
                raise ErrorDTE('Indique si la empresa ya emite facturas electrónicas o si debe certificarse.')
            cfg.camino = d['camino']
        if 'actecos' in d:
            actecos = [str(a).strip() for a in (d['actecos'] or []) if str(a).strip()]
            if len(actecos) > 4 or any(not a.isdigit() or len(a) != 6 for a in actecos):
                raise ErrorDTE('La actividad económica son de 1 a 4 códigos del SII de 6 dígitos (por ejemplo 620200).')
            cfg.actecos = actecos
        for campo, largo in (('telefono', 20), ('correo_emisor', 80), ('sucursal', 20), ('correo_intercambio', 120),
                             ('oficina_sii', 60)):
            if campo in d:
                setattr(cfg, campo, str(d[campo] or '').strip()[:largo])
        if 'codigo_sucursal' in d:
            codigo = str(d['codigo_sucursal'] or '').strip()
            if codigo and (not codigo.isdigit() or len(codigo) > 9):
                raise ErrorDTE('El código de sucursal del SII es un número de hasta 9 dígitos.')
            cfg.codigo_sucursal = codigo
        if 'resolucion_numero' in d:
            n = d['resolucion_numero']
            if n in (None, ''):
                cfg.resolucion_numero = None
            elif not str(n).isdigit():
                raise ErrorDTE('El número de resolución es un número entero (0 en certificación).')
            else:
                cfg.resolucion_numero = int(n)
        if 'resolucion_fecha' in d:
            cfg.resolucion_fecha = _fecha(d['resolucion_fecha'], 'La fecha de resolución')
        if 'certificacion_fecha' in d:
            cfg.certificacion_fecha = _fecha(d['certificacion_fecha'], 'La fecha de resolución de certificación')
        cfg.save()
        return Response(_config(cfg))


class CertificadoView(_Base):
    def post(self, request, slug):
        archivo = request.FILES.get('archivo')
        if not archivo:
            raise ErrorDTE('Adjunte el archivo del certificado (.pfx o .p12).')
        if archivo.size > MAX_ARCHIVO:
            raise ErrorDTE('El archivo es demasiado grande para ser un certificado.')
        c = servicio.cargar_certificado(request.empresa, archivo.read(), request.data.get('clave', ''), request.user)
        return Response({'titular': c.titular_nombre, 'rut': c.titular_rut, 'emitido_por': c.emitido_por,
                         'vence': c.valido_hasta}, status=status.HTTP_201_CREATED)


class CafsView(_Base):
    def get(self, request, slug):
        qs = Caf.objects.filter(organization=request.empresa)
        if request.query_params.get('ambiente'):
            qs = qs.filter(ambiente=request.query_params['ambiente'])
        return Response([_caf(c) for c in qs])

    def post(self, request, slug):
        archivo = request.FILES.get('archivo')
        if not archivo:
            raise ErrorDTE('Adjunte el archivo CAF (.xml) que entrega el SII.')
        if archivo.size > MAX_ARCHIVO:
            raise ErrorDTE('El archivo es demasiado grande para ser un CAF.')
        primer = request.data.get('primer_folio') or None
        c = servicio.cargar_caf(request.empresa, archivo.read(), request.user, int(primer) if primer else None)
        return Response(_caf(c), status=status.HTTP_201_CREATED)


class ProbarConexionView(_Base):
    """Pide una sesión al SII con el certificado: confirma que el SII lo reconoce."""

    def post(self, request, slug):
        ambiente = request.data.get('ambiente') or ConfiguracionDTE.de(request.empresa).ambiente or sii.CERTIFICACION
        cliente = motor.cliente(request.empresa, ambiente)
        cliente.token(renovar=True)
        return Response({'ok': True, 'ambiente': ambiente, 'titular': cliente.certificado.nombre,
                         'rut': cliente.certificado.rut})


class ActivarView(_Base):
    def post(self, request, slug):
        cfg = servicio.activar(request.empresa, request.data.get('ambiente'), request.user)
        return Response(_config(cfg))


class DesactivarView(_Base):
    def post(self, request, slug):
        return Response(_config(servicio.desactivar(request.empresa)))


class DocumentosView(_Base):
    def get(self, request, slug):
        qs = DocumentoEmitido.objects.filter(organization=request.empresa).select_related('envio')
        for campo in ('ambiente', 'estado', 'tipo'):
            if request.query_params.get(campo):
                qs = qs.filter(**{campo: request.query_params[campo]})
        return Response([_documento(x) for x in qs[:MAX_LISTA]])


class DocumentoXmlView(_Base):
    def get(self, request, slug, pk):
        x = DocumentoEmitido.objects.filter(organization=request.empresa, pk=pk).first()
        if x is None:
            return Response({'detail': 'No existe.'}, status=status.HTTP_404_NOT_FOUND)
        r = HttpResponse(x.xml.encode('iso-8859-1'), content_type='application/xml; charset=ISO-8859-1')
        r['Content-Disposition'] = f'attachment; filename="DTE_{ruts.normalizar(request.empresa.rut)}_T{x.tipo}F{x.folio}.xml"'
        return r


class NotaView(_Base):
    """Nota de crédito o débito sobre un documento emitido: {tipo: 61|56, codigo: 1|2|3, razon,
    lineas: [{nombre, cantidad, precio}] (solo para corregir montos)}."""
    rol_escritura = IsEditor

    def post(self, request, slug, pk):
        from .comercial import registrar_nota
        original = DocumentoEmitido.objects.filter(organization=request.empresa, pk=pk).first()
        if original is None:
            return Response({'detail': 'No existe.'}, status=status.HTTP_404_NOT_FOUND)
        d = request.data
        try:
            tipo, codigo = int(d.get('tipo') or 61), int(d.get('codigo') or 0)
        except (TypeError, ValueError):
            raise ErrorDTE('Tipo o código de nota no válido.')
        nota = servicio.emitir_nota(request.empresa, original, tipo, codigo, d.get('razon'), d.get('lineas'),
                                    usuario=request.user)
        registrar_nota(nota, original, request.user)
        return Response(_documento(nota), status=status.HTTP_201_CREATED)


class EnvioView(_Base):
    def get(self, request, slug, pk):
        e = EnvioSII.objects.filter(organization=request.empresa, pk=pk).first()
        if e is None:
            return Response({'detail': 'No existe.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(_envio(e))


class ReintentarView(_Base):
    """Vuelve a subir o a consultar ahora un envío que no ha terminado."""
    rol_escritura = IsEditor

    def post(self, request, slug, pk):
        e = EnvioSII.objects.filter(organization=request.empresa, pk=pk).first()
        if e is None:
            return Response({'detail': 'No existe.'}, status=status.HTTP_404_NOT_FOUND)
        if e.final:
            raise ErrorDTE('Ese envío ya terminó: no hay nada que reintentar.')
        if e.estado == EnvioSII.POR_SUBIR:
            motor.subir(e)
        else:
            motor.consultar(e)
        e.refresh_from_db()
        return Response(_envio(e))

"""El intercambio en la API: los documentos que llegan de proveedores, su aceptación o reclamo, la
casilla de intercambio y el reenvío de lo emitido al cliente.

Ver es de cualquier miembro; recibir, aceptar, reclamar y reenviar es de editor para arriba; la
casilla (lleva una clave) es del administrador.
"""
import email.utils
import hmac

from django.conf import settings
from django.core.exceptions import RequestDataTooBig
from django.http import HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.response import Response

from apps.workspaces.permissions import IsAdmin, IsEditor

from . import intercambio, sii
from .models import ConfiguracionDTE, DocumentoEmitido, DocumentoRecibido
from .nucleo import ErrorDTE
from .nucleo.documento import TIPOS
from .views import _Base

MAX_ARCHIVO = 5 * 1024 * 1024
MAX_LISTA = 200


def _recibido(x):
    return {'id': x.id, 'tipo': x.tipo, 'nombre': TIPOS.get(x.tipo, f'Documento {x.tipo}'), 'folio': x.folio,
            'fecha': x.fecha, 'emisor_rut': x.emisor_rut, 'emisor_razon_social': x.emisor_razon_social,
            'monto_neto': x.monto_neto, 'monto_exento': x.monto_exento, 'monto_iva': x.monto_iva,
            'monto_total': x.monto_total, 'origen': x.origen, 'correo_de': x.correo_de,
            'esquema_ok': x.esquema_ok, 'firma_ok': x.firma_ok, 'timbre_ok': x.timbre_ok,
            'observaciones': x.observaciones, 'estado': x.estado, 'estado_nombre': x.get_estado_display(),
            'respuesta_sii': x.respuesta_sii, 'acuse_enviado_en': x.acuse_enviado_en,
            'documento_tributario': x.documento_tributario_id, 'recibido_en': x.recibido_en}


def _casilla(cfg):
    return {'imap_servidor': cfg.imap_servidor, 'imap_puerto': cfg.imap_puerto, 'imap_usuario': cfg.imap_usuario,
            'tiene_clave': bool(cfg._imap_clave), 'imap_revisado_en': cfg.imap_revisado_en,
            'imap_error': cfg.imap_error, 'enviar_a_clientes': cfg.enviar_a_clientes,
            'correo_intercambio': cfg.correo_intercambio,
            'casilla_afable': cfg.casilla_afable, 'direccion_afable': intercambio.direccion_afable(cfg.organization),
            'casilla_afable_disponible': bool(intercambio.dominio_casilla())}


def _obtener(request, pk):
    x = DocumentoRecibido.objects.filter(organization=request.empresa, pk=pk).first()
    if x is None:
        raise ErrorDTE('Ese documento no existe.')
    return x


class RecibidosView(_Base):
    def get(self, request, slug):
        qs = DocumentoRecibido.objects.filter(organization=request.empresa)
        for campo in ('estado', 'tipo', 'emisor_rut'):
            if request.query_params.get(campo):
                qs = qs.filter(**{campo: request.query_params[campo]})
        return Response([_recibido(x) for x in qs[:MAX_LISTA]])


class SubirRecibidoView(_Base):
    """Un EnvioDTE que el proveedor mandó por otro lado: se sube a mano."""
    rol_escritura = IsEditor

    def post(self, request, slug):
        archivo = request.FILES.get('archivo')
        if not archivo:
            raise ErrorDTE('Adjunte el XML que le mandó el proveedor.')
        if archivo.size > MAX_ARCHIVO:
            raise ErrorDTE('El archivo es demasiado grande.')
        r = intercambio.recibir(request.empresa, archivo.read(), DocumentoRecibido.MANUAL,
                                nombre_archivo=archivo.name[:80])
        return Response({'recibidos': [_recibido(x) for x in r['recibidos']], 'estado_envio': r['estado_envio'],
                         'glosa': r['glosa'], 'ignorados': r['ignorados'], 'acuse': bool(r['acuse'])},
                        status=status.HTTP_201_CREATED)


class RecibidoView(_Base):
    def get(self, request, slug, pk):
        return Response(_recibido(_obtener(request, pk)))


class AceptarRecibidoView(_Base):
    rol_escritura = IsEditor

    def post(self, request, slug, pk):
        x = _obtener(request, pk)
        intercambio.aceptar(x, request.user, recibo_mercaderias=bool(request.data.get('recibo_mercaderias', True)),
                            recinto=str(request.data.get('recinto') or 'Oficina')[:80])
        return Response(_recibido(x))


class ReclamarRecibidoView(_Base):
    rol_escritura = IsEditor

    def post(self, request, slug, pk):
        x = _obtener(request, pk)
        intercambio.reclamar(x, request.data.get('motivo', ''), request.user,
                             accion=request.data.get('accion') or sii.RECLAMA_CONTENIDO)
        return Response(_recibido(x))


class RecibidoXmlView(_Base):
    def get(self, request, slug, pk):
        x = _obtener(request, pk)
        r = HttpResponse(x.xml.encode('iso-8859-1'), content_type='application/xml; charset=ISO-8859-1')
        r['Content-Disposition'] = f'attachment; filename="DTE_{x.emisor_rut}_T{x.tipo}F{x.folio}.xml"'
        return r


class CasillaView(_Base):
    rol_escritura = IsAdmin

    def get(self, request, slug):
        return Response(_casilla(ConfiguracionDTE.de(request.empresa)))

    def put(self, request, slug):
        cfg = ConfiguracionDTE.de(request.empresa)
        d = request.data
        for campo, largo in (('imap_servidor', 120), ('imap_usuario', 120), ('correo_intercambio', 120)):
            if campo in d:
                setattr(cfg, campo, str(d[campo] or '').strip()[:largo])
        if 'imap_puerto' in d:
            puerto = str(d['imap_puerto'] or '993').strip()
            if not puerto.isdigit() or not 0 < int(puerto) < 65536:
                raise ErrorDTE('El puerto IMAP es un número (normalmente 993).')
            cfg.imap_puerto = int(puerto)
        if 'clave' in d and d['clave'] is not None:
            cfg.guardar_clave_imap(str(d['clave']))
        if 'enviar_a_clientes' in d:
            cfg.enviar_a_clientes = bool(d['enviar_a_clientes'])
        if 'casilla_afable' in d:
            direccion = intercambio.direccion_afable(request.empresa)
            if d['casilla_afable']:
                if not intercambio.dominio_casilla():
                    raise ErrorDTE('La casilla de Afable todavía no está disponible.')
                if not direccion:
                    raise ErrorDTE('Para usar la casilla de Afable la empresa necesita un RUT válido.')
                cfg.casilla_afable, cfg.correo_intercambio = True, direccion
            else:
                cfg.casilla_afable = False
                if direccion and cfg.correo_intercambio == direccion:
                    cfg.correo_intercambio = ''
        cfg.save()
        return Response(_casilla(cfg))


class ProbarCasillaView(_Base):
    rol_escritura = IsAdmin

    def post(self, request, slug):
        cfg = ConfiguracionDTE.de(request.empresa)
        intercambio.probar_casilla(cfg)
        return Response({'ok': True, **_casilla(cfg)})


class RevisarCasillaView(_Base):
    """Revisa la casilla ahora, sin esperar los 15 minutos."""
    rol_escritura = IsEditor

    def post(self, request, slug):
        n = intercambio.revisar_casilla(request.empresa)
        return Response({'recibidos': n, **_casilla(ConfiguracionDTE.de(request.empresa))})


class EnviarAClienteView(_Base):
    """Reenvía al cliente el XML y el PDF de un documento emitido (a su correo o a otro)."""
    rol_escritura = IsEditor

    def post(self, request, slug, pk):
        x = DocumentoEmitido.objects.filter(organization=request.empresa, pk=pk).first()
        if x is None:
            raise ErrorDTE('Ese documento no existe.')
        if x.estado == DocumentoEmitido.RECHAZADO:
            raise ErrorDTE('El SII rechazó ese documento: no corresponde mandarlo al cliente.')
        para = intercambio.enviar_a_cliente(x, forzar=True, correo=(request.data.get('correo') or '').strip() or None)
        if not para:
            raise ErrorDTE('El cliente no tiene correo en su ficha. Indique a qué correo mandarlo.')
        return Response({'enviado_a': para})


# ── La casilla de Afable: el correo entrante ──────────────────────────────────────────────

MAX_CORREO = 15 * 1024 * 1024
CAMPOS_MIME = ('email', 'message', 'body-mime', 'raw', 'mime')


def _destinatarios_del_sobre(post):
    """Los destinatarios que informa el proveedor fuera del correo (to, recipient, envelope)."""
    import json
    salida = []
    for campo in ('to', 'recipient', 'recipients'):
        if post.get(campo):
            salida += [d for _, d in email.utils.getaddresses([post.get(campo)])]
    if post.get('envelope'):  # SendGrid: {"to": [...], "from": "..."}
        try:
            salida += list(json.loads(post['envelope']).get('to') or [])
        except (ValueError, AttributeError):
            pass
    return salida


@method_decorator(csrf_exempt, name='dispatch')
class CorreoEntranteView(View):
    """POST /api/v1/dte/correo-entrante/<secreto>/: lo llama el proveedor de correo entrante con
    cada correo que llega a una casilla dte-...@DTE_CORREO_DOMINIO. Acepta el MIME crudo en el
    cuerpo o en un campo de un formulario (email, message, body-mime, raw). Responde 200 aunque el
    correo no traiga nada útil, para que el proveedor no lo reintente sin fin."""

    def post(self, request, secreto):
        if not intercambio.dominio_casilla():
            return JsonResponse({'detail': 'La casilla de Afable no está habilitada.'}, status=404)
        esperado = getattr(settings, 'DTE_CORREO_SECRETO', '') or ''
        if not esperado or not hmac.compare_digest(str(secreto).encode(), esperado.encode()):
            return JsonResponse({'detail': 'No autorizado.'}, status=403)
        try:
            if request.content_type.startswith('multipart/') or request.content_type == 'application/x-www-form-urlencoded':
                crudo = b''
                for campo in CAMPOS_MIME:
                    if campo in request.FILES:
                        crudo = request.FILES[campo].read(MAX_CORREO + 1)
                        break
                    if request.POST.get(campo):
                        crudo = request.POST[campo].encode('utf-8', 'surrogateescape')
                        break
                sobre = _destinatarios_del_sobre(request.POST)
            else:
                crudo, sobre = request.read(MAX_CORREO + 1), []
        except RequestDataTooBig:
            return JsonResponse({'detail': 'Correo demasiado grande.'}, status=413)
        if len(crudo) > MAX_CORREO:
            return JsonResponse({'detail': 'Correo demasiado grande.'}, status=413)
        if not crudo:
            return JsonResponse({'recibidos': 0, 'ignorados': ['no llegó el correo (MIME)']})
        return JsonResponse(intercambio.recibir_correo(crudo, sobre))

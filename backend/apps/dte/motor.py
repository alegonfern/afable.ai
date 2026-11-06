"""El motor: sube al SII los envíos pendientes y consulta su resultado, empresa por empresa.

Corre en el corredor de automatizaciones (run_automations, cada 30 s) y justo después de emitir.
Una falla de una empresa no frena a las demás. Al SII se le consulta con espera creciente: no
permite uso masivo (ESPEC_SII.md §3.1).
"""
import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from . import sii
from .models import DocumentoEmitido, EnvioSII
from .nucleo import ErrorDTE

logger = logging.getLogger(__name__)

# Espera antes de cada consulta de estado (o reintento de subida), según los intentos hechos.
ESPERAS = [60, 120, 300, 600, 1800, 3600]
# STATUS del upload que no se arreglan reintentando: el archivo está mal (esquema o firma).
STATUS_DEFINITIVOS = {7, 8}
# STATUS que necesitan que la empresa haga algo en el SII (permisos): se reintenta cada hora.
STATUS_DE_PERMISOS = {1, 6}
POR_LOTE = 50


def _espera(intentos):
    return timedelta(seconds=ESPERAS[min(intentos, len(ESPERAS) - 1)])


def cliente(org, ambiente):
    from .servicio import certificado_activo
    cert = certificado_activo(org)
    if cert is None:
        raise ErrorDTE('La empresa no tiene un certificado digital activo.')
    return sii.ClienteSII(cert.cargar(), ambiente)


def _avisar_rechazo(envio, motivo):
    """Aviso en la campana a quien emitió y a los administradores."""
    try:
        from apps.notificaciones.avisos import avisar
        from apps.notificaciones.models import TIPO_AGENTE
        from apps.workspaces.models import ROLE_ADMIN
        org = envio.organization
        destinatarios = {d.emitido_por for d in envio.documentos.all() if d.emitido_por}
        destinatarios |= {m.user for m in org.memberships.filter(role=ROLE_ADMIN).select_related('user')}
        docs = ', '.join(f'{d.tipo}-{d.folio}' for d in envio.documentos.all())
        avisar(destinatarios, tipo=TIPO_AGENTE, organization=org, titulo=f'El SII rechazó {docs}',
               detalle=motivo[:300], enlace='/app/ajustes/facturacion-electronica')
    except Exception:
        logger.exception('dte: no se pudo avisar el rechazo del envío %s', envio.id)


def _rechazar(envio, motivo):
    """El SII no aceptó el envío: los documentos quedan rechazados y salen del Libro de Ventas
    (su orden de venta vuelve a quedar por facturar). El folio queda gastado, como manda el SII."""
    envio.estado = EnvioSII.RECHAZADO
    envio.error = motivo
    envio.siguiente_intento = None
    envio.save()
    for d in envio.documentos.all():
        d.estado, d.detalle_estado = DocumentoEmitido.RECHAZADO, motivo[:500]
        d.save(update_fields=['estado', 'detalle_estado'])
        if d.documento_tributario_id:
            d.documento_tributario.delete()  # arrastra su vínculo con la orden (PedidoFactura)
    _avisar_rechazo(envio, motivo)


def subir(envio, cli=None):
    """Sube un envío por subir. Deja el trackid y programa la primera consulta."""
    cli = cli or cliente(envio.organization, envio.ambiente)
    envio.intentos += 1
    try:
        r = cli.enviar(envio.xml.encode('iso-8859-1'), envio.organization.rut, nombre=f'EnvioDTE_{envio.id}.xml')
    except sii.ErrorSII as e:
        envio.respuesta = (e.detalle or '')[:20000]
        if e.codigo in STATUS_DEFINITIVOS:
            envio.save()
            _rechazar(envio, str(e))
            return envio
        envio.error = str(e)
        envio.siguiente_intento = timezone.now() + (timedelta(hours=1) if e.codigo in STATUS_DE_PERMISOS
                                                    else _espera(envio.intentos))
        envio.save()
        return envio
    envio.estado, envio.trackid, envio.error = EnvioSII.SUBIDO, r.trackid, ''
    envio.respuesta = r.xml[:20000]
    envio.intentos = 0
    envio.siguiente_intento = timezone.now() + _espera(0)
    envio.save()
    envio.documentos.update(estado=DocumentoEmitido.ENVIADO)
    return envio


def consultar(envio, cli=None):
    """Pregunta al SII cómo va un envío subido y, si ya terminó, deja el resultado en él y en
    cada documento."""
    cli = cli or cliente(envio.organization, envio.ambiente)
    r = cli.estado_envio(envio.organization.rut, envio.trackid)
    envio.estado_sii, envio.glosa, envio.resumen = r.estado, r.descripcion[:500], r.resumen
    envio.respuesta = r.xml[:20000]
    envio.intentos += 1
    if not r.final:
        envio.siguiente_intento = timezone.now() + _espera(envio.intentos)
        envio.save()
        return envio
    if r.estado in sii.ENVIO_RECHAZADO:
        envio.save()
        _rechazar(envio, f'{r.descripcion} ({r.estado}). Revise el detalle del envío.')
        return envio
    rechazados = sum(x['rechazados'] for x in r.resumen)
    reparos = sum(x['reparos'] for x in r.resumen) or (r.estado in ('RPR', 'RLV'))
    documentos = list(envio.documentos.all())
    if rechazados and rechazados >= len(documentos):
        envio.save()
        _rechazar(envio, 'El SII rechazó el documento. Revise el correo de resultado del SII.')
        return envio
    if rechazados:
        # Envío con varios documentos y algunos rechazados: se pregunta por cada uno.
        for d in documentos:
            est = cli.estado_dte(envio.organization.rut, d.receptor_rut, d.tipo, d.folio, d.fecha, d.monto_total)
            ok = est['estado'] == 'DOK'
            d.estado = DocumentoEmitido.ACEPTADO if ok else DocumentoEmitido.RECHAZADO
            d.detalle_estado = est.get('descripcion') or est.get('glosa', '')
            d.save(update_fields=['estado', 'detalle_estado'])
            if not ok and d.documento_tributario_id:
                d.documento_tributario.delete()
        envio.estado = EnvioSII.REPAROS
    else:
        envio.estado = EnvioSII.REPAROS if reparos else EnvioSII.ACEPTADO
        envio.documentos.update(estado=DocumentoEmitido.REPAROS if reparos else DocumentoEmitido.ACEPTADO,
                                detalle_estado=r.descripcion[:500])
    envio.siguiente_intento = None
    envio.save()
    _mandar_a_clientes(envio)
    return envio


def _mandar_a_clientes(envio):
    """Lo aceptado por el SII, a cada cliente (intercambio.py). Nunca voltea el motor."""
    if getattr(envio, 'proposito', EnvioSII.EMISION) != EnvioSII.EMISION:
        return
    from . import intercambio
    for d in envio.documentos.filter(estado__in=[DocumentoEmitido.ACEPTADO, DocumentoEmitido.REPAROS]):
        try:
            intercambio.enviar_a_cliente(d)
        except Exception:
            logger.exception('dte: no se pudo mandar %s al cliente', d)


def subir_sin_fallar(envio_id):
    """Después de emitir: intenta subir enseguida. Si el SII no responde, queda para el motor."""
    try:
        envio = EnvioSII.objects.select_related('organization').get(pk=envio_id)
        if envio.estado == EnvioSII.POR_SUBIR:
            subir(envio)
    except Exception:
        logger.exception('dte: no se pudo subir el envío %s; queda para el motor', envio_id)


def procesar(ahora=None):
    """Una pasada: sube lo pendiente y consulta lo subido que ya toca. Devuelve cuántos movió."""
    ahora = ahora or timezone.now()
    pendientes = (EnvioSII.objects.select_related('organization')
                  .filter(estado__in=[EnvioSII.POR_SUBIR, EnvioSII.SUBIDO], siguiente_intento__lte=ahora)
                  .order_by('siguiente_intento')[:POR_LOTE])
    clientes, movidos = {}, 0
    for envio in pendientes:
        clave = (envio.organization_id, envio.ambiente)
        try:
            if clave not in clientes:
                clientes[clave] = cliente(envio.organization, envio.ambiente)
            with transaction.atomic():
                if envio.estado == EnvioSII.POR_SUBIR:
                    subir(envio, clientes[clave])
                else:
                    consultar(envio, clientes[clave])
            movidos += 1
        except Exception as e:
            logger.exception('dte: falló el envío %s', envio.id)
            EnvioSII.objects.filter(pk=envio.id).update(
                error=str(e)[:2000], intentos=envio.intentos + 1,
                siguiente_intento=ahora + _espera(envio.intentos + 1))
    return movidos

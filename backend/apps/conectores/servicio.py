"""Lo común de todos los conectores: el registro de tipos, correr una sincronización dejando su
historial, y la pasada programada del corredor de automatizaciones."""
import logging

from django.utils import timezone

from .models import Conexion, Sincronizacion

logger = logging.getLogger(__name__)


class ErrorConector(Exception):
    """Un problema que se le explica a la persona (credencial mala, servicio caído…)."""


def modulo(tipo):
    """El módulo que implementa un tipo: probar(conexion), sincronizar(conexion, opciones, usuario)
    y toca_correr(conexion, ahora) para los que corren solos."""
    if tipo == Conexion.HUBSPOT:
        from . import hubspot
        return hubspot
    if tipo == Conexion.SII_RCV:
        from . import sii_rcv
        return sii_rcv
    raise ErrorConector(f'Conector desconocido: {tipo}.')


def de(org, tipo, crear=False):
    if crear:
        return Conexion.objects.get_or_create(organization=org, tipo=tipo)[0]
    return Conexion.objects.filter(organization=org, tipo=tipo).first()


def sincronizar(conexion, opciones=None, usuario=None, automatica=False):
    """Corre el conector y deja la corrida en el historial. Lanza ErrorConector si falla (después
    de anotarlo)."""
    s = Sincronizacion.objects.create(conexion=conexion, automatica=automatica, usuario=usuario)
    try:
        resumen = modulo(conexion.tipo).sincronizar(conexion, opciones or {}, usuario)
    except ErrorConector as e:
        s.estado, s.error, s.fin = Sincronizacion.ERROR, str(e), timezone.now()
        s.save()
        conexion.ultimo_error = str(e)
        conexion.ultima_sincronizacion = s.fin
        conexion.save(update_fields=['ultimo_error', 'ultima_sincronizacion', 'actualizado_en'])
        raise
    s.resumen, s.fin = resumen, timezone.now()
    s.save()
    conexion.ultimo_resultado, conexion.ultimo_error, conexion.ultima_sincronizacion = resumen, '', s.fin
    conexion.save(update_fields=['ultimo_resultado', 'ultimo_error', 'ultima_sincronizacion', 'actualizado_en'])
    return resumen


def procesar_programadas(ahora=None):
    """Una pasada del corredor: cada conector activo que corre solo y al que le toca. Una falla de
    una empresa no frena a las demás. Devuelve cuántos corrió."""
    ahora = ahora or timezone.now()
    corridos = 0
    for c in Conexion.objects.filter(activa=True).select_related('organization'):
        try:
            m = modulo(c.tipo)
            if not c.config.get('automatico') or not hasattr(m, 'toca_correr') or not m.toca_correr(c, ahora):
                continue
            sincronizar(c, automatica=True)
            corridos += 1
        except ErrorConector:
            pass  # ya quedó en el historial y en ultimo_error
        except Exception:
            logger.exception('conectores: falló %s de la empresa %s', c.tipo, c.organization_id)
    return corridos

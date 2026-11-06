import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


def _vincular_al_importar(sender, carga, documentos, **kwargs):
    """Las facturas recién importadas que cuadran con un solo pedido se amarran solas. Nunca
    voltea la importación: si algo falla, queda para hacerlo a mano."""
    from django.db import transaction
    from .facturacion import vincular_automatico
    try:
        with transaction.atomic():          # punto de guardado: un error no arrastra la carga
            vincular_automatico(documentos)
    except Exception:
        logger.exception('comercial: no se pudieron vincular las facturas de la carga %s', carga.id)


class ComercialConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.comercial'
    verbose_name = 'Compras y Ventas'

    def ready(self):
        # Sus automatizaciones se suman al catálogo de las de los módulos.
        from apps.finanzas import automatizaciones
        from apps.finanzas.senales import carga_importada
        from . import automatizaciones as propias
        automatizaciones.registrar(propias.CATALOGO, propias.FUNCIONES)
        carga_importada.connect(_vincular_al_importar, dispatch_uid='comercial_vincular_al_importar')

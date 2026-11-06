from django.apps import AppConfig


class DteConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.dte'
    verbose_name = 'Facturación electrónica'

    def ready(self):
        # Ventas emite con este facturador cuando la empresa lo activa (comercial/emision.py).
        from apps.comercial import emision
        from .comercial import FacturadorSII
        emision.PROVEEDORES[FacturadorSII.clave] = FacturadorSII

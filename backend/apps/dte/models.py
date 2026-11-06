"""El facturador electrónico de cada empresa (26-10-2026): su configuración, su certificado, sus
folios y los documentos que emite, con cada envío al SII.

Todo es por empresa (multiempresa) y por ambiente: lo de certificación (maullin) no se mezcla con
producción (palena). El certificado y los CAF llevan llaves privadas: se guardan cifrados.
"""
import base64

from django.conf import settings
from django.db import models

from services.encryption import decrypt, encrypt

from .sii import CERTIFICACION, PRODUCCION

AMBIENTES = [(CERTIFICACION, 'Certificación (pruebas del SII)'), (PRODUCCION, 'Producción')]


class ConfiguracionDTE(models.Model):
    """Cómo factura electrónicamente la empresa. Los datos del emisor que ya pide Ventas (razón
    social, giro, dirección, comuna) siguen en ConfiguracionComercial: no se piden dos veces."""

    YA_EMISOR, CERTIFICAR = 'ya_emisor', 'certificar'
    CAMINOS = [(YA_EMISOR, 'Ya emite facturas electrónicas con otro sistema'),
               (CERTIFICAR, 'Debe certificarse ante el SII')]

    organization = models.OneToOneField('organizations.Organization', on_delete=models.CASCADE,
                                        related_name='configuracion_dte')
    camino = models.CharField(max_length=12, choices=CAMINOS, blank=True)
    # Dónde emite: vacío mientras se configura; certificación para las pruebas; producción para facturar.
    ambiente = models.CharField(max_length=14, choices=AMBIENTES, blank=True)
    # Encendido: Ventas emite con este facturador (comercial/emision.py, proveedor 'sii').
    activo = models.BooleanField(default=False)
    actecos = models.JSONField(default=list, blank=True)  # códigos de actividad económica (1 a 4)
    telefono = models.CharField(max_length=20, blank=True)
    correo_emisor = models.CharField(max_length=80, blank=True)
    sucursal = models.CharField(max_length=20, blank=True)
    codigo_sucursal = models.CharField(max_length=9, blank=True)  # CdgSIISucur
    # La autorización del SII en producción (número y fecha de la resolución).
    resolucion_numero = models.PositiveIntegerField(null=True, blank=True)
    resolucion_fecha = models.DateField(null=True, blank=True)
    # En certificación el número es 0 y la fecha la publica el SII en "datos de su empresa" (maullin).
    certificacion_fecha = models.DateField(null=True, blank=True)
    # La casilla que la empresa declara en el SII para recibir y mandar XML (intercambio).
    correo_intercambio = models.CharField(max_length=120, blank=True)
    # La oficina del SII que va bajo el recuadro rojo de cada documento ("S.I.I. - SANTIAGO ORIENTE").
    # Vacía: la comuna del emisor.
    oficina_sii = models.CharField(max_length=60, blank=True)
    # Usar la casilla de intercambio que da Afable (dte-<rut>@<DTE_CORREO_DOMINIO>) en vez de la propia.
    casilla_afable = models.BooleanField(default=False)
    # Mandarle a cada cliente el XML y el PDF de lo que se le emite, cuando el SII lo acepta.
    enviar_a_clientes = models.BooleanField(default=True)
    # La casilla de intercambio, si la empresa usa la suya: Afable la revisa por IMAP.
    imap_servidor = models.CharField(max_length=120, blank=True)
    imap_puerto = models.PositiveIntegerField(default=993)
    imap_usuario = models.CharField(max_length=120, blank=True)
    _imap_clave = models.TextField(db_column='imap_clave_cifrada', blank=True)
    imap_revisado_en = models.DateTimeField(null=True, blank=True)
    imap_error = models.CharField(max_length=500, blank=True)
    activado_en = models.DateTimeField(null=True, blank=True)
    activado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name='+')
    actualizado_en = models.DateTimeField(auto_now=True)

    @classmethod
    def de(cls, organization):
        cfg, _ = cls.objects.get_or_create(organization=organization)
        return cfg

    def guardar_clave_imap(self, clave):
        self._imap_clave = encrypt(clave) if clave else ''

    @property
    def clave_imap(self):
        return decrypt(self._imap_clave) if self._imap_clave else ''

    def resolucion(self, ambiente=None):
        """(fecha, número) que van en la carátula de cada envío."""
        if (ambiente or self.ambiente) == CERTIFICACION:
            return self.certificacion_fecha, 0
        return self.resolucion_fecha, self.resolucion_numero


class CertificadoDigital(models.Model):
    """El .pfx de la persona que firma por la empresa. Uno activo a la vez."""

    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE,
                                     related_name='certificados_dte')
    titular_nombre = models.CharField(max_length=200)
    titular_rut = models.CharField(max_length=12)
    emitido_por = models.CharField(max_length=200, blank=True)
    valido_desde = models.DateTimeField()
    valido_hasta = models.DateTimeField()
    huella = models.CharField(max_length=64)  # SHA-256 del certificado, para reconocer el mismo archivo
    _pfx = models.TextField(db_column='pfx_cifrado')
    _clave = models.TextField(db_column='clave_cifrada')
    activo = models.BooleanField(default=True)
    subido_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name='+')
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado_en']

    def guardar_secretos(self, pfx, clave):
        self._pfx = encrypt(base64.b64encode(pfx).decode())
        self._clave = encrypt(clave or '')

    def cargar(self):
        """El certificado listo para firmar (nucleo.certificado.Certificado)."""
        from .nucleo.certificado import Certificado
        return Certificado.desde_pfx(base64.b64decode(decrypt(self._pfx)), decrypt(self._clave))


class Caf(models.Model):
    """Un archivo de folios autorizados por el SII para un tipo de documento."""

    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE,
                                     related_name='cafs')
    ambiente = models.CharField(max_length=14, choices=AMBIENTES)
    tipo = models.PositiveSmallIntegerField()
    desde = models.PositiveIntegerField()
    hasta = models.PositiveIntegerField()
    # El próximo folio por usar. Pasado `hasta`, el CAF está agotado.
    siguiente = models.PositiveIntegerField()
    fecha_autorizacion = models.DateField()
    _xml = models.TextField(db_column='xml_cifrado')  # trae la llave privada del timbre
    subido_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name='+')
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['tipo', 'desde']
        constraints = [models.UniqueConstraint(fields=['organization', 'ambiente', 'tipo', 'desde'],
                                               name='caf_unico')]

    @property
    def disponibles(self):
        return max(self.hasta - self.siguiente + 1, 0)

    @property
    def agotado(self):
        return self.siguiente > self.hasta

    def guardar_xml(self, xml):
        self._xml = encrypt(xml.decode('iso-8859-1'))

    def cargar(self):
        from .nucleo.caf import Caf as CafNucleo
        return CafNucleo(decrypt(self._xml).encode('iso-8859-1'))


class EnvioSII(models.Model):
    """Un EnvioDTE subido (o por subir) al SII y lo que el SII respondió."""

    POR_SUBIR, SUBIDO, ACEPTADO, REPAROS, RECHAZADO = 'por_subir', 'subido', 'aceptado', 'reparos', 'rechazado'
    ESTADOS = [(POR_SUBIR, 'Por subir'), (SUBIDO, 'En revisión del SII'), (ACEPTADO, 'Aceptado'),
               (REPAROS, 'Aceptado con reparos'), (RECHAZADO, 'Rechazado')]
    FINALES = (ACEPTADO, REPAROS, RECHAZADO)
    # Qué se subió: lo emitido día a día, o las piezas del proceso de certificación.
    EMISION, SET_PRUEBAS, SIMULACION, LIBRO_VENTAS, LIBRO_COMPRAS, LIBRO_GUIAS = (
        'emision', 'set_pruebas', 'simulacion', 'libro_ventas', 'libro_compras', 'libro_guias')
    PROPOSITOS = [(EMISION, 'Emisión'), (SET_PRUEBAS, 'Set de pruebas'), (SIMULACION, 'Simulación'),
                  (LIBRO_VENTAS, 'Libro de ventas'), (LIBRO_COMPRAS, 'Libro de compras'), (LIBRO_GUIAS, 'Libro de guías')]

    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE,
                                     related_name='envios_sii')
    ambiente = models.CharField(max_length=14, choices=AMBIENTES)
    proposito = models.CharField(max_length=14, choices=PROPOSITOS, default=EMISION)
    descripcion = models.CharField(max_length=200, blank=True)
    estado = models.CharField(max_length=10, choices=ESTADOS, default=POR_SUBIR)
    trackid = models.CharField(max_length=30, blank=True)
    estado_sii = models.CharField(max_length=10, blank=True)  # EPR, RSC, SOK...
    glosa = models.CharField(max_length=500, blank=True)
    resumen = models.JSONField(default=list, blank=True)
    error = models.TextField(blank=True)
    intentos = models.PositiveSmallIntegerField(default=0)
    siguiente_intento = models.DateTimeField(null=True, blank=True)
    xml = models.TextField()  # el EnvioDTE firmado (ISO-8859-1)
    respuesta = models.TextField(blank=True)  # lo último que respondió el SII, para revisar
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-creado_en']
        indexes = [models.Index(fields=['estado', 'siguiente_intento'])]

    @property
    def final(self):
        return self.estado in self.FINALES


class DocumentoEmitido(models.Model):
    """Un DTE emitido por el facturador nativo: el XML firmado y su estado en el SII."""

    POR_ENVIAR, ENVIADO, ACEPTADO, REPAROS, RECHAZADO = 'por_enviar', 'enviado', 'aceptado', 'reparos', 'rechazado'
    ESTADOS = [(POR_ENVIAR, 'Por enviar'), (ENVIADO, 'Enviado al SII'), (ACEPTADO, 'Aceptado por el SII'),
               (REPAROS, 'Aceptado con reparos'), (RECHAZADO, 'Rechazado por el SII')]

    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE,
                                     related_name='documentos_emitidos')
    ambiente = models.CharField(max_length=14, choices=AMBIENTES)
    tipo = models.PositiveSmallIntegerField()
    folio = models.PositiveIntegerField()
    fecha = models.DateField()
    receptor_rut = models.CharField(max_length=12)
    receptor_razon_social = models.CharField(max_length=255)
    monto_neto = models.BigIntegerField(default=0)
    monto_exento = models.BigIntegerField(default=0)
    monto_iva = models.BigIntegerField(default=0)
    monto_total = models.BigIntegerField(default=0)
    estado = models.CharField(max_length=10, choices=ESTADOS, default=POR_ENVIAR)
    detalle_estado = models.CharField(max_length=500, blank=True)
    xml = models.TextField()  # el <DTE> firmado, suelto (ISO-8859-1)
    envio = models.ForeignKey(EnvioSII, null=True, blank=True, on_delete=models.SET_NULL, related_name='documentos')
    # Su registro en el Libro de Ventas de Finanzas (y por ahí, su orden de venta).
    documento_tributario = models.OneToOneField('finanzas.DocumentoTributario', null=True, blank=True,
                                                on_delete=models.SET_NULL, related_name='emitido')
    emitido_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name='+')
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado_en']
        constraints = [models.UniqueConstraint(fields=['organization', 'ambiente', 'tipo', 'folio'],
                                               name='documento_emitido_unico')]

    def __str__(self):
        return f'{self.tipo}-{self.folio}'


class DocumentoRecibido(models.Model):
    """Un DTE que un proveedor le mandó a la empresa (intercambio): llegó por correo o se subió a
    mano. Se revisa (esquema, firma, timbre), se acusa recibo y se acepta o reclama."""

    RECIBIDO, ACEPTADO, RECLAMADO = 'recibido', 'aceptado', 'reclamado'
    ESTADOS = [(RECIBIDO, 'Recibido'), (ACEPTADO, 'Aceptado'), (RECLAMADO, 'Reclamado')]
    CORREO, MANUAL = 'correo', 'manual'

    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE,
                                     related_name='documentos_recibidos')
    tipo = models.PositiveSmallIntegerField()
    folio = models.PositiveIntegerField()
    fecha = models.DateField()
    emisor_rut = models.CharField(max_length=12)
    emisor_razon_social = models.CharField(max_length=255)
    monto_neto = models.BigIntegerField(default=0)
    monto_exento = models.BigIntegerField(default=0)
    monto_iva = models.BigIntegerField(default=0)
    monto_total = models.BigIntegerField(default=0)
    xml = models.TextField()  # el <DTE> tal como llegó, suelto
    origen = models.CharField(max_length=8, default=MANUAL)
    correo_de = models.CharField(max_length=200, blank=True)
    # La revisión al recibirlo: si algo falla, el documento se acusa con reparos o se rechaza.
    esquema_ok = models.BooleanField(default=False)
    firma_ok = models.BooleanField(default=False)
    timbre_ok = models.BooleanField(default=False)
    observaciones = models.TextField(blank=True)
    estado = models.CharField(max_length=10, choices=ESTADOS, default=RECIBIDO)
    # Lo que dijo el SII al registrar la aceptación o el reclamo (Ley 20.956).
    respuesta_sii = models.CharField(max_length=300, blank=True)
    acuse_enviado_en = models.DateTimeField(null=True, blank=True)
    documento_tributario = models.OneToOneField('finanzas.DocumentoTributario', null=True, blank=True,
                                                on_delete=models.SET_NULL, related_name='recibido')
    recibido_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recibido_en']
        constraints = [models.UniqueConstraint(fields=['organization', 'emisor_rut', 'tipo', 'folio'],
                                               name='documento_recibido_unico')]


class ProcesoCertificacion(models.Model):
    """El avance de la empresa en la certificación del SII (ESPEC_SII.md §9), con lo que Afable
    generó en cada paso. Uno por empresa."""

    SET_PRUEBAS, SIMULACION, INTERCAMBIO, MUESTRAS, DECLARACION, TERMINADO = (
        'set_pruebas', 'simulacion', 'intercambio', 'muestras', 'declaracion', 'terminado')
    PASOS = [(SET_PRUEBAS, 'Set de pruebas'), (SIMULACION, 'Simulación'), (INTERCAMBIO, 'Intercambio de información'),
             (MUESTRAS, 'Muestras de impresión'), (DECLARACION, 'Declaración de cumplimiento'),
             (TERMINADO, 'Autorizada')]

    organization = models.OneToOneField('organizations.Organization', on_delete=models.CASCADE,
                                        related_name='certificacion_dte')
    paso = models.CharField(max_length=12, choices=PASOS, default=SET_PRUEBAS)
    set_texto = models.TextField(blank=True)  # el set de pruebas tal como lo entrega el SII
    casos = models.JSONField(default=list, blank=True)  # el set interpretado, caso por caso
    notas = models.JSONField(default=dict, blank=True)  # lo que cada paso guarda (trackids, archivos...)
    actualizado_en = models.DateTimeField(auto_now=True)

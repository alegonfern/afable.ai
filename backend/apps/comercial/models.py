"""Compras y Ventas (22-10-2026): los documentos que vienen ANTES de la factura, al estilo Odoo.

Ventas:  Cotización → Orden de venta → Entrega → Factura
Compras: Solicitud de cotización → Orden de compra → Recepción → Factura del proveedor

La diferencia con Odoo es la factura: en Afable no se crea aquí, llega del SII (el Registro de
Compras y Ventas que se carga en Contabilidad, `finanzas.DocumentoTributario`). El pedido se
AMARRA a esa factura real (`PedidoFactura`), así nada se registra dos veces.

El contacto es la ficha única de finanzas (`finanzas.Contacto`): un RUT con las casillas cliente
y proveedor. El inventario se lleva siempre con bodegas y movimientos; el nivel que eligió la
empresa (sin inventario, básico, completo) solo decide qué se muestra y qué se pide.
"""

from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import models, transaction
from django.db.models import Sum

from apps.finanzas import constantes as fc

VENTA, COMPRA = 'venta', 'compra'
TIPOS_PEDIDO = [(VENTA, 'Venta'), (COMPRA, 'Compra')]

CLP, USD, UF = 'CLP', 'USD', 'UF'
MONEDAS = [(CLP, 'Peso chileno'), (USD, 'Dólar'), (UF, 'Unidad de fomento')]
# Cuántos decimales lleva cada moneda en los montos.
DECIMALES = {CLP: 0, USD: 2, UF: 4}

SIN_INVENTARIO, INVENTARIO_BASICO, INVENTARIO_COMPLETO = 'ninguno', 'basico', 'completo'
NIVELES_INVENTARIO = [
    (SIN_INVENTARIO, 'Sin inventario'),
    (INVENTARIO_BASICO, 'Básico: stock por producto'),
    (INVENTARIO_COMPLETO, 'Completo: stock por bodega'),
]

CERO = Decimal('0')


def redondear(valor, moneda):
    paso = Decimal(1).scaleb(-DECIMALES.get(moneda, 0))
    return Decimal(valor).quantize(paso, rounding=ROUND_HALF_UP)


class ConfiguracionComercial(models.Model):
    """Cómo trabaja la empresa sus compras y ventas. Se crea con los valores por defecto."""

    PEDIDO, ENTREGADO = 'pedido', 'entregado'
    POLITICAS = [(PEDIDO, 'Lo pedido'), (ENTREGADO, 'Lo entregado o recibido')]

    organization = models.OneToOneField('organizations.Organization', on_delete=models.CASCADE,
                                        related_name='configuracion_comercial')
    nivel_inventario = models.CharField(max_length=10, choices=NIVELES_INVENTARIO,
                                        default=SIN_INVENTARIO)
    # Qué se espera ver facturado: lo pedido o lo que ya se entregó (o recibió). Es la
    # "política de facturación" de Odoo; decide qué aparece en "Por facturar".
    facturar_ventas = models.CharField(max_length=10, choices=POLITICAS, default=PEDIDO)
    facturar_compras = models.CharField(max_length=10, choices=POLITICAS, default=ENTREGADO)
    validez_cotizacion_dias = models.PositiveSmallIntegerField(default=30)
    # Diferencia aceptada entre lo pedido y lo facturado antes de avisar.
    tolerancia_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('2'))
    # Cuántos días puede esperar una cotización enviada antes de avisar que no hay respuesta.
    dias_sin_respuesta = models.PositiveSmallIntegerField(default=7)
    condiciones_venta = models.TextField(blank=True)
    # Proveedor de emisión de facturas electrónicas. Vacío mientras no se elija.
    proveedor_dte = models.CharField(max_length=20, blank=True)
    # Los datos del EMISOR que lleva cada factura (25-10-2026). El RUT es el de la empresa
    # (Organization.rut); la razón social, si queda vacía, es su nombre.
    emisor_razon_social = models.CharField(max_length=255, blank=True)
    emisor_giro = models.CharField(max_length=255, blank=True)
    emisor_direccion = models.CharField(max_length=255, blank=True)
    emisor_comuna = models.CharField(max_length=80, blank=True)
    emisor_ciudad = models.CharField(max_length=80, blank=True)

    @classmethod
    def de(cls, organization):
        cfg, _ = cls.objects.get_or_create(organization=organization)
        return cfg

    @property
    def emisor(self):
        org = self.organization
        return {'razon_social': self.emisor_razon_social or org.name, 'rut': org.rut, 'giro': self.emisor_giro,
                'direccion': self.emisor_direccion, 'comuna': self.emisor_comuna, 'ciudad': self.emisor_ciudad}

    @property
    def emisor_faltan(self):
        """Lo que le falta a la empresa para emitir una factura, dicho como se le pide."""
        e = self.emisor
        return [nombre for clave, nombre in (('rut', 'el RUT'), ('razon_social', 'la razón social'), ('giro', 'el giro'),
                                             ('direccion', 'la dirección'), ('comuna', 'la comuna')) if not e[clave]]

    @property
    def con_inventario(self):
        return self.nivel_inventario != SIN_INVENTARIO


class Secuencia(models.Model):
    """Los correlativos de la empresa: OV-0001, OC-0001, GD-0001, REC-0001."""

    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE,
                                     related_name='secuencias_comerciales')
    prefijo = models.CharField(max_length=8)
    siguiente = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['organization', 'prefijo'],
                                               name='secuencia_unica')]

    @classmethod
    def tomar(cls, organization, prefijo):
        with transaction.atomic():
            sec, _ = cls.objects.select_for_update().get_or_create(organization=organization, prefijo=prefijo)
            numero = sec.siguiente
            sec.siguiente += 1
            sec.save(update_fields=['siguiente'])
        return f'{prefijo}-{numero:04d}'


class Producto(models.Model):
    """Lo que se vende o se compra. Como en Odoo: almacenable (lleva stock), consumible (se
    compra y se usa, sin stock) o servicio."""

    ALMACENABLE, CONSUMIBLE, SERVICIO = 'almacenable', 'consumible', 'servicio'
    TIPOS = [(ALMACENABLE, 'Almacenable'), (CONSUMIBLE, 'Consumible'), (SERVICIO, 'Servicio')]

    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE,
                                     related_name='productos')
    codigo = models.CharField(max_length=40, blank=True)
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    tipo = models.CharField(max_length=12, choices=TIPOS, default=ALMACENABLE)
    unidad = models.CharField(max_length=20, default='un')
    precio_venta = models.DecimalField(max_digits=18, decimal_places=4, default=CERO)
    costo = models.DecimalField(max_digits=18, decimal_places=4, default=CERO)
    exento = models.BooleanField(default=False)
    se_vende = models.BooleanField(default=True)
    se_compra = models.BooleanField(default=True)
    stock_minimo = models.DecimalField(max_digits=14, decimal_places=3, default=CERO)
    # Cuánto pedir al reponer (la automatización «Reponer stock»). En cero, lo que falta para
    # llegar al doble del mínimo.
    cantidad_reorden = models.DecimalField(max_digits=14, decimal_places=3, default=CERO)
    # Inventario (26-10-2026): el máximo que conviene tener, la familia para agrupar, dónde está
    # en la bodega (pasillo, estante) y el código de barras para contarlo.
    stock_maximo = models.DecimalField(max_digits=14, decimal_places=3, default=CERO)
    familia = models.CharField(max_length=80, blank=True)
    codigo_barras = models.CharField(max_length=40, blank=True)
    ubicacion = models.CharField(max_length=40, blank=True)
    # Con qué categoría de finanzas se cuenta (sirve para sugerir la de la factura).
    categoria_venta = models.ForeignKey('finanzas.Categoria', null=True, blank=True,
                                        on_delete=models.SET_NULL, related_name='+')
    categoria_compra = models.ForeignKey('finanzas.Categoria', null=True, blank=True,
                                         on_delete=models.SET_NULL, related_name='+')
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nombre']
        constraints = [models.UniqueConstraint(
            fields=['organization', 'codigo'], condition=~models.Q(codigo=''),
            name='producto_codigo_unico')]

    def __str__(self):
        return f'[{self.codigo}] {self.nombre}' if self.codigo else self.nombre

    @property
    def lleva_stock(self):
        return self.tipo == self.ALMACENABLE


class Bodega(models.Model):
    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE,
                                     related_name='bodegas')
    nombre = models.CharField(max_length=80)
    codigo = models.CharField(max_length=10, blank=True)
    direccion = models.CharField(max_length=255, blank=True)
    principal = models.BooleanField(default=False)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ['-principal', 'nombre']

    def __str__(self):
        return self.nombre

    @classmethod
    def principal_de(cls, organization):
        """La bodega por defecto. En el nivel básico es la única y no se muestra."""
        b = cls.objects.filter(organization=organization, principal=True).first()
        if b is None:
            b = cls.objects.create(organization=organization, nombre='Bodega principal',
                                   codigo='BP', principal=True)
        return b


class Pedido(models.Model):
    """Una cotización u orden, de venta o de compra. Es el mismo documento que avanza de estado,
    como en Odoo: la cotización OV-0012, al confirmarse, es la orden de venta OV-0012."""

    BORRADOR, ENVIADO, CONFIRMADO, CANCELADO = 'borrador', 'enviado', 'confirmado', 'cancelado'
    ESTADOS = [(BORRADOR, 'Borrador'), (ENVIADO, 'Enviado'), (CONFIRMADO, 'Confirmado'),
               (CANCELADO, 'Cancelado')]
    PREFIJO = {VENTA: 'OV', COMPRA: 'OC'}

    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE,
                                     related_name='pedidos')
    tipo = models.CharField(max_length=6, choices=TIPOS_PEDIDO)
    numero = models.CharField(max_length=20)
    contacto = models.ForeignKey('finanzas.Contacto', on_delete=models.PROTECT, related_name='pedidos')
    estado = models.CharField(max_length=10, choices=ESTADOS, default=BORRADOR)
    fecha = models.DateField()
    # Ventas: cuándo se comprometió la entrega. Compras: cuándo debería llegar.
    fecha_compromiso = models.DateField(null=True, blank=True)
    # Hasta cuándo vale la cotización.
    valida_hasta = models.DateField(null=True, blank=True)
    moneda = models.CharField(max_length=3, choices=MONEDAS, default=CLP)
    # Pesos por unidad de la moneda, del día del documento. 1 en pesos.
    tipo_cambio = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('1'))
    proyecto = models.ForeignKey('finanzas.Proyecto', null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name='pedidos')
    bodega = models.ForeignKey(Bodega, null=True, blank=True, on_delete=models.SET_NULL, related_name='pedidos')
    plazo_dias = models.PositiveSmallIntegerField(null=True, blank=True)
    # La OC del cliente (en ventas) o la cotización del proveedor (en compras).
    referencia = models.CharField(max_length=60, blank=True)
    notas = models.TextField(blank=True)
    condiciones = models.TextField(blank=True)
    # Totales en la moneda del documento, recalculados al guardar las líneas.
    neto = models.DecimalField(max_digits=18, decimal_places=4, default=CERO)
    exento = models.DecimalField(max_digits=18, decimal_places=4, default=CERO)
    iva = models.DecimalField(max_digits=18, decimal_places=4, default=CERO)
    total = models.DecimalField(max_digits=18, decimal_places=4, default=CERO)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name='+')
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    enviado_en = models.DateTimeField(null=True, blank=True)
    confirmado_en = models.DateTimeField(null=True, blank=True)
    # Cuándo se le recordó al cliente una cotización sin respuesta (automatización).
    recordado_en = models.DateTimeField(null=True, blank=True)
    # Quién lo armó: vacío si fue una persona; 'reposicion' si lo creó la automatización.
    origen = models.CharField(max_length=20, blank=True)

    class Meta:
        ordering = ['-fecha', '-id']
        constraints = [models.UniqueConstraint(fields=['organization', 'numero'], name='pedido_numero_unico')]
        indexes = [models.Index(fields=['organization', 'tipo', 'estado'])]

    def __str__(self):
        return self.numero

    @property
    def es_orden(self):
        return self.estado == self.CONFIRMADO

    def a_pesos(self, monto):
        return int(redondear(Decimal(monto) * self.tipo_cambio, CLP))

    @property
    def base_clp(self):
        """Lo que se compara con las facturas del SII: neto + exento, en pesos (sin IVA)."""
        return self.a_pesos(self.neto + self.exento)

    def recalcular(self):
        neto = exento = CERO
        for linea in self.lineas.all():
            if linea.exento:
                exento += linea.subtotal
            else:
                neto += linea.subtotal
        self.neto = redondear(neto, self.moneda)
        self.exento = redondear(exento, self.moneda)
        self.iva = redondear(self.neto * fc.IVA, self.moneda)
        self.total = self.neto + self.exento + self.iva
        self.save(update_fields=['neto', 'exento', 'iva', 'total', 'actualizado_en'])


class LineaPedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='lineas')
    orden = models.PositiveSmallIntegerField(default=0)
    producto = models.ForeignKey(Producto, null=True, blank=True, on_delete=models.PROTECT, related_name='lineas')
    descripcion = models.CharField(max_length=500)
    cantidad = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('1'))
    unidad = models.CharField(max_length=20, default='un')
    precio_unitario = models.DecimalField(max_digits=18, decimal_places=4, default=CERO)
    descuento_pct = models.DecimalField(max_digits=5, decimal_places=2, default=CERO)
    exento = models.BooleanField(default=False)
    # Lo entregado (ventas) o recibido (compras), sumado de las entregas hechas.
    cantidad_entregada = models.DecimalField(max_digits=14, decimal_places=3, default=CERO)

    class Meta:
        ordering = ['orden', 'id']

    @property
    def subtotal(self):
        bruto = self.cantidad * self.precio_unitario
        return bruto - bruto * self.descuento_pct / Decimal('100')

    @property
    def subtotal_entregado(self):
        if not self.cantidad:
            return CERO
        return self.subtotal * self.cantidad_entregada / self.cantidad

    @property
    def pendiente_entrega(self):
        return max(self.cantidad - self.cantidad_entregada, CERO)

    @property
    def mueve_stock(self):
        return self.producto_id is not None and self.producto.lleva_stock


class Entrega(models.Model):
    """Una entrega a un cliente (guía de despacho) o una recepción de un proveedor. Se registra
    hecha: cuando se crea, la mercadería ya salió o ya llegó, y el stock se mueve.

    También la devolución: lo que el cliente devuelve, o lo que se le devuelve al proveedor.
    Resta de lo entregado (o recibido) y mueve el stock al revés."""

    HECHA, ANULADA = 'hecha', 'anulada'
    ESTADOS = [(HECHA, 'Hecha'), (ANULADA, 'Anulada')]
    ENTREGA, DEVOLUCION = 'entrega', 'devolucion'
    TIPOS = [(ENTREGA, 'Entrega o recepción'), (DEVOLUCION, 'Devolución')]
    PREFIJO = {VENTA: 'GD', COMPRA: 'REC'}
    PREFIJO_DEVOLUCION = {VENTA: 'DV', COMPRA: 'DC'}

    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE,
                                     related_name='entregas')
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='entregas')
    numero = models.CharField(max_length=20)
    fecha = models.DateField()
    bodega = models.ForeignKey(Bodega, null=True, blank=True, on_delete=models.SET_NULL, related_name='entregas')
    estado = models.CharField(max_length=8, choices=ESTADOS, default=HECHA)
    tipo = models.CharField(max_length=10, choices=TIPOS, default=ENTREGA)
    # El folio de la guía de despacho electrónica (DTE 52), si se emitió.
    folio_guia = models.CharField(max_length=20, blank=True)
    notas = models.TextField(blank=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name='+')
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha', '-id']


class LineaEntrega(models.Model):
    entrega = models.ForeignKey(Entrega, on_delete=models.CASCADE, related_name='lineas')
    linea = models.ForeignKey(LineaPedido, on_delete=models.CASCADE, related_name='entregas')
    cantidad = models.DecimalField(max_digits=14, decimal_places=3)


class MovimientoStock(models.Model):
    """Cada entrada o salida de una bodega. El stock no se guarda: es la suma de esto."""

    COMPRA, VENTA, AJUSTE, TRASPASO, INICIAL, ANULACION, DEVOLUCION = (
        'compra', 'venta', 'ajuste', 'traspaso', 'inicial', 'anulacion', 'devolucion')
    ENTRADA, SALIDA, CONTEO = 'entrada', 'salida', 'conteo'
    TIPOS = [(COMPRA, 'Recepción de compra'), (VENTA, 'Entrega de venta'), (AJUSTE, 'Ajuste'),
             (TRASPASO, 'Traspaso'), (INICIAL, 'Stock inicial'), (ANULACION, 'Anulación'),
             (DEVOLUCION, 'Devolución'), (ENTRADA, 'Entrada manual'), (SALIDA, 'Salida manual'),
             (CONTEO, 'Toma de inventario')]
    # Por qué entra o sale algo sin una orden de por medio (26-10-2026).
    MOTIVOS_ENTRADA = [('inicial', 'Stock inicial'), ('produccion', 'Producción'),
                       ('devolucion_sin_orden', 'Devolución sin orden'), ('hallazgo', 'Sobrante encontrado'),
                       ('otro_entrada', 'Otro')]
    MOTIVOS_SALIDA = [('merma', 'Merma o daño'), ('vencimiento', 'Vencimiento'), ('consumo_interno', 'Consumo interno'),
                      ('muestra', 'Muestra o regalo'), ('robo', 'Pérdida o robo'), ('otro_salida', 'Otro')]
    MOTIVOS = MOTIVOS_ENTRADA + MOTIVOS_SALIDA

    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE,
                                     related_name='movimientos_stock')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='movimientos')
    bodega = models.ForeignKey(Bodega, on_delete=models.PROTECT, related_name='movimientos')
    # Positivo entra, negativo sale.
    cantidad = models.DecimalField(max_digits=14, decimal_places=3)
    tipo = models.CharField(max_length=10, choices=TIPOS)
    fecha = models.DateField()
    # Lo que costó cada unidad en pesos, sin IVA: en una recepción, el precio de la OC; en lo
    # demás, el costo promedio del momento. Con esto se valoriza el inventario.
    costo_unitario = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    entrega = models.ForeignKey(Entrega, null=True, blank=True, on_delete=models.SET_NULL, related_name='movimientos')
    referencia = models.CharField(max_length=120, blank=True)
    motivo = models.CharField(max_length=20, choices=MOTIVOS, blank=True)
    conteo = models.ForeignKey('ConteoInventario', null=True, blank=True, on_delete=models.SET_NULL,
                               related_name='movimientos')
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name='+')
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha', '-id']
        indexes = [models.Index(fields=['organization', 'producto', 'bodega'])]


class ConteoInventario(models.Model):
    """Una toma de inventario: se fotografía lo que dice el sistema, se cuenta lo que hay y, al
    aplicar, las diferencias quedan como movimientos (tipo CONTEO)."""

    BORRADOR, CONTANDO, APLICADO, CANCELADO = 'borrador', 'contando', 'aplicado', 'cancelado'
    ESTADOS = [(BORRADOR, 'Borrador'), (CONTANDO, 'Contando'), (APLICADO, 'Aplicado'), (CANCELADO, 'Cancelado')]

    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE,
                                     related_name='conteos_inventario')
    numero = models.CharField(max_length=20)
    estado = models.CharField(max_length=10, choices=ESTADOS, default=CONTANDO)
    bodega = models.ForeignKey(Bodega, null=True, blank=True, on_delete=models.SET_NULL, related_name='conteos')
    familia = models.CharField(max_length=80, blank=True)
    fecha = models.DateField()
    notas = models.TextField(blank=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name='+')
    creado_en = models.DateTimeField(auto_now_add=True)
    aplicado_en = models.DateTimeField(null=True, blank=True)
    aplicado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name='+')

    class Meta:
        ordering = ['-creado_en']


class LineaConteo(models.Model):
    conteo = models.ForeignKey(ConteoInventario, on_delete=models.CASCADE, related_name='lineas')
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='+')
    bodega = models.ForeignKey(Bodega, on_delete=models.CASCADE, related_name='+')
    # Lo que decía el sistema al crear el conteo y lo que se contó (vacío: todavía no).
    sistema = models.DecimalField(max_digits=14, decimal_places=3, default=CERO)
    contada = models.DecimalField(max_digits=14, decimal_places=3, null=True, blank=True)
    costo_unitario = models.DecimalField(max_digits=18, decimal_places=4, default=CERO)

    class Meta:
        ordering = ['producto__nombre', 'id']


def stock(organization, producto=None, bodega=None):
    """{(producto_id, bodega_id): cantidad} con lo que hay hoy."""
    qs = MovimientoStock.objects.filter(organization=organization)
    if producto is not None:
        qs = qs.filter(producto=producto)
    if bodega is not None:
        qs = qs.filter(bodega=bodega)
    return {(r['producto'], r['bodega']): r['total'] or CERO
            for r in qs.values('producto', 'bodega').annotate(total=Sum('cantidad'))}


class PedidoFactura(models.Model):
    """La factura real del SII que corresponde a un pedido. Un pedido puede facturarse en varias
    facturas y una factura puede cubrir varios pedidos: el monto dice cuánto de esa factura
    (sin IVA, en pesos) le toca a este pedido."""

    AUTOMATICA, MANUAL = 'auto', 'manual'

    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='facturas')
    documento = models.ForeignKey('finanzas.DocumentoTributario', on_delete=models.CASCADE,
                                  related_name='pedidos')
    monto = models.BigIntegerField()
    origen = models.CharField(max_length=6, default=MANUAL)
    # La factura la dio por pagada un pago de este pedido (y se desmarca si ese pago se borra).
    marcado_pagado = models.BooleanField(default=False)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name='+')
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['pedido', 'documento'], name='pedido_factura_unica')]


class TipoCambio(models.Model):
    """El valor en pesos de una moneda en un día (dólar observado, UF). Es de todos: no depende
    de la empresa. Se trae de la fuente pública y se guarda para no volver a pedirlo."""

    moneda = models.CharField(max_length=3, choices=MONEDAS)
    fecha = models.DateField()
    valor = models.DecimalField(max_digits=14, decimal_places=4)
    fuente = models.CharField(max_length=40, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['moneda', 'fecha'], name='tipo_cambio_unico')]
        ordering = ['-fecha']


class PagoPedido(models.Model):
    """Un cobro (de una orden de venta) o un pago (de una orden de compra), en pesos y con IVA.
    Cuando lo pagado cubre la orden, sus facturas del SII quedan pagadas en Finanzas."""

    TRANSFERENCIA, EFECTIVO, TARJETA, CHEQUE, OTRO = 'transferencia', 'efectivo', 'tarjeta', 'cheque', 'otro'
    MEDIOS = [(TRANSFERENCIA, 'Transferencia'), (EFECTIVO, 'Efectivo'), (TARJETA, 'Tarjeta'),
              (CHEQUE, 'Cheque'), (OTRO, 'Otro')]

    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='pagos')
    fecha = models.DateField()
    monto = models.BigIntegerField()
    medio = models.CharField(max_length=15, choices=MEDIOS, default=TRANSFERENCIA)
    referencia = models.CharField(max_length=80, blank=True)
    notas = models.TextField(blank=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name='+')
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['fecha', 'id']


class PrecioContacto(models.Model):
    """El precio de un producto para un cliente (en ventas) o de un proveedor (en compras). Se
    propone solo al agregar el producto a una línea de ese contacto. En compras, el proveedor
    con precio es el que se usa al reponer stock (el preferido, o el más barato)."""

    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE,
                                     related_name='precios_contacto')
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='precios')
    contacto = models.ForeignKey('finanzas.Contacto', on_delete=models.CASCADE, related_name='precios')
    tipo = models.CharField(max_length=6, choices=TIPOS_PEDIDO)
    precio = models.DecimalField(max_digits=18, decimal_places=4)
    # Solo compras: el código con que el proveedor conoce el producto y si es el preferido.
    codigo_contacto = models.CharField(max_length=40, blank=True)
    preferido = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['producto', 'contacto', 'tipo'], name='precio_contacto_unico')]
        ordering = ['-preferido', 'precio']

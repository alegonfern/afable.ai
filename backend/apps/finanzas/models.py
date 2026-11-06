"""Finanzas: lo que la empresa descarga del SII, clasificado para entender su negocio.

Todo cuelga de la Empresa (`organizations.Organization`), igual que los archivos y las
conexiones: es información de la empresa, no de un área.
"""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from . import constantes as c


class ConfiguracionTributaria(models.Model):
    """Las variables tributarias que dependen de cada empresa: régimen y tasa de PPM."""

    organization = models.OneToOneField(
        'organizations.Organization', on_delete=models.CASCADE,
        related_name='configuracion_tributaria',
    )
    regimen = models.CharField(max_length=8, choices=c.REGIMENES,
                               default=c.REGIMEN_PRO_PYME_GENERAL)
    # Porcentaje (0.25 = 0,25%). Parte con la sugerida del régimen; la empresa la confirma.
    tasa_ppm = models.DecimalField(max_digits=5, decimal_places=3,
                                   default=c.PPM_SUGERIDA[c.REGIMEN_PRO_PYME_GENERAL])
    # Sin confirmar, el F29 se muestra con la advertencia de que la tasa es la sugerida.
    tasa_ppm_confirmada = models.BooleanField(default=False)
    actualizado_en = models.DateTimeField(auto_now=True)

    @classmethod
    def de(cls, organization):
        """La configuración de la empresa, creándola con los valores sugeridos si no existe."""
        config, _ = cls.objects.get_or_create(organization=organization)
        return config


class Categoria(models.Model):
    TIPOS = [('ingreso', 'Ingreso'), ('gasto', 'Gasto')]

    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE,
                                     related_name='categorias_financieras')
    nombre = models.CharField(max_length=80)
    tipo = models.CharField(max_length=8, choices=TIPOS)
    # La cuenta del plan de cuentas a la que corresponde (22-10-2026). Opcional: hoy nada la
    # usa; queda para cuando Afable lleve la contabilidad formal (diario, mayor, balance) y los
    # asientos salgan de lo que ya está clasificado, sin reclasificar.
    cuenta_codigo = models.CharField(max_length=20, blank=True)
    cuenta_nombre = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ['tipo', 'nombre']
        constraints = [models.UniqueConstraint(fields=['organization', 'nombre'],
                                               name='categoria_unica_por_empresa')]

    def __str__(self):
        return self.nombre

    @classmethod
    def asegurar_iniciales(cls, organization):
        """Crea las categorías de partida la primera vez que la empresa usa Finanzas."""
        if cls.objects.filter(organization=organization).exists():
            return
        cls.objects.bulk_create([
            cls(organization=organization, nombre=nombre, tipo=tipo)
            for tipo, nombres in c.CATEGORIAS_INICIALES.items() for nombre in nombres
        ])


class Proyecto(models.Model):
    """Donde se gana o se pierde: una obra, un local, un cliente, una línea de productos."""

    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE,
                                     related_name='proyectos_financieros')
    nombre = models.CharField(max_length=120)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ['nombre']
        constraints = [models.UniqueConstraint(fields=['organization', 'nombre'],
                                               name='proyecto_unico_por_empresa')]

    def __str__(self):
        return self.nombre


class Carga(models.Model):
    """Un archivo del SII subido. Nace en BORRADOR: se revisa (categoría, proyecto, pago) y
    recién al confirmar entran los documentos. Así nada queda a medio clasificar."""

    BORRADOR = 'borrador'
    IMPORTADA = 'importada'

    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE,
                                     related_name='cargas_sii')
    libro = models.CharField(max_length=12, choices=c.LIBROS)
    nombre_archivo = models.CharField(max_length=255)
    subido_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True,
                                   on_delete=models.SET_NULL)
    filas = models.PositiveIntegerField(default=0)
    nuevos = models.PositiveIntegerField(default=0)
    duplicados = models.PositiveIntegerField(default=0)
    # [{"fila": 7, "folio": "1043", "motivo": "..."}]
    errores = models.JSONField(default=list, blank=True)
    estado = models.CharField(max_length=10, default=BORRADOR)
    # Mientras es borrador: las filas leídas con lo que Afable propone para cada una.
    filas_previas = models.JSONField(default=list, blank=True)
    # Los que ya estaban cargados: no se tocan, pero se muestran.
    ya_estaban = models.JSONField(default=list, blank=True)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creada_en']


class DocumentoTributario(models.Model):
    """Una línea del Registro de Compras y Ventas o una boleta de honorarios recibida."""

    POR_REVISAR = 'por_revisar'
    CONFIRMADO = 'confirmado'
    ESTADOS = [(POR_REVISAR, 'Por revisar'), (CONFIRMADO, 'Confirmado')]

    ORIGEN_REGLA = 'regla'
    ORIGEN_IA = 'ia'

    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE,
                                     related_name='documentos_tributarios')
    carga = models.ForeignKey(Carga, null=True, blank=True, on_delete=models.SET_NULL,
                              related_name='documentos')
    libro = models.CharField(max_length=12, choices=c.LIBROS)
    tipo_documento = models.CharField(max_length=4)          # '33', '61', 'BHE'…
    folio = models.CharField(max_length=20)
    # La contraparte: el proveedor en compras y honorarios, el cliente en ventas.
    rut = models.CharField(max_length=12)
    razon_social = models.CharField(max_length=255, blank=True)
    fecha = models.DateField()
    monto_exento = models.BigIntegerField(default=0)
    monto_neto = models.BigIntegerField(default=0)
    monto_iva = models.BigIntegerField(default=0)
    monto_total = models.BigIntegerField(default=0)
    # Solo honorarios: lo retenido (que la empresa entera en el F29) y lo pagado al emisor.
    monto_retenido = models.BigIntegerField(default=0)

    contraparte = models.ForeignKey('Contraparte', null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name='documentos')
    categoria = models.ForeignKey(Categoria, null=True, blank=True, on_delete=models.SET_NULL,
                                  related_name='documentos')
    # Cuándo se espera el pago (fecha + plazo de la contraparte) y si ya se pagó o se cobró.
    fecha_vencimiento = models.DateField(null=True, blank=True)
    pagado = models.BooleanField(default=False)
    fecha_pago = models.DateField(null=True, blank=True)
    medio_pago = models.CharField(max_length=40, blank=True)
    estado = models.CharField(max_length=12, choices=ESTADOS, default=POR_REVISAR)
    # De dónde salió la categoría que tiene: una regla del proveedor o una sugerencia de la IA.
    # Vacío si la puso una persona.
    origen_clasificacion = models.CharField(max_length=8, blank=True)
    # Emitida desde Afable (25-10-2026, comercial/emision.py): tiene su PDF y su pedido. Las que
    # llegan del Registro de Ventas del SII se emitieron en otro lado.
    emitido_en_afable = models.BooleanField(default=False)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha', '-id']
        constraints = [models.UniqueConstraint(
            fields=['organization', 'libro', 'tipo_documento', 'rut', 'folio'],
            name='documento_tributario_unico',
        )]
        indexes = [models.Index(fields=['organization', 'libro', 'fecha'])]

    @property
    def signo(self):
        return -1 if self.tipo_documento in c.TIPOS_QUE_RESTAN else 1


class Asignacion(models.Model):
    """Qué parte de un documento corresponde a cada proyecto (60/40, por ejemplo)."""

    documento = models.ForeignKey(DocumentoTributario, on_delete=models.CASCADE,
                                  related_name='asignaciones')
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE, related_name='asignaciones')
    porcentaje = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01')), MaxValueValidator(Decimal('100'))],
    )

    class Meta:
        constraints = [models.UniqueConstraint(fields=['documento', 'proyecto'],
                                               name='asignacion_unica')]


class Contacto(models.Model):
    """La ficha ÚNICA de una persona o empresa con la que se trabaja (22-10-2026), como el
    contacto de Odoo: un RUT, con las casillas cliente y proveedor. Ventas muestra los clientes y
    Compras los proveedores. Lo que depende del rol (el plazo de pago y la regla de categoría como
    proveedor o como cliente) sigue en `Contraparte`, una por libro, colgada de esta ficha."""

    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE,
                                     related_name='contactos')
    rut = models.CharField(max_length=12, blank=True)
    razon_social = models.CharField(max_length=255)
    giro = models.CharField(max_length=255, blank=True)
    direccion = models.CharField(max_length=255, blank=True)
    comuna = models.CharField(max_length=80, blank=True)
    ciudad = models.CharField(max_length=80, blank=True)
    email = models.EmailField(blank=True)
    telefono = models.CharField(max_length=30, blank=True)
    persona_contacto = models.CharField(max_length=120, blank=True)
    es_cliente = models.BooleanField(default=False)
    es_proveedor = models.BooleanField(default=False)
    notas = models.TextField(blank=True)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['razon_social']
        constraints = [models.UniqueConstraint(
            fields=['organization', 'rut'], condition=~models.Q(rut=''),
            name='contacto_unico_por_rut')]

    def __str__(self):
        return self.razon_social or self.rut

    @classmethod
    def para(cls, organization, rut, razon_social='', libro=None):
        """La ficha del RUT (la crea si no existe) con el rol que corresponde al libro marcado."""
        contacto, _ = cls.objects.get_or_create(
            organization=organization, rut=rut,
            defaults={'razon_social': razon_social or rut})
        cambios = []
        if not contacto.razon_social and razon_social:
            contacto.razon_social = razon_social
            cambios.append('razon_social')
        if libro == 'ventas' and not contacto.es_cliente:
            contacto.es_cliente = True
            cambios.append('es_cliente')
        if libro in ('compras', 'honorarios') and not contacto.es_proveedor:
            contacto.es_proveedor = True
            cambios.append('es_proveedor')
        if cambios:
            contacto.save(update_fields=cambios)
        return contacto


class Contraparte(models.Model):
    """Lo que depende del ROL de un contacto en un libro: el plazo habitual de pago y, si se
    decidió, la regla con que se clasifican sus documentos. Un contacto que es cliente y
    proveedor tiene dos (una por libro), colgadas de la misma ficha (`Contacto`)."""

    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE,
                                     related_name='contrapartes')
    contacto = models.ForeignKey(Contacto, null=True, blank=True, on_delete=models.CASCADE,
                                 related_name='roles')
    libro = models.CharField(max_length=12, choices=c.LIBROS)
    rut = models.CharField(max_length=12)
    razon_social = models.CharField(max_length=255, blank=True)
    # Días entre el documento y su pago. Vacío: se usa PLAZO_PAGO_POR_DEFECTO.
    plazo_dias = models.PositiveSmallIntegerField(null=True, blank=True)
    # La regla: "siempre así para esta contraparte". Solo cuenta si `regla_activa`.
    regla_activa = models.BooleanField(default=False)
    categoria = models.ForeignKey(Categoria, null=True, blank=True, on_delete=models.SET_NULL)
    medio_pago = models.CharField(max_length=40, blank=True)
    # [{"proyecto": 3, "porcentaje": "60"}]
    reparto = models.JSONField(default=list, blank=True)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['razon_social']
        constraints = [models.UniqueConstraint(fields=['organization', 'libro', 'rut'],
                                               name='contraparte_unica_por_libro')]

    @property
    def plazo(self):
        return self.plazo_dias if self.plazo_dias is not None else c.PLAZO_PAGO_POR_DEFECTO

    def save(self, *args, **kwargs):
        # Toda contraparte cuelga de su ficha única: venga del importador, de una regla o de
        # una pantalla, la ficha se crea (o se marca con el rol) aquí, en un solo lugar.
        if self.contacto_id is None:
            self.contacto = Contacto.para(self.organization, self.rut, self.razon_social, self.libro)
        super().save(*args, **kwargs)


class DeclaracionF29(models.Model):
    """El estado del F29 de un mes: si ya se pagó, cuánto y cuándo. El monto estimado no se
    guarda: se calcula siempre desde los documentos."""

    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE,
                                     related_name='declaraciones_f29')
    anio = models.PositiveSmallIntegerField()
    mes = models.PositiveSmallIntegerField()
    pagado = models.BooleanField(default=False)
    monto_pagado = models.BigIntegerField(null=True, blank=True)
    fecha_pago = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['organization', 'anio', 'mes'],
                                               name='f29_unico_por_mes')]



# ── Conciliación bancaria ("El cuadre") ─────────────────────────────────────

class CuentaBancaria(models.Model):
    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE,
                                     related_name='cuentas_bancarias')
    banco = models.CharField(max_length=80)
    nombre = models.CharField(max_length=80, blank=True)       # "Cuenta corriente", "Vista"…
    numero = models.CharField(max_length=40, blank=True)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['banco', 'nombre']

    def __str__(self):
        return f'{self.banco} {self.nombre} {self.numero}'.strip()


class Cartola(models.Model):
    """Un archivo de movimientos bancarios subido."""

    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE,
                                     related_name='cartolas')
    cuenta = models.ForeignKey(CuentaBancaria, on_delete=models.CASCADE, related_name='cartolas')
    nombre_archivo = models.CharField(max_length=255)
    desde = models.DateField(null=True)
    hasta = models.DateField(null=True)
    saldo_final = models.BigIntegerField(null=True, blank=True)
    nuevos = models.PositiveIntegerField(default=0)
    duplicados = models.PositiveIntegerField(default=0)
    errores = models.JSONField(default=list, blank=True)
    subida_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creada_en']


class MovimientoBancario(models.Model):
    """Una línea de la cartola. Monto con signo: abono positivo, cargo negativo."""

    PENDIENTE = 'pendiente'      # sin explicar todavía
    CONCILIADO = 'conciliado'    # cruzado con uno o más documentos
    TRASPASO = 'traspaso'        # entre cuentas propias: no es ingreso ni gasto
    IDENTIFICADO = 'identificado'  # explicado sin documento (retiro, comisión, impuesto…)
    ESTADOS = [(PENDIENTE, 'Pendiente'), (CONCILIADO, 'Conciliado'), (TRASPASO, 'Traspaso'),
               (IDENTIFICADO, 'Identificado')]

    # Cómo se explica un movimiento sin documento del SII.
    TIPOS_SIN_DOCUMENTO = [
        ('retiro_dueno', 'Retiro del dueño'), ('aporte_capital', 'Aporte de capital'),
        ('comision', 'Comisión o gasto bancario'), ('remuneraciones', 'Remuneraciones'),
        ('impuestos', 'Pago de impuestos (F29, TGR)'), ('prestamo', 'Préstamo o crédito'),
        ('otro', 'Otro'),
    ]

    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE,
                                     related_name='movimientos_bancarios')
    cuenta = models.ForeignKey(CuentaBancaria, on_delete=models.CASCADE, related_name='movimientos')
    cartola = models.ForeignKey(Cartola, null=True, on_delete=models.SET_NULL, related_name='movimientos')
    fecha = models.DateField()
    descripcion = models.CharField(max_length=255, blank=True)
    monto = models.BigIntegerField()
    saldo = models.BigIntegerField(null=True, blank=True)
    # Para no repetir al volver a subir la misma cartola (fecha + monto + glosa + n° de orden).
    huella = models.CharField(max_length=64)
    estado = models.CharField(max_length=14, choices=ESTADOS, default=PENDIENTE)
    # 'auto' si lo cruzó Afable, 'manual' si una persona. Vacío mientras está pendiente.
    origen = models.CharField(max_length=8, blank=True)
    tipo_sin_documento = models.CharField(max_length=20, blank=True, choices=TIPOS_SIN_DOCUMENTO)
    documentos = models.ManyToManyField(DocumentoTributario, blank=True, related_name='movimientos')
    # El otro lado de un traspaso (o la sugerencia de que lo es, mientras está pendiente).
    pareja = models.OneToOneField('self', null=True, blank=True, on_delete=models.SET_NULL,
                                  related_name='+')
    nota = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-fecha', '-id']
        constraints = [models.UniqueConstraint(fields=['cuenta', 'huella'], name='movimiento_unico')]
        indexes = [models.Index(fields=['organization', 'fecha'])]


class CierreMes(models.Model):
    """Un mes conciliado y cerrado: deja constancia de cómo quedó el cuadre."""

    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE,
                                     related_name='cierres_de_mes')
    anio = models.PositiveSmallIntegerField()
    mes = models.PositiveSmallIntegerField()
    porcentaje = models.DecimalField(max_digits=5, decimal_places=1)
    resumen = models.JSONField(default=dict)
    cerrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    cerrado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-anio', '-mes']
        constraints = [models.UniqueConstraint(fields=['organization', 'anio', 'mes'],
                                               name='cierre_unico_por_mes')]



class AutomatizacionModulo(models.Model):
    """Una automatización del catálogo (`automatizaciones.CATALOGO`) activada por la empresa."""

    organization = models.ForeignKey('organizations.Organization', on_delete=models.CASCADE,
                                     related_name='automatizaciones_modulo')
    DIARIA, SEMANAL, MENSUAL = 'diaria', 'semanal', 'mensual'
    FRECUENCIAS = [(DIARIA, 'Cada día'), (SEMANAL, 'Cada semana'), (MENSUAL, 'Cada mes')]

    clave = models.CharField(max_length=40)
    activa = models.BooleanField(default=True)
    por_correo = models.BooleanField(default=True)
    # WhatsApp al lado del correo (22-10-2026): llega a los seguidores con teléfono en su perfil.
    por_whatsapp = models.BooleanField(default=False)
    # La programación (22-10-2026): cada cuánto y a qué hora corre. Vacía = la del catálogo.
    frecuencia = models.CharField(max_length=8, choices=FRECUENCIAS, blank=True)
    dia_semana = models.PositiveSmallIntegerField(null=True, blank=True)     # 0 = lunes
    dia_mes = models.PositiveSmallIntegerField(null=True, blank=True)        # 1 a 28
    hora = models.PositiveSmallIntegerField(null=True, blank=True)           # 0 a 23
    proxima_ejecucion = models.DateTimeField(null=True, blank=True)
    # A quién avisa. Sin seguidores: a los administradores y editores, como hasta ahora.
    seguidores = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True,
                                        related_name='automatizaciones_que_sigue')
    # Qué se avisó por última vez (mes, semana o estado): evita repetir el mismo aviso.
    marca = models.CharField(max_length=60, blank=True)
    ultima_ejecucion = models.DateTimeField(null=True, blank=True)
    ultimo_resultado = models.TextField(blank=True)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['organization', 'clave'],
                                               name='automatizacion_unica_por_empresa')]

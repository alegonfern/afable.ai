"""Facturación: quién paga, con qué, y qué se le cobró.

⭐ **El que paga es la EMPRESA**, y un plan cubre todos sus Workspaces. Afable se vende por
empresa: los archivos, las conexiones y los agentes son de ella, y los miembros entran y
salen. Colgarlo de la persona —como estaba al principio— significaba que si el que pagó se
iba, la empresa quedaba sin plan; colgarlo de un Workspace habría significado pagar una vez
por cada área. Sólo el administrador de la empresa toca esta sección.

Dos pasarelas, porque son dos públicos distintos:

- **Flow** cobra en CLP a los clientes chilenos (Webpay, transferencia).
- **PayPal** cobra en USD al resto. No es un lujo: Flow liquida solo en pesos.

El proveedor viaja en cada fila (`proveedor`) en vez de haber una tabla por pasarela.
Con una tabla por pasarela, "¿qué le cobramos a esta empresa?" habría que preguntarlo
dos veces y unir a mano, y la tercera pasarela obligaría a tocar todas las consultas.

**Ningún dato de tarjeta se guarda acá.** De un medio de pago guardamos lo que sirve
para reconocerlo en una lista (`etiqueta`: "Visa ···· 4242" o el correo de PayPal) y el
identificador que la pasarela nos dio para volver a cobrarle. El número vive en la
pasarela, que para eso está certificada.
"""

from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.db import models

PROVEEDOR_FLOW = 'flow'
PROVEEDOR_PAYPAL = 'paypal'
PROVEEDOR_CHOICES = [
    (PROVEEDOR_FLOW, 'Flow (CLP)'),
    (PROVEEDOR_PAYPAL, 'PayPal (USD)'),
]

MONEDA_CLP = 'CLP'
MONEDA_USD = 'USD'

# Qué moneda cobra cada pasarela. Un solo lugar donde se decide, para que no haya
# una vista armando un cobro en pesos contra PayPal.
MONEDA_DE_PROVEEDOR = {
    PROVEEDOR_FLOW: MONEDA_CLP,
    PROVEEDOR_PAYPAL: MONEDA_USD,
}

# Días de prueba de un plan nuevo. El mismo número para las dos pasarelas: si
# difirieran, el precio dependería de con qué tarjeta pagó y eso no se puede explicar.
DIAS_DE_PRUEBA = 14


class Plan(models.Model):
    """Un plan y su precio en las dos monedas.

    `price_usd` no es la conversión de `price_clp`: es el precio de lista en dólares
    (US$99 donde en Chile son $99.000). Convertir al tipo de cambio del día daría un
    precio que se mueve solo y que nadie puede poner en una landing.

    `es_a_medida` es el caso Enterprise: aparece en la lista, se puede elegir, pero no
    tiene precio ni pasa por una pasarela. Sin este campo habría que adivinarlo de un
    precio en 0, y "gratis" y "hablemos" son dos cosas muy distintas.
    """

    id = models.CharField(max_length=100, primary_key=True)
    name = models.CharField(max_length=100)
    price_clp = models.IntegerField()
    price_usd = models.IntegerField(default=0)
    es_a_medida = models.BooleanField(default=False)
    max_agents = models.IntegerField(default=0)
    max_integrations = models.IntegerField(default=0)
    queries_per_month = models.IntegerField(default=0)
    # El plan se vende por asientos más consumo: `max_usuarios` son los asientos que
    # incluye y `tokens_por_mes` el cupo de créditos del período (1 crédito =
    # US$0,000001 de costo del proveedor, ver services/consumo.py). `queries_per_month`
    # queda porque lo muestra la pantalla de facturación, pero no se aplica en ninguna
    # parte y nunca se comparó contra un costo: el límite real es el de créditos.
    max_usuarios = models.IntegerField(default=0)
    tokens_por_mes = models.BigIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'payment_plans'
        verbose_name = 'Plan'

    def __str__(self):
        return self.name

    def precio_en(self, moneda):
        """El precio en esa moneda, o None si el plan se conversa."""
        if self.es_a_medida:
            return None
        return self.price_usd if moneda == MONEDA_USD else self.price_clp


class ClientePasarela(models.Model):
    """El identificador que la pasarela le puso a esta empresa.

    Flow y PayPal cada uno crea su propio "customer" y después todo se cobra contra
    ese id. Se guarda uno por empresa y por pasarela: pedirlo de nuevo en cada cobro
    crearía un cliente duplicado por cada intento de pago.
    """

    organization = models.ForeignKey(
        'organizations.Organization', on_delete=models.CASCADE, related_name='clientes_pasarela'
    )
    proveedor = models.CharField(max_length=20, choices=PROVEEDOR_CHOICES)
    customer_id = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'clientes_pasarela'
        verbose_name = 'Cliente de pasarela'
        verbose_name_plural = 'Clientes de pasarela'
        unique_together = [('organization', 'proveedor')]

    def __str__(self):
        return f'{self.organization.name} → {self.proveedor}:{self.customer_id}'


class MetodoPago(models.Model):
    """Un medio de pago guardado, como se le muestra a la persona.

    `etiqueta` es lo único que se dibuja en pantalla, y lo arma quien crea la fila
    con lo que la pasarela devolvió: "Visa ···· 4242" en Flow, el correo de la cuenta
    en PayPal. Guardar marca y últimos cuatro en campos separados obligaría a
    inventar un formato para PayPal, que no tiene ni marca ni cuatro dígitos.

    `principal` es con qué se cobra la próxima vez. Lo garantiza `marcar_principal`,
    no el campo: dos principales dejarían el próximo cobro al azar del orden de la
    consulta.
    """

    organization = models.ForeignKey(
        'organizations.Organization', on_delete=models.CASCADE, related_name='metodos_pago'
    )
    proveedor = models.CharField(max_length=20, choices=PROVEEDOR_CHOICES)
    etiqueta = models.CharField(max_length=120)
    # Con qué lo vuelve a cobrar la pasarela. En Flow es el customerId con tarjeta
    # registrada; en PayPal, el id de la suscripción que la persona aprobó.
    token_pasarela = models.CharField(max_length=200, blank=True)
    principal = models.BooleanField(default=False)
    creado_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'metodos_pago'
        verbose_name = 'Medio de pago'
        verbose_name_plural = 'Medios de pago'
        ordering = ['-principal', '-creado_at']

    def __str__(self):
        return f'{self.organization.name} — {self.etiqueta}'

    def marcar_principal(self):
        """Este pasa a ser el principal y los demás dejan de serlo, en un solo lugar."""
        MetodoPago.objects.filter(organization=self.organization).exclude(pk=self.pk).update(
            principal=False
        )
        if not self.principal:
            self.principal = True
            self.save(update_fields=['principal'])


class Subscription(models.Model):
    ESTADO_PRUEBA = 'trial'
    ESTADO_ACTIVA = 'active'
    ESTADO_SUSPENDIDA = 'suspended'
    ESTADO_CANCELADA = 'cancelled'
    STATUS_CHOICES = [
        (ESTADO_PRUEBA, 'En prueba'),
        (ESTADO_ACTIVA, 'Activa'),
        (ESTADO_SUSPENDIDA, 'Suspendida'),
        (ESTADO_CANCELADA, 'Cancelada'),
    ]
    # Los dos estados en los que la empresa tiene derecho a usar el producto. Se
    # consulta en varios lados y tenerlo escrito una vez evita que una consulta se
    # olvide de 'trial' y le corte el acceso a quien está probando.
    ESTADOS_VIGENTES = [ESTADO_PRUEBA, ESTADO_ACTIVA]

    organization = models.ForeignKey(
        'organizations.Organization', on_delete=models.CASCADE, related_name='subscriptions'
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='subscriptions')
    proveedor = models.CharField(max_length=20, choices=PROVEEDOR_CHOICES, default=PROVEEDOR_FLOW)
    moneda = models.CharField(max_length=3, default=MONEDA_CLP)
    # El id que le puso la pasarela. Uno solo para las dos: una suscripción vive en
    # una pasarela y nada más, así que dos columnas dejarían siempre una vacía.
    id_externo = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=ESTADO_PRUEBA)
    # Mientras la pasarela no confirme, la suscripción existe pero no da acceso.
    aprobada = models.BooleanField(default=False)
    trial_end = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'subscriptions'
        verbose_name = 'Suscripción'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.organization.name} — {self.plan.name} ({self.status})'

    @property
    def vigente(self):
        return self.status in self.ESTADOS_VIGENTES and self.aprobada


class Payment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('paid', 'Pagado'),
        ('rejected', 'Rechazado'),
        ('cancelled', 'Cancelado'),
    ]

    organization = models.ForeignKey(
        'organizations.Organization', on_delete=models.CASCADE, related_name='payments'
    )
    subscription = models.ForeignKey(
        Subscription, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments'
    )
    proveedor = models.CharField(max_length=20, choices=PROVEEDOR_CHOICES, default=PROVEEDOR_FLOW)
    moneda = models.CharField(max_length=3, default=MONEDA_CLP)
    # El token de Flow o el id del cobro de PayPal: con qué se le pregunta a la
    # pasarela por este cobro.
    referencia_pasarela = models.CharField(max_length=200, blank=True)
    commerce_order = models.CharField(max_length=50, unique=True)
    amount = models.IntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    subject = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payments'
        verbose_name = 'Pago'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.commerce_order} — {self.status}'

    @classmethod
    def generate_commerce_order(cls):
        # `AFA-` y no `VEL-`: el prefijo viejo era de Velery, y este número queda
        # escrito en la cartola del cliente.
        return f'AFA-{uuid4().hex[:12].upper()}'


class TarifaModelo(models.Model):
    """El precio del proveedor para un modelo, en US$ por millón de tokens.

    Existe para que un cambio de precio sea editar dos números con fecha y no salir a
    buscar constantes por el código. Y para que agregar un modelo sea una fila: el peso
    de un modelo dentro del plan **es** su precio por millón, así que con estos dos
    números queda definido cuánto rinde el cupo del cliente en ese modelo.

    No se borra ni se edita una tarifa vieja: se crea otra con `vigente_desde`
    posterior. El consumo que ya se anotó tiene que seguir explicándose con el precio
    que estaba corriendo ese día.
    """

    modelo = models.CharField(max_length=120)
    proveedor = models.CharField(max_length=20)
    precio_entrada_usd_millon = models.DecimalField(max_digits=10, decimal_places=4)
    precio_salida_usd_millon = models.DecimalField(max_digits=10, decimal_places=4)
    # Los multiplicadores de caché son POR PROVEEDOR, no una constante: en Anthropic
    # leer de caché vale 0,1 de la entrada y en DeepSeek 0,032. Y escribir por una hora
    # cuesta el doble que por cinco minutos, así que van separados. Los valores por
    # omisión son los de Anthropic, que es el proveedor del chat.
    factor_cache_lectura = models.DecimalField(max_digits=6, decimal_places=4, default=Decimal('0.1'))
    factor_cache_escritura = models.DecimalField(max_digits=6, decimal_places=4, default=Decimal('1.25'))
    factor_cache_escritura_1h = models.DecimalField(max_digits=6, decimal_places=4, default=Decimal('2'))
    vigente_desde = models.DateTimeField()
    notas = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = 'tarifas_modelo'
        verbose_name = 'Tarifa de modelo'
        verbose_name_plural = 'Tarifas de modelo'
        ordering = ['modelo', '-vigente_desde']
        indexes = [models.Index(fields=['modelo', '-vigente_desde'])]

    def __str__(self):
        return (f'{self.modelo}: US${self.precio_entrada_usd_millon}/'
                f'{self.precio_salida_usd_millon} por millón')

    @classmethod
    def vigente_para(cls, modelo, momento=None):
        """La tarifa que corre hoy para ese modelo, o None si nadie la cargó."""
        from django.utils import timezone

        return (
            cls.objects
            .filter(modelo=(modelo or '').strip().lower(),
                    vigente_desde__lte=momento or timezone.now())
            .order_by('-vigente_desde')
            .first()
        )


class ConsumoTokens(models.Model):
    """Una fila por llamada a la API de un modelo. La escribe `services/consumo.py`.

    Por llamada y no por mensaje: una pregunta con herramientas conectadas puede dar
    ocho vueltas al modelo, y el costo es la suma de las ocho. Agrupar por mensaje
    escondería el crecimiento que se quiere medir.

    `organization` es opcional porque el chat de la landing lo usa un visitante que
    todavía no es empresa. Ese gasto existe igual y tiene que quedar anotado, aunque no
    se le cobre a nadie.

    `sin_tarifa` marca las llamadas de un modelo al que nadie le cargó precio. Se anotan
    con 0 créditos, y la marca es para que aparezcan como una cifra que falta en vez de
    como consumo que no ocurrió.
    """

    organization = models.ForeignKey(
        'organizations.Organization', on_delete=models.CASCADE,
        related_name='consumos', null=True, blank=True,
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        related_name='consumos', null=True, blank=True,
    )
    proveedor = models.CharField(max_length=20)
    modelo = models.CharField(max_length=120)
    # De dónde salió la llamada: 'chat', 'agente', 'resumen', 'automatizacion', 'lead'.
    # Sirve para responder "¿en qué se me fue el cupo?", que es la primera pregunta que
    # hace alguien cuando ve el número.
    motivo = models.CharField(max_length=40, blank=True)
    # Une las filas de UNA MISMA pregunta del usuario. Sin esto se puede sumar el gasto
    # pero no se puede contestar cuántas vueltas dio una pregunta, que es la cifra que
    # dice si el bucle de herramientas se está yendo de las manos.
    turno = models.CharField(max_length=32, blank=True, db_index=True)
    tokens_entrada = models.IntegerField(default=0)
    tokens_salida = models.IntegerField(default=0)
    tokens_cache_lectura = models.IntegerField(default=0)
    tokens_cache_escritura = models.IntegerField(default=0)
    # La parte del total escrito que se guardó por una hora. Se anota aparte porque
    # cuesta el doble que la de cinco minutos.
    tokens_cache_escritura_1h = models.IntegerField(default=0)
    creditos = models.BigIntegerField(default=0)
    sin_tarifa = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'consumo_tokens'
        verbose_name = 'Consumo de tokens'
        verbose_name_plural = 'Consumos de tokens'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', '-created_at']),
            models.Index(fields=['modelo']),
        ]

    def __str__(self):
        return f'{self.modelo} · {self.creditos} créditos'


class SaldoAdicional(models.Model):
    """Créditos comprados aparte del plan. No expiran.

    Se consumen **después** del cupo incluido, no antes: si expiraran o se gastaran
    primero, el cliente que compró un paquete estaría pagando dos veces el mismo mes.
    Cada compra es su propia fila para que el historial quede a la vista; el disponible
    es la suma.
    """

    organization = models.ForeignKey(
        'organizations.Organization', on_delete=models.CASCADE, related_name='saldos_adicionales',
    )
    creditos_comprados = models.BigIntegerField()
    creditos_usados = models.BigIntegerField(default=0)
    payment = models.ForeignKey(
        Payment, on_delete=models.SET_NULL, related_name='saldos', null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'saldos_adicionales'
        verbose_name = 'Saldo adicional'
        verbose_name_plural = 'Saldos adicionales'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.organization.name}: {self.disponible} créditos disponibles'

    @property
    def disponible(self):
        return max(self.creditos_comprados - self.creditos_usados, 0)

    @classmethod
    def disponible_de(cls, organization):
        from django.db.models import F, Sum

        total = (
            cls.objects
            .filter(organization=organization)
            .aggregate(t=Sum(F('creditos_comprados') - F('creditos_usados')))['t']
        )
        return max(total or 0, 0)

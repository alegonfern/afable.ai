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

from uuid import uuid4

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

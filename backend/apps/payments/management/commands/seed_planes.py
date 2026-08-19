"""Los planes de Afable con su precio en las dos monedas.

Se corre en cada despliegue (es idempotente): los precios y los límites viven acá y no
en la base a mano, para que no haya un ambiente cobrando otro número. Lo que NO toca es
`is_active`, así que un plan retirado desde el admin no revive solo.

El precio en dólares es de lista, no una conversión: US$99 donde en Chile son $99.000.
Al tipo de cambio serían ~104, y un precio que se mueve con el dólar no se puede poner en
una página de precios.
"""

from django.core.management.base import BaseCommand

from apps.payments.models import Plan

PLANES = [
    {
        'id': 'afable_starter_monthly',
        'name': 'Starter',
        'price_clp': 99_000,
        'price_usd': 99,
        'max_agents': 3,
        'max_integrations': 10,
        'queries_per_month': 5_000,
        'max_usuarios': 3,
        # 25 millones de créditos = US$25 de costo del proveedor en el peor caso, sobre
        # US$99 de precio: 75% de margen. Sale de la fórmula (3 asientos × US$18 + 25
        # millones × US$1,80 el millón = 99).
        'tokens_por_mes': 25_000_000,
    },
    {
        'id': 'afable_growth_monthly',
        'name': 'Growth',
        'price_clp': 299_000,
        'price_usd': 299,
        'max_agents': 15,
        'max_integrations': 50,
        'queries_per_month': 50_000,
        'max_usuarios': 5,
        # 5 × US$18 + 150 millones × US$1,39 = 299. Queda 23% más barato por crédito que
        # Starter, y el descuento lo financian los dos asientos extra, no el margen.
        'tokens_por_mes': 150_000_000,
    },
    {
        # Sin precio y sin pasarela: se conversa. `es_a_medida` es lo que hace que la
        # pantalla ofrezca "hablemos" en vez de un botón de pago por $0.
        'id': 'afable_enterprise_monthly',
        'name': 'Enterprise',
        'price_clp': 0,
        'price_usd': 0,
        'es_a_medida': True,
        'max_agents': 0,
        'max_integrations': 0,
        'queries_per_month': 0,
        # A medida: los asientos y el cupo se pactan y se cargan a mano, con piso en el
        # precio de Growth.
        'max_usuarios': 0,
        'tokens_por_mes': 0,
    },
]


class Command(BaseCommand):
    help = 'Crea o actualiza los planes de Afable con sus precios en CLP y USD.'

    def handle(self, *args, **options):
        for datos in PLANES:
            plan_id = datos.pop('id')
            plan, creado = Plan.objects.update_or_create(id=plan_id, defaults=datos)
            self.stdout.write(
                f'{"creado " if creado else "al día"} · {plan.name}: '
                f'${plan.price_clp:,} CLP / US${plan.price_usd}'
                + (' (a medida)' if plan.es_a_medida else '')
            )

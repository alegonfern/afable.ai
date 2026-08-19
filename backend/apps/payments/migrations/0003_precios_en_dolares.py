"""Los planes que ya están en la base pasan a tener precio en dólares y su marca.

Hacía falta una migración de datos y no sólo el comando `seed_planes`: la migración
`0001_initial` ya había insertado los tres planes, y con `price_usd=0` y
`es_a_medida=False` **Enterprise quedaba como un plan cobrable de $0** — alguien lo
contrataba, la pasarela cobraba nada, y la empresa quedaba "suscrita" sin servicio.

Los números van escritos acá a mano, aunque el comando `seed_planes` tenga los mismos.
Una migración es una foto de un momento: si importara la lista del comando, cambiar un
precio mañana cambiaría lo que esta migración hizo ayer, y dos bases con la misma
historia terminarían distintas.
"""

from django.db import migrations

PRECIOS = {
    'afable_starter_monthly': {'price_usd': 99, 'es_a_medida': False},
    'afable_growth_monthly': {'price_usd': 299, 'es_a_medida': False},
    'afable_enterprise_monthly': {'price_usd': 0, 'es_a_medida': True},
}


def poner_precios(apps, schema_editor):
    Plan = apps.get_model('payments', 'Plan')
    for plan_id, datos in PRECIOS.items():
        Plan.objects.filter(id=plan_id).update(**datos)


def quitar_precios(apps, schema_editor):
    Plan = apps.get_model('payments', 'Plan')
    Plan.objects.filter(id__in=PRECIOS).update(price_usd=0, es_a_medida=False)


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0002_facturacion_por_workspace'),
    ]

    operations = [
        migrations.RunPython(poner_precios, quitar_precios),
    ]

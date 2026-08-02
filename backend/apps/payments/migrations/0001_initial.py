from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def insert_plans(apps, schema_editor):
    Plan = apps.get_model('payments', 'Plan')
    Plan.objects.bulk_create([
        Plan(
            id='afable_starter_monthly',
            name='Starter',
            price_clp=99000,
            max_agents=3,
            max_integrations=10,
            queries_per_month=5000,
            is_active=True,
        ),
        Plan(
            id='afable_growth_monthly',
            name='Growth',
            price_clp=299000,
            max_agents=0,
            max_integrations=50,
            queries_per_month=50000,
            is_active=True,
        ),
        Plan(
            id='afable_enterprise_monthly',
            name='Enterprise',
            price_clp=0,
            max_agents=0,
            max_integrations=0,
            queries_per_month=0,
            is_active=True,
        ),
    ])


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Plan',
            fields=[
                ('id', models.CharField(max_length=100, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
                ('price_clp', models.IntegerField()),
                ('max_agents', models.IntegerField(default=0)),
                ('max_integrations', models.IntegerField(default=0)),
                ('queries_per_month', models.IntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={'db_table': 'payment_plans', 'verbose_name': 'Plan'},
        ),
        migrations.CreateModel(
            name='FlowCustomer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('flow_customer_id', models.CharField(max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='flow_customer',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'db_table': 'flow_customers', 'verbose_name': 'Cliente Flow'},
        ),
        migrations.CreateModel(
            name='Subscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('flow_subscription_id', models.CharField(blank=True, max_length=100)),
                ('status', models.CharField(
                    choices=[
                        ('trial', 'Trial'),
                        ('active', 'Activa'),
                        ('suspended', 'Suspendida'),
                        ('cancelled', 'Cancelada'),
                    ],
                    default='trial',
                    max_length=20,
                )),
                ('trial_end', models.DateTimeField(blank=True, null=True)),
                ('current_period_end', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('plan', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='subscriptions',
                    to='payments.plan',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='subscriptions',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'db_table': 'subscriptions', 'verbose_name': 'Suscripción', 'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='Payment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('flow_token', models.CharField(blank=True, max_length=200)),
                ('commerce_order', models.CharField(max_length=50, unique=True)),
                ('amount', models.IntegerField()),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pendiente'),
                        ('paid', 'Pagado'),
                        ('rejected', 'Rechazado'),
                        ('cancelled', 'Cancelado'),
                    ],
                    default='pending',
                    max_length=20,
                )),
                ('subject', models.CharField(max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('subscription', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='payments',
                    to='payments.subscription',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='payments',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'db_table': 'payments', 'verbose_name': 'Pago', 'ordering': ['-created_at']},
        ),
        migrations.RunPython(insert_plans, migrations.RunPython.noop),
    ]

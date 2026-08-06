"""La facturación pasa de la persona al Workspace.

Se BORRAN y se vuelven a crear `Subscription` y `Payment` en vez de renombrar campo por
campo. Las tres tablas estaban vacías (0 suscripciones, 0 pagos, 0 clientes) y nada de
esto está en producción, así que no hay dato que preservar; una cadena de
Remove/Add/Alter para llegar al mismo lugar sería más larga y más difícil de leer dentro
de un año.

`FlowCustomer` desaparece: lo reemplaza `ClientePasarela`, que sirve para las dos
pasarelas.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspaces', '0008_workspace_logo'),
        ('payments', '0001_initial'),
    ]

    operations = [
        # ── Fuera lo viejo ────────────────────────────────────────────────────────
        migrations.DeleteModel(name='Payment'),
        migrations.DeleteModel(name='Subscription'),
        migrations.DeleteModel(name='FlowCustomer'),

        # ── El plan gana su precio en dólares ─────────────────────────────────────
        migrations.AddField(
            model_name='plan',
            name='price_usd',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='plan',
            name='es_a_medida',
            field=models.BooleanField(default=False),
        ),

        # ── Lo nuevo, colgado del Workspace ───────────────────────────────────────
        migrations.CreateModel(
            name='ClientePasarela',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('proveedor', models.CharField(choices=[('flow', 'Flow (CLP)'), ('paypal', 'PayPal (USD)')], max_length=20)),
                ('customer_id', models.CharField(max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('workspace', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='clientes_pasarela', to='workspaces.workspace')),
            ],
            options={
                'verbose_name': 'Cliente de pasarela',
                'verbose_name_plural': 'Clientes de pasarela',
                'db_table': 'clientes_pasarela',
                'unique_together': {('workspace', 'proveedor')},
            },
        ),
        migrations.CreateModel(
            name='MetodoPago',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('proveedor', models.CharField(choices=[('flow', 'Flow (CLP)'), ('paypal', 'PayPal (USD)')], max_length=20)),
                ('etiqueta', models.CharField(max_length=120)),
                ('token_pasarela', models.CharField(blank=True, max_length=200)),
                ('principal', models.BooleanField(default=False)),
                ('creado_at', models.DateTimeField(auto_now_add=True)),
                ('workspace', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='metodos_pago', to='workspaces.workspace')),
            ],
            options={
                'verbose_name': 'Medio de pago',
                'verbose_name_plural': 'Medios de pago',
                'db_table': 'metodos_pago',
                'ordering': ['-principal', '-creado_at'],
            },
        ),
        migrations.CreateModel(
            name='Subscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('proveedor', models.CharField(choices=[('flow', 'Flow (CLP)'), ('paypal', 'PayPal (USD)')], default='flow', max_length=20)),
                ('moneda', models.CharField(default='CLP', max_length=3)),
                ('id_externo', models.CharField(blank=True, max_length=200)),
                ('status', models.CharField(choices=[('trial', 'En prueba'), ('active', 'Activa'), ('suspended', 'Suspendida'), ('cancelled', 'Cancelada')], default='trial', max_length=20)),
                ('aprobada', models.BooleanField(default=False)),
                ('trial_end', models.DateTimeField(blank=True, null=True)),
                ('current_period_end', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('plan', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='subscriptions', to='payments.plan')),
                ('workspace', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='subscriptions', to='workspaces.workspace')),
            ],
            options={
                'verbose_name': 'Suscripción',
                'db_table': 'subscriptions',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Payment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('proveedor', models.CharField(choices=[('flow', 'Flow (CLP)'), ('paypal', 'PayPal (USD)')], default='flow', max_length=20)),
                ('moneda', models.CharField(default='CLP', max_length=3)),
                ('referencia_pasarela', models.CharField(blank=True, max_length=200)),
                ('commerce_order', models.CharField(max_length=50, unique=True)),
                ('amount', models.IntegerField()),
                ('status', models.CharField(choices=[('pending', 'Pendiente'), ('paid', 'Pagado'), ('rejected', 'Rechazado'), ('cancelled', 'Cancelado')], default='pending', max_length=20)),
                ('subject', models.CharField(max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('subscription', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='payments', to='payments.subscription')),
                ('workspace', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payments', to='workspaces.workspace')),
            ],
            options={
                'verbose_name': 'Pago',
                'db_table': 'payments',
                'ordering': ['-created_at'],
            },
        ),
    ]

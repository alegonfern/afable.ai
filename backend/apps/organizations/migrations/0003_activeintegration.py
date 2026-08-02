from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0002_integrationscan'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ActiveIntegration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('integration_type', models.CharField(choices=[('dummyjson', 'DummyJSON Store'), ('sheets', 'Google Sheets'), ('notion', 'Notion'), ('postgres', 'PostgreSQL')], max_length=50)),
                ('is_active', models.BooleanField(default=True)),
                ('connected_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='active_integrations', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'active_integrations',
                'unique_together': {('user', 'integration_type')},
            },
        ),
    ]

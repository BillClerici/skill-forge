# Initial migration for subscriptions app

from django.db import migrations, models
import uuid
from decimal import Decimal


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Subscription',
            fields=[
                ('subscription_id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)),
                ('account_id', models.UUIDField()),
                ('tier', models.CharField(max_length=50)),
                ('status', models.CharField(max_length=20)),
                ('billing_cycle', models.CharField(max_length=20, null=True, blank=True)),
                ('max_players', models.IntegerField(default=1)),
                ('max_characters_per_player', models.IntegerField(default=3)),
                ('max_campaigns', models.IntegerField(default=1)),
                ('price_per_month', models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))),
                ('currency', models.CharField(max_length=3, default='USD')),
                ('stripe_subscription_id', models.CharField(max_length=100, null=True, blank=True)),
                ('stripe_customer_id', models.CharField(max_length=100, null=True, blank=True)),
                ('start_date', models.DateTimeField()),
                ('end_date', models.DateTimeField(null=True, blank=True)),
                ('trial_end_date', models.DateTimeField(null=True, blank=True)),
                ('next_billing_date', models.DateTimeField(null=True, blank=True)),
                ('cancelled_at', models.DateTimeField(null=True, blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'subscriptions',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Invoice',
            fields=[
                ('invoice_id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)),
                ('subscription_id', models.UUIDField()),
                ('account_id', models.UUIDField()),
                ('invoice_number', models.CharField(max_length=50, unique=True)),
                ('amount', models.DecimalField(max_digits=10, decimal_places=2)),
                ('tax', models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))),
                ('total', models.DecimalField(max_digits=10, decimal_places=2)),
                ('currency', models.CharField(max_length=3, default='USD')),
                ('status', models.CharField(max_length=20)),
                ('stripe_invoice_id', models.CharField(max_length=100, null=True, blank=True)),
                ('stripe_payment_intent_id', models.CharField(max_length=100, null=True, blank=True)),
                ('billing_period_start', models.DateTimeField()),
                ('billing_period_end', models.DateTimeField()),
                ('due_date', models.DateTimeField()),
                ('paid_at', models.DateTimeField(null=True, blank=True)),
                ('payment_method', models.CharField(max_length=50, null=True, blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'invoices',
                'ordering': ['-created_at'],
            },
        ),
    ]

"""
Subscription and Invoice models for SkillForge
Tracks subscription history and billing
"""
import uuid
from django.db import models
from decimal import Decimal


class Subscription(models.Model):
    """Subscription history for accounts"""
    subscription_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account_id = models.UUIDField()

    # Subscription details
    tier = models.CharField(
        max_length=50,
        choices=[
            ('free', 'Free'),
            ('individual', 'Individual'),
            ('family', 'Family'),
            ('educator', 'Educator'),
            ('premium', 'Premium'),
            ('enterprise', 'Enterprise'),
        ]
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('trial', 'Trial'),
            ('active', 'Active'),
            ('past_due', 'Past Due'),
            ('cancelled', 'Cancelled'),
            ('suspended', 'Suspended'),
            ('expired', 'Expired'),
        ]
    )
    billing_cycle = models.CharField(
        max_length=20,
        choices=[
            ('monthly', 'Monthly'),
            ('annual', 'Annual'),
        ],
        null=True,
        blank=True
    )

    # Player limits
    max_players = models.IntegerField(default=1)
    max_characters_per_player = models.IntegerField(default=3)
    max_campaigns = models.IntegerField(default=1)

    # Pricing
    price_per_month = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    currency = models.CharField(max_length=3, default='USD')

    # Stripe integration
    stripe_subscription_id = models.CharField(max_length=100, null=True, blank=True)
    stripe_customer_id = models.CharField(max_length=100, null=True, blank=True)

    # Dates
    start_date = models.DateTimeField()
    end_date = models.DateTimeField(null=True, blank=True)
    trial_end_date = models.DateTimeField(null=True, blank=True)
    next_billing_date = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'subscriptions'
        managed = False
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.tier.title()} - {self.status}"


class Invoice(models.Model):
    """Invoice history for subscriptions"""
    invoice_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription_id = models.UUIDField()
    account_id = models.UUIDField()

    # Invoice details
    invoice_number = models.CharField(max_length=50, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')

    status = models.CharField(
        max_length=20,
        choices=[
            ('draft', 'Draft'),
            ('pending', 'Pending'),
            ('paid', 'Paid'),
            ('failed', 'Failed'),
            ('refunded', 'Refunded'),
            ('void', 'Void'),
        ]
    )

    # Stripe integration
    stripe_invoice_id = models.CharField(max_length=100, null=True, blank=True)
    stripe_payment_intent_id = models.CharField(max_length=100, null=True, blank=True)

    # Dates
    billing_period_start = models.DateTimeField()
    billing_period_end = models.DateTimeField()
    due_date = models.DateTimeField()
    paid_at = models.DateTimeField(null=True, blank=True)

    # Payment details
    payment_method = models.CharField(max_length=50, null=True, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'invoices'
        managed = False
        ordering = ['-created_at']

    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.status}"

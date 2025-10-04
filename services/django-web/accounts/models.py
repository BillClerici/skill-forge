"""
Account models for SkillForge
Using existing PostgreSQL tables with managed=False
"""
import uuid
from django.db import models


class Account(models.Model):
    """Account model - maps to existing accounts table"""
    account_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, null=True, blank=True)
    account_owner_player_id = models.UUIDField(null=True, blank=True)
    account_type = models.CharField(
        max_length=50,
        choices=[
            ('individual', 'Individual'),
            ('family', 'Family'),
            ('educational', 'Educational'),
            ('organizational', 'Organizational'),
        ]
    )
    subscription_tier = models.CharField(max_length=50, null=True, blank=True)
    subscription_status = models.CharField(
        max_length=20,
        default='active',
        choices=[
            ('active', 'Active'),
            ('past_due', 'Past Due'),
            ('cancelled', 'Cancelled'),
            ('suspended', 'Suspended'),
        ]
    )
    billing_cycle = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        choices=[
            ('monthly', 'Monthly'),
            ('annual', 'Annual'),
        ]
    )
    subscription_start_date = models.DateField(null=True, blank=True)
    next_billing_date = models.DateField(null=True, blank=True)
    max_players = models.IntegerField(default=1)
    current_player_count = models.IntegerField(default=1)
    stripe_customer_id = models.CharField(max_length=100, null=True, blank=True)
    stripe_subscription_id = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'accounts'
        managed = False  # Don't let Django manage this table

    def __str__(self):
        return f"{self.account_type.title()} Account ({self.account_id})"

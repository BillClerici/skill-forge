"""
Admin configuration for Accounts
"""
from django.contrib import admin
from .models import Account


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ['account_id', 'account_type', 'subscription_tier', 'subscription_status', 'current_member_count', 'created_at']
    list_filter = ['account_type', 'subscription_status', 'subscription_tier']
    search_fields = ['account_id', 'stripe_customer_id']
    readonly_fields = ['account_id', 'created_at', 'updated_at']

    fieldsets = (
        ('Basic Information', {
            'fields': ('account_id', 'account_type', 'account_owner_member_id')
        }),
        ('Subscription', {
            'fields': ('subscription_tier', 'subscription_status', 'billing_cycle',
                      'subscription_start_date', 'next_billing_date')
        }),
        ('Members', {
            'fields': ('max_members', 'current_member_count')
        }),
        ('Payment', {
            'fields': ('stripe_customer_id', 'stripe_subscription_id')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

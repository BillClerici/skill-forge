"""
Admin configuration for Players
"""
from django.contrib import admin
from .models import Player


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ['player_id', 'display_name', 'role', 'age', 'email', 'is_active', 'created_at']
    list_filter = ['role', 'is_active', 'content_restriction_level']
    search_fields = ['player_id', 'display_name', 'email']
    readonly_fields = ['player_id', 'created_at', 'updated_at', 'age']

    fieldsets = (
        ('Basic Information', {
            'fields': ('player_id', 'account_id', 'display_name', 'email', 'date_of_birth', 'age')
        }),
        ('Role & Permissions', {
            'fields': ('role', 'can_manage_account', 'can_manage_players', 'can_view_billing')
        }),
        ('Content Restrictions', {
            'fields': ('content_restriction_level', 'allowed_universes', 'blocked_universes'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

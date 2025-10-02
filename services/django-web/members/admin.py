"""
Admin configuration for Members
"""
from django.contrib import admin
from .models import Member


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ['member_id', 'display_name', 'role', 'age', 'email', 'is_active', 'created_at']
    list_filter = ['role', 'is_active', 'content_restriction_level']
    search_fields = ['member_id', 'display_name', 'email']
    readonly_fields = ['member_id', 'created_at', 'updated_at', 'age']

    fieldsets = (
        ('Basic Information', {
            'fields': ('member_id', 'account_id', 'display_name', 'email', 'date_of_birth', 'age')
        }),
        ('Role & Permissions', {
            'fields': ('role', 'can_manage_account', 'can_manage_members', 'can_view_billing')
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

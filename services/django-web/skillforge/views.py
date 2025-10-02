"""
Main views for SkillForge
"""
from django.shortcuts import render
from accounts.models import Account
from members.models import Member


def dashboard(request):
    """Dashboard homepage"""
    context = {
        'total_accounts': Account.objects.count(),
        'total_members': Member.objects.count(),
        'recent_accounts': Account.objects.order_by('-created_at')[:5],
        'recent_members': Member.objects.order_by('-created_at')[:5],
    }
    return render(request, 'dashboard.html', context)

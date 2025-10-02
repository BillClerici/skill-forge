"""
Account views for SkillForge
"""
from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, DetailView
from .models import Account


class AccountListView(ListView):
    model = Account
    template_name = 'accounts/account_list.html'
    context_object_name = 'accounts'
    paginate_by = 20

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_accounts'] = Account.objects.count()
        return context


class AccountDetailView(DetailView):
    model = Account
    template_name = 'accounts/account_detail.html'
    context_object_name = 'account'
    slug_field = 'account_id'
    slug_url_kwarg = 'account_id'

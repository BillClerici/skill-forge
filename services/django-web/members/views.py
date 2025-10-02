"""
Member views for SkillForge
"""
from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, DetailView
from .models import Member
from accounts.models import Account


class MemberListView(ListView):
    model = Member
    template_name = 'members/member_list.html'
    context_object_name = 'members'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()
        account_id = self.request.GET.get('account')
        if account_id:
            queryset = queryset.filter(account_id=account_id)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_members'] = Member.objects.count()
        return context


class MemberDetailView(DetailView):
    model = Member
    template_name = 'members/member_detail.html'
    context_object_name = 'member'
    slug_field = 'member_id'
    slug_url_kwarg = 'member_id'

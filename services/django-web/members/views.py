"""
Player views for SkillForge
"""
from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, DetailView
from .models import Player
from .models_profile import PlayerProfile
from accounts.models import Account


class PlayerListView(ListView):
    model = Player
    template_name = 'players/player_list.html'
    context_object_name = 'players'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()
        account_id = self.request.GET.get('account')
        if account_id:
            queryset = queryset.filter(account_id=account_id)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_players'] = Player.objects.count()
        return context


class PlayerDetailView(DetailView):
    model = Player
    template_name = 'players/player_detail.html'
    context_object_name = 'player'
    slug_field = 'player_id'
    slug_url_kwarg = 'player_id'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        player = self.get_object()
        # Get the account for the back link
        try:
            context['account'] = Account.objects.get(account_id=player.account_id)
        except Account.DoesNotExist:
            context['account'] = None
        # Get the player profile if it exists
        try:
            context['profile'] = PlayerProfile.objects.get(player_id=player.player_id)
        except PlayerProfile.DoesNotExist:
            context['profile'] = None
        # Get characters for this player
        from characters.models import Character
        context['characters'] = Character.objects.filter(player_id=player.player_id)
        return context

"""
Player Profile views for SkillForge
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import View
from django.contrib import messages
from django.db import transaction
from .models import Player
from .forms_profile import PlayerProfileForm


class PlayerProfileConfigView(View):
    """Configure or update player preferences and settings"""

    def get(self, request, player_id):
        player = get_object_or_404(Player, player_id=player_id)
        form = PlayerProfileForm(instance=player)

        return render(request, 'players/profile_config.html', {
            'form': form,
            'player': player,
            'is_create': False,
        })

    @transaction.atomic
    def post(self, request, player_id):
        player = get_object_or_404(Player, player_id=player_id)
        form = PlayerProfileForm(request.POST, instance=player)

        if form.is_valid():
            form.save()
            messages.success(request, f'Player settings updated successfully for {player.display_name}!')
            return redirect('player_detail', player_id=player_id)

        return render(request, 'players/profile_config.html', {
            'form': form,
            'player': player,
            'is_create': False,
        })

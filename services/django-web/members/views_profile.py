"""
Player Profile views for SkillForge
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import View
from django.contrib import messages
from django.db import transaction
from .models import Player
from .models_profile import PlayerProfile
from .forms_profile import PlayerProfileForm


class PlayerProfileConfigView(View):
    """Configure or update player profile preferences"""

    def get(self, request, player_id):
        player = get_object_or_404(Player, player_id=player_id)

        # Try to get existing profile or create new instance
        try:
            profile = PlayerProfile.objects.get(player_id=player_id)
            is_create = False
        except PlayerProfile.DoesNotExist:
            profile = PlayerProfile(player_id=player_id)
            is_create = True

        form = PlayerProfileForm(instance=profile)

        return render(request, 'players/profile_config.html', {
            'form': form,
            'player': player,
            'profile': profile if not is_create else None,
            'is_create': is_create,
        })

    @transaction.atomic
    def post(self, request, player_id):
        player = get_object_or_404(Player, player_id=player_id)

        # Try to get existing profile
        try:
            profile = PlayerProfile.objects.get(player_id=player_id)
            is_create = False
        except PlayerProfile.DoesNotExist:
            profile = PlayerProfile(player_id=player_id)
            is_create = True

        form = PlayerProfileForm(request.POST, instance=profile)

        if form.is_valid():
            profile = form.save(commit=False)
            profile.player_id = player_id
            profile.save()

            if is_create:
                messages.success(request, f'Player profile created successfully for {player.display_name}!')
            else:
                messages.success(request, f'Player profile updated successfully for {player.display_name}!')

            return redirect('player_detail', player_id=player_id)

        return render(request, 'players/profile_config.html', {
            'form': form,
            'player': player,
            'profile': profile,
            'is_create': is_create,
        })

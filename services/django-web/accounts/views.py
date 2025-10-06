"""
Account views for SkillForge
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.db import transaction
from .models import Account
from .forms import AccountCreateForm, AccountEditForm, PlayerCreateForm, PlayerEditForm
from members.models import Player
from subscriptions.models import Subscription, Invoice


class AccountListView(ListView):
    model = Account
    template_name = 'accounts/account_list.html'
    context_object_name = 'accounts'
    paginate_by = 20

    def get_queryset(self):
        # Get accounts with owner player info
        accounts = Account.objects.all()
        # Attach owner player to each account
        for account in accounts:
            if account.account_owner_player_id:
                try:
                    account.owner_player = Player.objects.get(player_id=account.account_owner_player_id)
                except Player.DoesNotExist:
                    account.owner_player = None
            else:
                account.owner_player = None
        return accounts

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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        account = self.get_object()

        # Get all players for this account
        players = Player.objects.filter(account_id=account.account_id).order_by('-created_at')
        context['players'] = players
        context['primary_players'] = players.filter(role='owner')

        # Get subscription history
        subscriptions = Subscription.objects.filter(account_id=account.account_id)
        context['subscriptions'] = subscriptions
        context['active_subscription'] = subscriptions.filter(status='active').first()

        # Get recent invoices
        invoices = Invoice.objects.filter(account_id=account.account_id)[:10]
        context['invoices'] = invoices

        return context


class AccountCreateView(View):
    """Create a new account with primary player"""

    def get(self, request):
        form = AccountCreateForm()
        return render(request, 'accounts/account_form.html', {
            'form': form,
            'is_create': True
        })

    @transaction.atomic
    def post(self, request):
        form = AccountCreateForm(request.POST)

        if form.is_valid():
            # Create account
            account = form.save(commit=False)
            account.current_player_count = 1
            account.save()

            # Create primary player
            primary_player = Player.objects.create(
                account_id=account.account_id,
                display_name=form.cleaned_data['primary_player_name'],
                email=form.cleaned_data.get('primary_player_email'),
                date_of_birth=form.cleaned_data['primary_player_dob'],
                role='owner',
                can_manage_account=True,
                can_manage_players=True,
                can_view_billing=True,
                is_active=True
            )

            # Set account owner
            account.account_owner_player_id = primary_player.player_id
            account.save()

            messages.success(request, f'Account created successfully with primary player "{primary_player.display_name}"!')
            return redirect('account_detail', account_id=account.account_id)

        return render(request, 'accounts/account_form.html', {
            'form': form,
            'is_create': True
        })


class AccountUpdateView(View):
    """Update account details"""

    def get(self, request, account_id):
        account = get_object_or_404(Account, account_id=account_id)
        form = AccountEditForm(instance=account)
        return render(request, 'accounts/account_form.html', {
            'form': form,
            'account': account,
            'is_create': False
        })

    def post(self, request, account_id):
        account = get_object_or_404(Account, account_id=account_id)
        form = AccountEditForm(request.POST, instance=account)

        if form.is_valid():
            form.save()
            messages.success(request, f'Account updated successfully!')
            return redirect('account_detail', account_id=account.account_id)

        return render(request, 'accounts/account_form.html', {
            'form': form,
            'account': account,
            'is_create': False
        })


class AccountDeleteView(View):
    """Delete an account and all associated players"""

    def post(self, request, account_id):
        account = get_object_or_404(Account, account_id=account_id)
        account_name = str(account.account_id)

        # Delete all players in the account
        Player.objects.filter(account_id=account_id).delete()

        # Delete the account
        account.delete()

        messages.success(request, f'Account "{account_name}" and all associated players have been deleted.')
        return redirect('account_list')


class PlayerCreateView(View):
    """Add a new player to an account"""

    def get(self, request, account_id):
        account = get_object_or_404(Account, account_id=account_id)
        form = PlayerCreateForm()
        return render(request, 'accounts/player_form.html', {
            'form': form,
            'account': account,
            'is_create': True
        })

    @transaction.atomic
    def post(self, request, account_id):
        account = get_object_or_404(Account, account_id=account_id)
        form = PlayerCreateForm(request.POST)

        if form.is_valid():
            # Check if account has reached max players
            current_count = Player.objects.filter(account_id=account_id, is_active=True).count()
            if current_count >= account.max_players:
                messages.error(request, f'This account has reached its maximum of {account.max_players} players. Upgrade your subscription to add more.')
                return redirect('account_detail', account_id=account_id)

            # Create player
            player = form.save(commit=False)
            player.account_id = account.account_id
            player.save()

            # Update player count
            account.current_player_count = Player.objects.filter(account_id=account_id, is_active=True).count()
            account.save()

            messages.success(request, f'Player "{player.display_name}" added successfully!')
            return redirect('account_detail', account_id=account.account_id)

        return render(request, 'accounts/player_form.html', {
            'form': form,
            'account': account,
            'is_create': True
        })


class PlayerUpdateView(View):
    """Update player details"""

    def get(self, request, account_id, player_id):
        account = get_object_or_404(Account, account_id=account_id)
        player = get_object_or_404(Player, player_id=player_id, account_id=account_id)
        form = PlayerEditForm(instance=player)
        return render(request, 'accounts/player_form.html', {
            'form': form,
            'account': account,
            'player': player,
            'is_create': False
        })

    def post(self, request, account_id, player_id):
        account = get_object_or_404(Account, account_id=account_id)
        player = get_object_or_404(Player, player_id=player_id, account_id=account_id)
        form = PlayerEditForm(request.POST, instance=player)

        if form.is_valid():
            # Ensure at least one owner remains
            if player.role == 'owner' and form.cleaned_data.get('role') != 'owner':
                owner_count = Player.objects.filter(account_id=account_id, role='owner').exclude(player_id=player_id).count()
                if owner_count == 0:
                    messages.error(request, 'Cannot remove owner role. At least one owner must exist.')
                    return redirect('account_player_edit', account_id=account_id, player_id=player_id)

            form.save()
            messages.success(request, f'Player "{player.display_name}" updated successfully!')
            return redirect('player_detail', player_id=player.player_id)

        return render(request, 'accounts/player_form.html', {
            'form': form,
            'account': account,
            'player': player,
            'is_create': False
        })


class PlayerDeleteView(View):
    """Remove a player from an account"""

    def post(self, request, account_id, player_id):
        account = get_object_or_404(Account, account_id=account_id)
        player = get_object_or_404(Player, player_id=player_id, account_id=account_id)

        # Prevent deleting the last owner
        if player.role == 'owner':
            owner_count = Player.objects.filter(account_id=account_id, role='owner').count()
            if owner_count <= 1:
                messages.error(request, 'Cannot delete the last owner. Please designate another owner first.')
                return redirect('account_detail', account_id=account_id)

        player_name = player.display_name
        player.delete()

        # Update player count
        account.current_player_count = Player.objects.filter(account_id=account_id, is_active=True).count()
        account.save()

        messages.success(request, f'Player "{player_name}" has been removed from the account.')
        return redirect('account_detail', account_id=account_id)

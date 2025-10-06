# Initial migration for members app (Players)

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Player',
            fields=[
                ('player_id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)),
                ('account_id', models.UUIDField()),
                ('display_name', models.CharField(max_length=100)),
                ('email', models.EmailField(max_length=255, null=True, blank=True)),
                ('date_of_birth', models.DateField()),
                ('role', models.CharField(max_length=20)),
                ('can_manage_account', models.BooleanField(default=False)),
                ('can_manage_players', models.BooleanField(default=False)),
                ('can_view_billing', models.BooleanField(default=False)),
                ('content_restriction_level', models.CharField(max_length=20, default='automatic')),
                ('allowed_universes', models.JSONField(null=True, blank=True)),
                ('blocked_universes', models.JSONField(null=True, blank=True)),
                ('daily_time_limit_minutes', models.IntegerField(null=True, blank=True)),
                ('weekday_time_limit_minutes', models.IntegerField(null=True, blank=True)),
                ('weekend_time_limit_minutes', models.IntegerField(null=True, blank=True)),
                ('quiet_hours_start', models.TimeField(null=True, blank=True)),
                ('quiet_hours_end', models.TimeField(null=True, blank=True)),
                ('can_play_with_family', models.BooleanField(default=True)),
                ('can_play_with_friends', models.BooleanField(default=False)),
                ('can_play_with_strangers', models.BooleanField(default=False)),
                ('friend_requests_require_approval', models.BooleanField(default=True)),
                ('can_chat_in_family_campaigns', models.BooleanField(default=True)),
                ('can_chat_with_friends', models.BooleanField(default=False)),
                ('can_chat_with_strangers', models.BooleanField(default=False)),
                ('parent_can_view_activity', models.BooleanField(default=True)),
                ('send_weekly_report_to_parent', models.BooleanField(default=True)),
                ('notify_parent_on_new_campaign', models.BooleanField(default=True)),
                ('parent_email_for_notifications', models.EmailField(max_length=255, null=True, blank=True)),
                ('password_hash', models.CharField(max_length=255, null=True, blank=True)),
                ('last_login', models.DateTimeField(null=True, blank=True)),
                ('login_count', models.IntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'players',
            },
        ),
        migrations.CreateModel(
            name='PlayerProfile',
            fields=[
                ('profile_id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)),
                ('player_id', models.UUIDField()),
                ('character_name', models.CharField(max_length=100)),
                ('universe_id', models.UUIDField()),
                ('world_id', models.UUIDField()),
                ('archetype', models.CharField(max_length=100, null=True, blank=True)),
                ('appearance_data', models.JSONField(null=True, blank=True)),
                ('portrait_url', models.CharField(max_length=500, null=True, blank=True)),
                ('world_knowledge_level', models.DecimalField(max_digits=3, decimal_places=2, default=0.00)),
                ('discovered_locations', models.JSONField(null=True, blank=True)),
                ('known_npcs', models.JSONField(null=True, blank=True)),
                ('completed_quests', models.JSONField(null=True, blank=True)),
                ('total_playtime_minutes', models.IntegerField(default=0)),
                ('character_level', models.IntegerField(default=1)),
                ('character_achievements', models.JSONField(null=True, blank=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_played_at', models.DateTimeField(null=True, blank=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'player_profiles',
            },
        ),
    ]

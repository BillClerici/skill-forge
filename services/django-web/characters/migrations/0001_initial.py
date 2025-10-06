# Initial migration for characters app

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Character',
            fields=[
                ('character_id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)),
                ('player_id', models.UUIDField()),
                ('name', models.CharField(max_length=100)),
                ('title', models.CharField(max_length=200, null=True, blank=True)),
                ('description', models.TextField(null=True, blank=True)),
                ('backstory', models.TextField(null=True, blank=True)),
                ('personality_traits', models.JSONField(default=list)),
                ('blooms_level', models.CharField(max_length=20, default='remembering')),
                ('age', models.IntegerField(null=True, blank=True)),
                ('height', models.CharField(max_length=50, null=True, blank=True)),
                ('appearance', models.TextField(null=True, blank=True)),
                ('level', models.IntegerField(default=1)),
                ('experience_points', models.IntegerField(default=0)),
                ('attributes', models.JSONField(default=dict)),
                ('skills', models.JSONField(default=list)),
                ('inventory', models.JSONField(default=list)),
                ('voice_profile', models.JSONField(default=dict)),
                ('images', models.JSONField(default=list)),
                ('primary_image_index', models.IntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('is_alive', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('last_played', models.DateTimeField(null=True, blank=True)),
            ],
            options={
                'db_table': 'characters',
            },
        ),
    ]

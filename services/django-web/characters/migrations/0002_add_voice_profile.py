# Generated migration to add voice_profile field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('characters', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE characters
            ADD COLUMN IF NOT EXISTS voice_profile JSONB DEFAULT '{}';
            """,
            reverse_sql="""
            ALTER TABLE characters
            DROP COLUMN IF EXISTS voice_profile;
            """
        ),
    ]

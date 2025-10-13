# Generated manually for dimensional maturity system
# Date: 2025-01-13

from django.db import migrations


def add_dimensional_maturity_column(apps, schema_editor):
    """Add dimensional_maturity JSONB column to characters table"""
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute("""
            ALTER TABLE characters
            ADD COLUMN IF NOT EXISTS dimensional_maturity JSONB DEFAULT '{
                "physical": {"current_level": 1, "bloom_level": "Remember", "experience_points": 0, "next_level_threshold": 100},
                "emotional": {"current_level": 1, "bloom_level": "Remember", "experience_points": 0, "next_level_threshold": 100},
                "intellectual": {"current_level": 1, "bloom_level": "Remember", "experience_points": 0, "next_level_threshold": 100},
                "social": {"current_level": 1, "bloom_level": "Remember", "experience_points": 0, "next_level_threshold": 100},
                "spiritual": {"current_level": 1, "bloom_level": "Remember", "experience_points": 0, "next_level_threshold": 100},
                "vocational": {"current_level": 1, "bloom_level": "Remember", "experience_points": 0, "next_level_threshold": 100},
                "environmental": {"current_level": 1, "bloom_level": "Remember", "experience_points": 0, "next_level_threshold": 100}
            }'::jsonb;
        """)

        # Create GIN index for efficient JSONB queries
        schema_editor.execute("""
            CREATE INDEX IF NOT EXISTS idx_characters_dimensional_maturity
            ON characters USING GIN (dimensional_maturity);
        """)


def remove_dimensional_maturity_column(apps, schema_editor):
    """Remove dimensional_maturity column (for rollback)"""
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute("""
            DROP INDEX IF EXISTS idx_characters_dimensional_maturity;
        """)
        schema_editor.execute("""
            ALTER TABLE characters DROP COLUMN IF EXISTS dimensional_maturity;
        """)


class Migration(migrations.Migration):

    dependencies = [
        ('characters', '0002_alter_character_options'),
    ]

    operations = [
        migrations.RunPython(
            add_dimensional_maturity_column,
            remove_dimensional_maturity_column
        ),
    ]

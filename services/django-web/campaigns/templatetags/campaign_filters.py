"""
Custom template filters for campaign views
"""
from django import template

register = template.Library()


@register.filter(name='friendly_key')
def friendly_key(value):
    """
    Convert snake_case keys to friendly Title Case names.

    Examples:
        total_campaign_objectives -> Total Campaign Objectives
        coverage_percentage -> Coverage Percentage
        average_redundancy -> Average Redundancy
    """
    if not value:
        return value

    # Replace underscores with spaces
    friendly = value.replace('_', ' ')

    # Title case
    friendly = friendly.title()

    return friendly

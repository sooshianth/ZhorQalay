from django import template

register = template.Library()

@register.filter
def mul(value, arg):
    """Multiply the arg with the value."""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def sum_monthly_hours(monthly_data):
    """Sum up the total hours from monthly summary data"""
    try:
        return sum(float(month['total_hours']) for month in monthly_data)
    except (ValueError, TypeError, KeyError):
        return 0 
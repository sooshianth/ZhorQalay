from django import template
from django.utils.safestring import mark_safe
from core.PurchaseModel import Purchase

register = template.Library()

@register.filter
def get_status_display(status_code):
    """
    Custom template filter to get the display value for a status code.
    Usage: {{ status_code|get_status_display }}
    """
    status_dict = dict(Purchase.STATUS_CHOICES)
    return status_dict.get(status_code, status_code) 
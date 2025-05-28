from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary using bracket notation in templates."""
    if not dictionary:
        return None
    return dictionary.get(key, None) 
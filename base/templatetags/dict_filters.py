from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Obtiene un item de un diccionario usando una clave"""
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None

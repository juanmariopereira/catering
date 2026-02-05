from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Obtiene un item de un diccionario usando una clave"""
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None


@register.filter
def get_item_pk(dictionary, key):
    """Obtiene el pk del item en un diccionario por clave (para objetos con atributo pk)."""
    if isinstance(dictionary, dict):
        item = dictionary.get(key)
        if item is not None and hasattr(item, 'pk'):
            return item.pk
    return None

"""
Filtros para mostrar cantidades en previsión de compra:
- ≥ 1000 g → mostrar en kg
- ≥ 1000 ml → mostrar en L
"""
from django import template

from purchases.utils import (
    prevision_cantidad_display as _cantidad_display,
    prevision_unidad_display as _unidad_display,
    prevision_medida_por_unidad_item_display as _medida_por_unidad_item_display,
)

register = template.Library()


@register.filter
def prevision_cantidad_display(cantidad, unidad_medida):
    """Cantidad para mostrar: gramo ≥ 1000 → kg; ml ≥ 1000 → L."""
    return _cantidad_display(cantidad, unidad_medida)


@register.filter
def prevision_unidad_display(cantidad, unidad_medida):
    """Unidad para mostrar: gramo ≥ 1000 → "kg"; ml ≥ 1000 → "L"."""
    return _unidad_display(cantidad, unidad_medida)


@register.filter
def prevision_medida_por_unidad_display(item):
    """Si la unidad es 'un', devuelve la medida por unidad del ingrediente (ej. 50 g/un)."""
    return _medida_por_unidad_item_display(item)

"""
Utilidades para previsión de compra.
Conversión de unidades para mostrar: ≥ 1000 g → kg, ≥ 1000 ml → L.
Agrupación de ítems por tipo de ingrediente.
"""
from collections import defaultdict


def _es_gramo(unidad_medida):
    if not unidad_medida:
        return False
    nom = (getattr(unidad_medida, 'nombre', None) or '').lower()
    sim = (getattr(unidad_medida, 'simbolo', None) or '').lower()
    return 'gramo' in nom or nom == 'gramo' or sim == 'g' or 'gram' in nom


def _es_mililitro(unidad_medida):
    if not unidad_medida:
        return False
    nom = (getattr(unidad_medida, 'nombre', None) or '').lower()
    sim = (getattr(unidad_medida, 'simbolo', None) or '').lower()
    return 'mililitro' in nom or nom == 'ml' or sim == 'ml'


def _es_unidad(unidad_medida):
    """True si la unidad es tipo 'unidad' (un, unidad, etc.)."""
    if not unidad_medida:
        return False
    nom = (getattr(unidad_medida, 'nombre', None) or '').lower()
    sim = (getattr(unidad_medida, 'simbolo', None) or '').lower()
    return nom == 'unidad' or sim == 'un' or 'unidad' in nom


def _cantidad_float(cantidad):
    try:
        return float(cantidad)
    except (TypeError, ValueError):
        return None


def prevision_cantidad_display(cantidad, unidad_medida):
    """
    Cantidad para mostrar en previsión: si es gramo ≥ 1000 → /1000; si es ml ≥ 1000 → /1000.
    """
    c = _cantidad_float(cantidad)
    if c is None:
        return cantidad
    if c >= 1000 and _es_gramo(unidad_medida):
        return round(c / 1000, 2)
    if c >= 1000 and _es_mililitro(unidad_medida):
        return round(c / 1000, 2)
    return cantidad


def prevision_unidad_display(cantidad, unidad_medida):
    """
    Unidad para mostrar: gramo ≥ 1000 → "kg"; ml ≥ 1000 → "L".
    """
    c = _cantidad_float(cantidad)
    if c is None or not unidad_medida:
        return str(unidad_medida) if unidad_medida else ''
    if c >= 1000 and _es_gramo(unidad_medida):
        return 'kg'
    if c >= 1000 and _es_mililitro(unidad_medida):
        return 'L'
    return getattr(unidad_medida, 'simbolo', None) or getattr(unidad_medida, 'nombre', str(unidad_medida))


def prevision_medida_por_unidad_display(ingrediente):
    """
    Para ítems en unidad (un): devuelve la medida por unidad del ingrediente,
    ej. "50 g/un" o "100 ml/un". Vacío si no aplica o no tiene equivalencia.
    """
    if not ingrediente:
        return ''
    eq = getattr(ingrediente, 'equivalencia_por_unidad', None)
    if eq is None:
        return ''
    try:
        val = float(eq)
    except (TypeError, ValueError):
        return ''
    if val <= 0:
        return ''
    tipo = (getattr(ingrediente, 'equivalencia_por_unidad_tipo', None) or 'g').strip().lower()
    if tipo == 'ml':
        return f'{val:g} ml/un'
    return f'{val:g} g/un'


def prevision_medida_por_unidad_item_display(item):
    """
    Para un PrevisionCompraItem: si la unidad es 'un' (unidad), devuelve la medida
    por unidad del ingrediente (ej. "50 g/un"); si no, devuelve cadena vacía.
    """
    if not item:
        return ''
    if not _es_unidad(getattr(item, 'unidad_medida', None)):
        return ''
    ing = getattr(item, 'ingrediente', None)
    return prevision_medida_por_unidad_display(ing)


def agrupar_items_prevision_por_tipo(items_queryset):
    """
    Agrupa ítems de previsión por tipo de ingrediente.
    items_queryset: queryset o lista de PrevisionCompraItem (con ingrediente y ingrediente.tipo_ingrediente).
    Devuelve lista de dicts: [ {'tipo_nombre': str, 'tipo_orden': int, 'items': [item, ...] }, ... ]
    ordenada alfabéticamente por tipo_nombre. Los sin tipo van al final como "Sin tipo".
    """
    grupos = defaultdict(list)
    for item in items_queryset:
        tipo = getattr(item.ingrediente, 'tipo_ingrediente', None) if getattr(item, 'ingrediente', None) else None
        if tipo is None:
            key = (9999, 'Sin tipo')
        else:
            orden = getattr(tipo, 'orden', 999)
            nombre = getattr(tipo, 'nombre', str(tipo))
            key = (orden, nombre)
        grupos[key].append(item)

    # Ordenar ítems dentro de cada grupo por nombre de ingrediente
    for key in grupos:
        grupos[key].sort(key=lambda i: (getattr(i.ingrediente, 'nombre', '') or '').lower())

    # Ordenar grupos alfabéticamente por nombre del tipo; "Sin tipo" al final
    resultado = []
    for (orden, nombre) in sorted(grupos.keys(), key=lambda k: (k[1] == 'Sin tipo', k[1].lower())):
        resultado.append({
            'tipo_nombre': nombre,
            'tipo_orden': orden,
            'items': grupos[(orden, nombre)],
        })
    return resultado

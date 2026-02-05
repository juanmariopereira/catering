"""
Filtros para formatear números con punto como separador de miles (formato español).
"""
from django import template

register = template.Library()


def _parte_entera_con_puntos(n_int):
    """Convierte parte entera a string con punto cada 3 dígitos (1.234.567)."""
    s = str(abs(n_int))
    rev = s[::-1]
    con_puntos = '.'.join(rev[i:i + 3] for i in range(0, len(rev), 3))[::-1]
    return ('-' if n_int < 0 else '') + con_puntos


@register.filter
def separador_miles(value, arg=None):
    """
    Formatea un número con punto como separador de miles (ej. 1234 → 1.234).
    Uso: {{ value|separador_miles }} para enteros; {{ value|separador_miles:2 }} para 2 decimales (coma decimal).
    """
    if value is None:
        return ''
    try:
        n = float(value)
    except (TypeError, ValueError):
        return value
    decimales = None
    if arg is not None:
        try:
            decimales = int(arg)
        except (TypeError, ValueError):
            pass
    if decimales is not None and decimales == 0:
        return _parte_entera_con_puntos(int(round(n)))
    if decimales is not None and decimales >= 1:
        entero = int(n)
        resto = round(n - entero, decimales)
        s_decimal = f"{resto:.{decimales}f}".split('.', 1)[-1]
        return _parte_entera_con_puntos(entero) + ',' + s_decimal
    # Sin argumento: entero si es entero, sino 2 decimales
    if n == int(n):
        return _parte_entera_con_puntos(int(n))
    entero = int(n)
    resto = round(n - entero, 2)
    s_decimal = f"{resto:.2f}".split('.', 1)[-1]
    return _parte_entera_con_puntos(entero) + ',' + s_decimal

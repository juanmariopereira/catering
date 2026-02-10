"""
Capa de lógica de negocio para la app clients.

Los servicios reciben parámetros simples (IDs, filtros, fechas) y devuelven
datos (querysets, dicts) o realizan operaciones. Pueden ser usados tanto por
vistas web (views) como por futuras API views (REST para app móvil).
"""

from .cliente_services import (
    list_clientes_queryset,
    get_cliente_detalle_data,
    get_cliente_delete_context,
    save_cliente_con_ingredientes_no_gustados,
)

__all__ = [
    'list_clientes_queryset',
    'get_cliente_detalle_data',
    'get_cliente_delete_context',
    'save_cliente_con_ingredientes_no_gustados',
]

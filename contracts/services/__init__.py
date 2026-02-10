"""
Capa de lógica de negocio para la app contracts.

Los servicios pueden ser usados por vistas web y por futuras API REST (app móvil).
"""

from .contrato_services import (
    list_contratos_queryset,
    get_contrato_detalle_data,
    get_contrato_list_context,
    get_contrato_create_initial,
    get_contrato_create_context,
    get_cliente_direccion_data,
    get_ultimo_contrato_direccion_data,
    aplicar_dias_extra,
)

__all__ = [
    'list_contratos_queryset',
    'get_contrato_detalle_data',
    'get_contrato_list_context',
    'get_contrato_create_initial',
    'get_contrato_create_context',
    'get_cliente_direccion_data',
    'get_ultimo_contrato_direccion_data',
    'aplicar_dias_extra',
]

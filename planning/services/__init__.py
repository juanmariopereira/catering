"""
Capa de lógica de negocio para la app planning.

Los servicios pueden ser usados por vistas web y por futuras API REST (app móvil).
"""

from .resumen_services import get_resumen_por_fecha
from .clientes_fecha_services import get_clientes_reciben_fecha, VIGENCIA_CHOICES
from .contratos_sin_entregador_services import get_contratos_sin_entregador_fecha
from .calendario_services import get_calendario_data
from .planificacion_services import (
    list_planificaciones_queryset,
    get_planificacion_list_context,
    get_planificacion_existente_fecha_plan,
    get_planificacion_menu_create_initial,
    get_planificacion_menu_create_context,
    get_recetas_por_tipo,
    get_recetas_del_menu,
    get_etiqueta_dieta_data,
    get_etiquetas_masivo_data,
    get_planificacion_menu_editar_context,
    guardar_sustituciones_from_post,
    guardar_dietas_personalizadas_from_post,
    actualizar_planificacion_menu,
    guardar_recetas_planificacion_menu,
    crear_planificacion_menu,
    crear_planificacion_menu_con_recetas,
)

__all__ = [
    'get_resumen_por_fecha',
    'get_clientes_reciben_fecha',
    'VIGENCIA_CHOICES',
    'get_contratos_sin_entregador_fecha',
    'get_calendario_data',
    'list_planificaciones_queryset',
    'get_planificacion_list_context',
    'get_planificacion_existente_fecha_plan',
    'get_planificacion_menu_create_initial',
    'get_planificacion_menu_create_context',
    'get_recetas_por_tipo',
    'get_recetas_del_menu',
    'get_etiqueta_dieta_data',
    'get_etiquetas_masivo_data',
    'get_planificacion_menu_editar_context',
    'guardar_sustituciones_from_post',
    'guardar_dietas_personalizadas_from_post',
    'actualizar_planificacion_menu',
    'guardar_recetas_planificacion_menu',
    'crear_planificacion_menu',
    'crear_planificacion_menu_con_recetas',
]

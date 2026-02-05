from typing import List, Set, Dict, Any
from django.db.models import Q
from .models import PlanificacionMenu, PlanificacionMenuReceta, PlanificacionClienteSustituta
from clients.models import IngredienteNoGustado
from diets.models import DietaReceta
from recipes.models import RecetaIngrediente
from contracts.models import Contrato


def obtener_ingredientes_no_gustados(cliente_id: int) -> Set[int]:
    """Obtiene los IDs de ingredientes que no le gustan a un cliente"""
    ingredientes_no_gustados = IngredienteNoGustado.objects.filter(
        cliente_id=cliente_id
    ).values_list('ingrediente_id', flat=True)
    return set(ingredientes_no_gustados)


def obtener_ingredientes_de_receta(receta_id: int) -> Set[int]:
    """Obtiene los IDs de ingredientes de una receta"""
    from recipes.models import RecetaIngrediente
    ingredientes = RecetaIngrediente.objects.filter(
        receta_id=receta_id
    ).values_list('ingrediente_id', flat=True)
    return set(ingredientes)


def verificar_conflicto_ingredientes(receta_id: int, ingredientes_no_gustados: Set[int]) -> bool:
    """Verifica si una receta contiene ingredientes que no le gustan al cliente"""
    ingredientes_receta = obtener_ingredientes_de_receta(receta_id)
    return bool(ingredientes_receta.intersection(ingredientes_no_gustados))


def sugerir_recetas_alternativas(dieta_id: int, cliente_id: int) -> List[int]:
    """
    Sugiere recetas alternativas para una dieta considerando los ingredientes
    que no le gustan al cliente.
    
    Retorna una lista de IDs de recetas alternativas que no contienen
    ingredientes que no le gustan al cliente.
    """
    from recipes.models import Receta
    from diets.models import DietaReceta
    
    # Obtener ingredientes que no le gustan al cliente
    ingredientes_no_gustados = obtener_ingredientes_no_gustados(cliente_id)
    
    if not ingredientes_no_gustados:
        return []
    
    # Obtener recetas de la dieta
    recetas_dieta = DietaReceta.objects.filter(dieta_id=dieta_id).values_list('receta_id', flat=True)
    
    # Verificar qué recetas tienen conflictos
    recetas_con_conflicto = []
    for receta_id in recetas_dieta:
        if verificar_conflicto_ingredientes(receta_id, ingredientes_no_gustados):
            recetas_con_conflicto.append(receta_id)
    
    if not recetas_con_conflicto:
        return []
    
    # Buscar recetas alternativas de la misma categoría que no tengan conflictos
    recetas_alternativas = []
    for receta_id in recetas_con_conflicto:
        receta = Receta.objects.get(id=receta_id)
        
        # Buscar recetas de la misma categoría que no tengan ingredientes conflictivos
        recetas_similares = Receta.objects.filter(
            categoria=receta.categoria,
            activa=True
        ).exclude(id=receta_id)
        
        for receta_alternativa in recetas_similares:
            if not verificar_conflicto_ingredientes(receta_alternativa.id, ingredientes_no_gustados):
                if receta_alternativa.id not in recetas_alternativas:
                    recetas_alternativas.append(receta_alternativa.id)
    
    return recetas_alternativas


def obtener_ingredientes_conflicto_receta(receta_id: int, ingredientes_no_gustados: Set[int]) -> List[Any]:
    """Devuelve la lista de ingredientes (objetos) de una receta que están en ingredientes_no_gustados."""
    from recipes.models import Ingrediente
    ingredientes_receta = RecetaIngrediente.objects.filter(
        receta_id=receta_id
    ).select_related('ingrediente').values_list('ingrediente_id', flat=True)
    conflictivos_ids = set(ingredientes_receta) & ingredientes_no_gustados
    if not conflictivos_ids:
        return []
    return list(Ingrediente.objects.filter(id__in=conflictivos_ids))


def obtener_conflictos_planificacion(dieta_id: int, cliente_id: int) -> List[Dict[str, Any]]:
    """
    Para una dieta y un cliente, devuelve la lista de recetas de la dieta que contienen
    ingredientes que el cliente no gusta, con detalle: momento (tipo_comida), receta,
    ingredientes en conflicto. Sirve para mostrar avisos y permitir sustituciones.
    """
    ingredientes_no_gustados = obtener_ingredientes_no_gustados(cliente_id)
    if not ingredientes_no_gustados:
        return []

    dieta_recetas = (
        DietaReceta.objects.filter(dieta_id=dieta_id)
        .select_related('receta', 'tipo_comida')
        .order_by('tipo_comida__orden', 'orden')
    )
    conflictos = []
    for dr in dieta_recetas:
        if verificar_conflicto_ingredientes(dr.receta_id, ingredientes_no_gustados):
            ingredientes_conflicto = obtener_ingredientes_conflicto_receta(
                dr.receta_id, ingredientes_no_gustados
            )
            conflictos.append({
                'dieta_receta': dr,
                'receta': dr.receta,
                'tipo_comida': dr.tipo_comida,
                'ingredientes_conflicto': ingredientes_conflicto,
                'ingredientes_nombres': [i.nombre for i in ingredientes_conflicto],
            })
    return conflictos


def recetas_alternativas_para_momento(
    tipo_comida_id: int,
    receta_id: int,
    cliente_id: int,
    categoria_preferida: str = None,
) -> List[Any]:
    """
    Recetas alternativas para sustituir una receta en un momento dado, que no contengan
    ingredientes que el cliente no gusta. Opcionalmente de la misma categoría.
    """
    from recipes.models import Receta
    ingredientes_no_gustados = obtener_ingredientes_no_gustados(cliente_id)
    receta_original = Receta.objects.get(id=receta_id)
    qs = Receta.objects.filter(activa=True).exclude(id=receta_id)
    if categoria_preferida:
        qs = qs.filter(categoria=receta_original.categoria)
    alternativas = []
    for r in qs:
        if not verificar_conflicto_ingredientes(r.id, ingredientes_no_gustados):
            alternativas.append(r)
    return alternativas


def obtener_conflictos_menu_por_cliente(planificacion_menu, contrato) -> List[Dict[str, Any]]:
    """
    Para un menú planificado (fecha + plan) y un contrato (cliente), devuelve las recetas
    del menú que contienen ingredientes que el cliente no gusta, para mostrar avisos
    y permitir sustituciones (PlanificacionClienteSustituta).
    """
    cliente_id = contrato.cliente_id
    ingredientes_no_gustados = obtener_ingredientes_no_gustados(cliente_id)
    if not ingredientes_no_gustados:
        return []
    menu_recetas = (
        PlanificacionMenuReceta.objects.filter(planificacion_menu=planificacion_menu)
        .select_related('receta', 'tipo_comida')
        .order_by('tipo_comida__orden', 'orden')
    )
    conflictos = []
    for mr in menu_recetas:
        if verificar_conflicto_ingredientes(mr.receta_id, ingredientes_no_gustados):
            ingredientes_conflicto = obtener_ingredientes_conflicto_receta(
                mr.receta_id, ingredientes_no_gustados
            )
            conflictos.append({
                'menu_receta': mr,
                'receta': mr.receta,
                'tipo_comida': mr.tipo_comida,
                'ingredientes_conflicto': ingredientes_conflicto,
                'ingredientes_nombres': [i.nombre for i in ingredientes_conflicto],
            })
    return conflictos


def _receta_efectiva_por_contrato(fecha, contrato_id, tipo_comida_id, receta_original_id, sustituciones_map):
    """Devuelve receta_id efectiva (sustituta si existe, sino original)."""
    key = (contrato_id, tipo_comida_id, receta_original_id)
    return sustituciones_map.get(key) or receta_original_id


def recetas_a_preparar_por_fecha(fecha) -> List[Dict[str, Any]]:
    """
    Recetas a preparar para una fecha usando PlanificacionMenu y PlanificacionMenuReceta,
    aplicando PlanificacionClienteSustituta por cliente.
    Devuelve lista de dict: receta, cantidad, planificaciones.
    Cada planificación incluye: menu, contrato, es_sustituta, receta_original_nombre (si es sustituta)
    para que el reporte de cocina muestre qué cliente recibe plato diferente.
    """
    from collections import defaultdict
    from recipes.models import Receta
    menus = PlanificacionMenu.objects.filter(fecha=fecha).select_related('plan').prefetch_related('recetas')
    sustituciones = PlanificacionClienteSustituta.objects.filter(fecha=fecha)
    sustituciones_map = {
        (s.contrato_id, s.tipo_comida_id, s.receta_original_id): s.receta_sustituta_id
        for s in sustituciones
    }
    recetas_dict = defaultdict(int)
    planificaciones_por_receta = defaultdict(list)
    recetas_objs_cache = {}
    for menu in menus:
        contratos = Contrato.objects.filter(
            plan=menu.plan,
            estado='activo',
            fecha_inicio__lte=fecha,
        ).filter(Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=fecha))
        for contrato in contratos:
            for mr in menu.recetas.all():
                receta_original_id = mr.receta_id
                receta_id = _receta_efectiva_por_contrato(
                    fecha, contrato.id, mr.tipo_comida_id, receta_original_id, sustituciones_map
                )
                recetas_dict[receta_id] += 1
                es_sustituta = receta_id != receta_original_id
                receta_original_nombre = None
                if es_sustituta and receta_original_id not in recetas_objs_cache:
                    try:
                        recetas_objs_cache[receta_original_id] = Receta.objects.get(pk=receta_original_id)
                    except Receta.DoesNotExist:
                        recetas_objs_cache[receta_original_id] = None
                if es_sustituta and recetas_objs_cache.get(receta_original_id):
                    receta_original_nombre = recetas_objs_cache[receta_original_id].nombre
                planificaciones_por_receta[receta_id].append({
                    'menu': menu,
                    'contrato': contrato,
                    'es_sustituta': es_sustituta,
                    'receta_original_nombre': receta_original_nombre,
                })
    recetas_objs = {r.id: r for r in Receta.objects.filter(id__in=recetas_dict.keys())} if recetas_dict else {}
    return [
        {
            'receta': recetas_objs[receta_id],
            'cantidad': recetas_dict[receta_id],
            'planificaciones': planificaciones_por_receta[receta_id],
        }
        for receta_id in recetas_dict
    ]


def ingredientes_por_rango_fechas(fecha_desde, fecha_hasta) -> Dict[tuple, float]:
    """
    Suma de ingredientes (id, unidad) -> cantidad para menús planificados en el rango,
    aplicando sustituciones por cliente. Para previsiones de compra.
    """
    from collections import defaultdict
    from recipes.models import RecetaIngrediente
    menus = PlanificacionMenu.objects.filter(
        fecha__gte=fecha_desde,
        fecha__lte=fecha_hasta,
    ).select_related('plan').prefetch_related('recetas')
    ingredientes_totales = defaultdict(float)
    for menu in menus:
        sustituciones = PlanificacionClienteSustituta.objects.filter(
            fecha=menu.fecha,
            contrato__plan=menu.plan,
        ).values_list('contrato_id', 'tipo_comida_id', 'receta_original_id', 'receta_sustituta_id')
        sustituciones_map = {
            (c, t, r_orig): r_sust for c, t, r_orig, r_sust in sustituciones
        }
        contratos = Contrato.objects.filter(
            plan=menu.plan,
            estado='activo',
            fecha_inicio__lte=menu.fecha,
        ).filter(Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=menu.fecha))
        for contrato in contratos:
            for mr in menu.recetas.all():
                receta_id = _receta_efectiva_por_contrato(
                    menu.fecha, contrato.id, mr.tipo_comida_id, mr.receta_id, sustituciones_map
                )
                for ri in RecetaIngrediente.objects.filter(receta_id=receta_id):
                    key = (ri.ingrediente_id, ri.unidad_medida)
                    ingredientes_totales[key] += float(ri.cantidad)
    return dict(ingredientes_totales)

from typing import List, Set
from .models import PlanificacionDieta
from clients.models import IngredienteNoGustado
from diets.models import DietaReceta


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

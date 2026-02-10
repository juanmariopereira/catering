"""
Lógica de negocio: contratos que reciben menú en una fecha pero no tienen entregador asignado.
"""

from django.utils import timezone

from planning.models import PlanificacionMenu
from contracts.models import contratos_activos_en_fecha
from delivery.utils import contratos_en_ruta_fecha
from base.models import es_feriado, get_feriado


def get_contratos_sin_entregador_fecha(fecha=None):
    """
    Contratos activos en la fecha con menú planificado pero sin ruta/entregador.

    Returns:
        dict con: fecha, filas (lista de {contrato, cliente, plan}), es_feriado, feriado.
    """
    if fecha is None:
        fecha = timezone.now().date()
    menus_por_plan = {
        pm.plan_id: pm
        for pm in PlanificacionMenu.objects.filter(fecha=fecha).select_related('plan')
    }
    contratos_fecha = contratos_activos_en_fecha(fecha).select_related('plan', 'cliente')
    contrato_ids_con_ruta = contratos_en_ruta_fecha(fecha)
    filas = []
    for c in contratos_fecha:
        if c.plan_id not in menus_por_plan or c.id in contrato_ids_con_ruta:
            continue
        filas.append({
            'contrato': c,
            'cliente': c.cliente,
            'plan': c.plan,
        })
    return {
        'fecha': fecha,
        'filas': filas,
        'es_feriado': es_feriado(fecha),
        'feriado': get_feriado(fecha),
    }

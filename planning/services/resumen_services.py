"""
Lógica de negocio para resumen por fecha: clientes por plan, menús, avisos.
"""

from collections import defaultdict
from datetime import date, timedelta

from django.utils import timezone

from planning.models import PlanificacionMenu
from planning.utils import obtener_conflictos_menu_por_cliente
from contracts.models import contratos_activos_en_fecha
from plans.models import Plan
from base.models import es_feriado, get_feriado


def get_resumen_por_fecha(fecha=None):
    """
    Resumen de cantidad de clientes por plan en una fecha.
    Incluye menús planificados y avisos de conflictos (ingredientes no gustados).

    Args:
        fecha: date o None (usa hoy)

    Returns:
        dict con: fecha, resumen (lista de {plan, cantidad, contratos, planificacion_menu}),
        fecha_anterior, fecha_siguiente, total_clientes, menus_creados, avisos_pendientes,
        es_feriado, feriado.
    """
    if fecha is None:
        fecha = timezone.now().date()
    contratos_fecha = contratos_activos_en_fecha(fecha).select_related('plan', 'cliente')
    por_plan = defaultdict(list)
    for c in contratos_fecha:
        por_plan[c.plan].append(c)
    menus_por_plan = {
        pm.plan_id: pm
        for pm in PlanificacionMenu.objects.filter(fecha=fecha).select_related('plan')
    }
    resumen = []
    for plan in Plan.objects.filter(activo=True).order_by('nombre'):
        contratos = por_plan.get(plan, [])
        planificacion_menu = menus_por_plan.get(plan.id)
        resumen.append({
            'plan': plan,
            'cantidad': len(contratos),
            'contratos': contratos,
            'planificacion_menu': planificacion_menu,
        })
    avisos_pendientes = 0
    for r in resumen:
        if not r['planificacion_menu'] or not r['contratos']:
            continue
        for c in r['contratos']:
            if obtener_conflictos_menu_por_cliente(r['planificacion_menu'], c):
                avisos_pendientes += 1
    return {
        'fecha': fecha,
        'resumen': resumen,
        'fecha_anterior': fecha - timedelta(days=1),
        'fecha_siguiente': fecha + timedelta(days=1),
        'total_clientes': sum(r['cantidad'] for r in resumen),
        'menus_creados': len([r for r in resumen if r['planificacion_menu']]),
        'avisos_pendientes': avisos_pendientes,
        'es_feriado': es_feriado(fecha),
        'feriado': get_feriado(fecha),
    }

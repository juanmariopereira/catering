"""
Lógica de negocio para el calendario de planificaciones (mes).
"""

from datetime import date, timedelta

from django.utils import timezone

from planning.models import PlanificacionMenu
from base.models import Feriado


def get_calendario_data(year=None, month=None):
    """
    Datos para renderizar el calendario de un mes: celdas, planificaciones por día, feriados.

    Args:
        year, month: int o None (usa mes actual).

    Returns:
        dict con: fecha (primer día del mes), mes_anterior, mes_siguiente, ultimo_dia,
        celdas_vacias_inicio, celdas_vacias_fin, rango_vacias_inicio, rango_vacias_fin,
        dias_del_mes, planificaciones_por_dia (dict día -> [PlanificacionMenu]),
        feriados_por_dia (dict día -> nombre).
    """
    if year and month:
        try:
            fecha = date(int(year), int(month), 1)
        except (ValueError, TypeError):
            fecha = timezone.now().date().replace(day=1)
    else:
        fecha = timezone.now().date().replace(day=1)

    if fecha.month == 12:
        siguiente_mes = fecha.replace(year=fecha.year + 1, month=1)
    else:
        siguiente_mes = fecha.replace(month=fecha.month + 1)
    ultimo_dia = (siguiente_mes - timedelta(days=1)).day
    primer_dia_mes = fecha.replace(day=1)
    celdas_vacias_inicio = primer_dia_mes.weekday()
    dias_del_mes = list(range(1, ultimo_dia + 1))
    TOTAL_CELDAS_MES = 6 * 7
    celdas_vacias_fin = TOTAL_CELDAS_MES - celdas_vacias_inicio - ultimo_dia
    rango_vacias_inicio = list(range(celdas_vacias_inicio))
    rango_vacias_fin = list(range(max(0, celdas_vacias_fin)))

    planificaciones = PlanificacionMenu.objects.filter(
        fecha__year=fecha.year,
        fecha__month=fecha.month,
    ).select_related('plan')
    planificaciones_por_dia = {}
    for planificacion in planificaciones:
        dia = planificacion.fecha.day
        if dia not in planificaciones_por_dia:
            planificaciones_por_dia[dia] = []
        planificaciones_por_dia[dia].append(planificacion)

    feriados_mes = Feriado.objects.filter(
        fecha__year=fecha.year,
        fecha__month=fecha.month,
    )
    feriados_por_dia = {f.fecha.day: f.nombre for f in feriados_mes}

    if fecha.month == 1:
        mes_anterior = fecha.replace(year=fecha.year - 1, month=12)
    else:
        mes_anterior = fecha.replace(month=fecha.month - 1)

    return {
        'fecha': fecha,
        'mes_anterior': mes_anterior,
        'mes_siguiente': siguiente_mes,
        'ultimo_dia': ultimo_dia,
        'celdas_vacias_inicio': celdas_vacias_inicio,
        'celdas_vacias_fin': celdas_vacias_fin,
        'rango_vacias_inicio': rango_vacias_inicio,
        'rango_vacias_fin': rango_vacias_fin,
        'dias_del_mes': dias_del_mes,
        'planificaciones_por_dia': planificaciones_por_dia,
        'feriados_por_dia': feriados_por_dia,
    }

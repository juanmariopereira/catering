"""
Utilidades para rutas de entrega: contratos con entrega en una fecha
y contratos sin asignar a ninguna ruta.
"""
from datetime import date

from contracts.models import contratos_activos_en_fecha
from routes.models import RutaCliente

# Día de la semana: Python weekday() 0=lunes, 6=domingo -> valor en contrato.dias_entrega
DIA_SEMANA_NOMBRE = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo']


def contratos_con_entrega_en_fecha(fecha):
    """
    Contratos activos en la fecha que tienen entrega ese día (dias_entrega).
    """
    if hasattr(fecha, 'date'):
        fecha = fecha.date()
    dia_semana = DIA_SEMANA_NOMBRE[fecha.weekday()]
    return (
        contratos_activos_en_fecha(fecha)
        .filter(dias_entrega__contains=[dia_semana])
        .distinct()
    )


def contratos_sin_ruta_en_fecha(fecha):
    """
    Contratos que tienen entrega en la fecha pero no están en ninguna ruta ese día.
    Útil para detectar entregas pendientes de asignar (rutas ya creadas o nuevos contratos).
    """
    con_entrega = contratos_con_entrega_en_fecha(fecha)
    asignados = set(
        RutaCliente.objects.filter(ruta__fecha=fecha).values_list('contrato_id', flat=True)
    )
    return con_entrega.exclude(pk__in=asignados).select_related('cliente', 'plan')

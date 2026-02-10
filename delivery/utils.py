"""
Utilidades para rutas de entrega: contratos con entrega en una fecha,
contratos sin asignar a ninguna plantilla, y paradas del día por entregador.
"""
from datetime import date

from base.models import es_feriado
from contracts.models import Contrato, contratos_activos_en_fecha
from routes.models import PlantillaRutaCliente

# Día de la semana: Python weekday() 0=lunes, 6=domingo -> valor en contrato.dias_entrega
DIA_SEMANA_NOMBRE = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo']


def contratos_con_entrega_en_fecha(fecha):
    """
    Contratos activos en la fecha que tienen entrega ese día (dias_entrega).
    En feriados no hay entregas: devuelve queryset vacío.
    """
    if hasattr(fecha, 'date'):
        fecha = fecha.date()
    if es_feriado(fecha):
        return Contrato.objects.none()
    dia_semana = DIA_SEMANA_NOMBRE[fecha.weekday()]
    return (
        contratos_activos_en_fecha(fecha)
        .filter(dias_entrega__contains=[dia_semana])
        .distinct()
    )


def contratos_en_ruta_fecha(fecha):
    """
    Contrato IDs que están en alguna plantilla y tendrían entrega ese día
    (activo en fecha + dias_entrega). Útil para dietas, cocina, planificación.
    """
    from routes.models import PlantillaRuta, PlantillaRutaCliente
    if hasattr(fecha, 'date'):
        fecha = fecha.date()
    if es_feriado(fecha):
        return set()
    dia_semana = DIA_SEMANA_NOMBRE[fecha.weekday()]
    out = set()
    for prc in PlantillaRutaCliente.objects.select_related('contrato').filter(
        plantilla_ruta__entregador__activo=True,
    ):
        c = prc.contrato
        if not c.activo_en_fecha(fecha):
            continue
        if not c.dias_entrega or dia_semana not in c.dias_entrega:
            continue
        out.add(c.id)
    return out


def entregador_por_contrato_en_fecha(fecha):
    """
    Devuelve {contrato_id: entregador} para contratos con entrega en la fecha
    que están asignados a alguna plantilla de entregador activo.
    """
    if hasattr(fecha, 'date'):
        fecha = fecha.date()
    if es_feriado(fecha):
        return {}
    dia_semana = DIA_SEMANA_NOMBRE[fecha.weekday()]
    out = {}
    for prc in PlantillaRutaCliente.objects.filter(
        plantilla_ruta__entregador__activo=True,
    ).select_related('plantilla_ruta__entregador', 'contrato'):
        c = prc.contrato
        if not c.activo_en_fecha(fecha):
            continue
        if not c.dias_entrega or dia_semana not in c.dias_entrega:
            continue
        out[c.id] = prc.plantilla_ruta.entregador
    return out


def contratos_sin_ruta_en_fecha(fecha):
    """
    Contratos que tienen entrega en la fecha pero no están en ninguna plantilla de entregador.
    (Sin ruta = no asignados a ningún entregador en la plantilla.)
    """
    con_entrega = contratos_con_entrega_en_fecha(fecha)
    asignados = set(
        PlantillaRutaCliente.objects.values_list('contrato_id', flat=True)
    )
    return con_entrega.exclude(pk__in=asignados).select_related('cliente', 'plan')


def get_paradas_ruta_fecha(entregador, fecha):
    """
    Paradas de la ruta del día para un entregador en una fecha.
    Lista de (PlantillaRutaCliente, estado_entrega_dia o None) ordenada por orden_entrega.
    Solo incluye contratos activos en la fecha y con entrega ese día (dias_entrega).
    """
    if hasattr(fecha, 'date'):
        fecha = fecha.date()
    if es_feriado(fecha):
        return []
    dia_semana = DIA_SEMANA_NOMBRE[fecha.weekday()]
    from routes.models import PlantillaRuta, EntregaDia

    plantilla = getattr(entregador, 'plantilla_ruta', None)
    if not plantilla:
        return []
    prcs = list(
        plantilla.clientes.select_related('contrato__cliente', 'contrato__plan')
        .order_by('orden_entrega')
    )
    # Filtrar: activo en fecha y tiene entrega ese día
    out = []
    for prc in prcs:
        c = prc.contrato
        if not c.activo_en_fecha(fecha):
            continue
        if not c.dias_entrega or dia_semana not in c.dias_entrega:
            continue
        estado = EntregaDia.objects.filter(
            entregador=entregador,
            contrato=c,
            fecha=fecha,
        ).first()
        out.append((prc, estado))
    return out


class RutaClienteDia:
    """
    Objeto compatible con la plantilla ruta_imprimible: tiene .contrato, .orden_entrega,
    .codigo_entrega, .entregada, .no_entregada, .fecha_entrega, etc., a partir de
    (PlantillaRutaCliente, EntregaDia o None).
    """
    def __init__(self, prc, estado):
        self.prc = prc
        self.estado = estado
        self.contrato = prc.contrato
        self.orden_entrega = prc.orden_entrega
        self.codigo_entrega = prc.codigo_entrega or ''
        self.entregada = estado.entregada if estado else False
        self.fecha_entrega = estado.fecha_entrega if estado else None
        self.marcadopor_entregada = estado.marcadopor_entregada if estado else None
        self.no_entregada = estado.no_entregada if estado else False
        self.motivo_no_entrega = estado.motivo_no_entrega if estado else ''
        self.fecha_no_entrega = estado.fecha_no_entrega if estado else None
        self.marcadopor_no_entrega = estado.marcadopor_no_entrega if estado else None
        self.pk = estado.pk if estado else None
        self.entregador_id = prc.plantilla_ruta.entregador_id
        self.contrato_id = prc.contrato_id
        # Hora de entrega pactada en el contrato (horario_entrega)
        self.horario_entrega = getattr(prc.contrato, 'horario_entrega', None)
        # La plantilla espera .direccion_entrega como dict (calle, etc.); en contrato es texto, usamos {}
        self.direccion_entrega = {}

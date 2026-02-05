from datetime import timedelta
from django.utils import timezone
from .models import Cobro, _dias_vencimiento_por_frecuencia
from contracts.models import Contrato


def generar_cobro_automatico(contrato: Contrato, periodo_desde, periodo_hasta):
    """
    Genera un cobro automático para un contrato en un período específico.
    La fecha de vencimiento se calcula automáticamente según la frecuencia del contrato.
    """
    dias_periodo = (periodo_hasta - periodo_desde).days + 1

    if contrato.frecuencia_pago == 'diario':
        monto = float(contrato.precio) * dias_periodo
    elif contrato.frecuencia_pago == 'semanal':
        semanas = dias_periodo / 7
        monto = float(contrato.precio) * semanas
    elif contrato.frecuencia_pago == 'quincenal':
        quincenas = dias_periodo / 15
        monto = float(contrato.precio) * quincenas
    elif contrato.frecuencia_pago == 'mensual':
        meses = dias_periodo / 30
        monto = float(contrato.precio) * meses
    else:
        monto = float(contrato.precio)

    cobro = Cobro.objects.create(
        contrato=contrato,
        periodo_desde=periodo_desde,
        periodo_hasta=periodo_hasta,
        monto=monto,
        fecha_vencimiento=periodo_hasta + timedelta(days=_dias_vencimiento_por_frecuencia(contrato.frecuencia_pago)),
        estado='pendiente',
    )
    return cobro


def generar_cobros_pendientes():
    """
    Genera cobros pendientes para todos los contratos activos
    según su frecuencia de pago.
    """
    contratos_activos = Contrato.objects.filter(estado='activo')
    cobros_generados = []
    hoy = timezone.now().date()

    for contrato in contratos_activos:
        if contrato.frecuencia_pago == 'mensual':
            periodo_desde = hoy.replace(day=1)
            if hoy.month == 12:
                periodo_hasta = hoy.replace(year=hoy.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                periodo_hasta = hoy.replace(month=hoy.month + 1, day=1) - timedelta(days=1)

            existente = Cobro.objects.filter(
                contrato=contrato,
                periodo_desde=periodo_desde,
                periodo_hasta=periodo_hasta,
            ).first()

            if not existente:
                cobro = generar_cobro_automatico(contrato, periodo_desde, periodo_hasta)
                cobros_generados.append(cobro)

    return cobros_generados


def obtener_cobros_vencidos():
    """Obtiene todos los cobros vencidos y no pagados."""
    hoy = timezone.now().date()
    return Cobro.objects.filter(
        fecha_vencimiento__lt=hoy,
        estado__in=['pendiente', 'vencida']
    )

from datetime import timedelta
from django.utils import timezone
from .models import Factura
from contracts.models import Contrato


def generar_factura_automatica(contrato: Contrato, periodo_desde, periodo_hasta):
    """
    Genera una factura automática para un contrato en un período específico
    """
    # Calcular monto según frecuencia de pago
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
    
    # Calcular fecha de vencimiento (30 días después de la emisión)
    fecha_emision = timezone.now().date()
    fecha_vencimiento = fecha_emision + timedelta(days=30)
    
    factura = Factura.objects.create(
        contrato=contrato,
        fecha_emision=fecha_emision,
        fecha_vencimiento=fecha_vencimiento,
        monto=monto,
        periodo_desde=periodo_desde,
        periodo_hasta=periodo_hasta,
        estado='pendiente'
    )
    
    return factura


def generar_facturas_pendientes():
    """
    Genera facturas pendientes para todos los contratos activos
    según su frecuencia de pago
    """
    contratos_activos = Contrato.objects.filter(estado='activo')
    facturas_generadas = []
    
    hoy = timezone.now().date()
    
    for contrato in contratos_activos:
        # Verificar si ya existe una factura para el período actual
        # Esto depende de la lógica de negocio específica
        # Por ahora, generamos facturas mensuales automáticamente
        
        if contrato.frecuencia_pago == 'mensual':
            # Generar factura para el mes actual
            periodo_desde = hoy.replace(day=1)
            if hoy.month == 12:
                periodo_hasta = hoy.replace(year=hoy.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                periodo_hasta = hoy.replace(month=hoy.month + 1, day=1) - timedelta(days=1)
            
            # Verificar si ya existe factura para este período
            factura_existente = Factura.objects.filter(
                contrato=contrato,
                periodo_desde=periodo_desde,
                periodo_hasta=periodo_hasta
            ).first()
            
            if not factura_existente:
                factura = generar_factura_automatica(contrato, periodo_desde, periodo_hasta)
                facturas_generadas.append(factura)
    
    return facturas_generadas


def obtener_facturas_vencidas():
    """Obtiene todas las facturas vencidas y no pagadas"""
    hoy = timezone.now().date()
    return Factura.objects.filter(
        fecha_vencimiento__lt=hoy,
        estado__in=['pendiente', 'vencida']
    )

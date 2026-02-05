"""
Vistas principales del proyecto.
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum
from datetime import date, timedelta, datetime

from planning.models import PlanificacionDieta
from billing.models import Factura
from routes.models import Ruta
from purchases.models import PrevisionCompra
from clients.models import Cliente
from contracts.models import Contrato


@login_required
def dashboard(request):
    """Dashboard principal con indicadores y menú de navegación."""
    hoy = timezone.now().date()

    # Planificaciones del día
    planificaciones_hoy = PlanificacionDieta.objects.filter(fecha=hoy)
    planificaciones_pendientes = planificaciones_hoy.filter(estado='pendiente').count()
    planificaciones_preparacion = planificaciones_hoy.filter(estado='en_preparacion').count()
    planificaciones_completadas = planificaciones_hoy.filter(estado='completada').count()
    total_planificaciones_hoy = planificaciones_hoy.count()

    # Facturación
    facturas_pendientes = Factura.objects.filter(estado='pendiente').count()
    facturas_vencidas = Factura.objects.filter(estado='vencida').count()
    monto_pendiente = Factura.objects.filter(
        estado__in=['pendiente', 'vencida']
    ).aggregate(total=Sum('monto'))['total'] or 0

    # Rutas del día
    rutas_hoy = Ruta.objects.filter(fecha=hoy, activa=True)
    total_rutas_hoy = rutas_hoy.count()

    # Previsiones recientes (últimos 7 días)
    hace_7_dias = hoy - timedelta(days=7)
    inicio_semana = timezone.make_aware(datetime.combine(hace_7_dias, datetime.min.time()))
    previsiones_recientes = PrevisionCompra.objects.filter(
        fecha_generacion__gte=inicio_semana
    ).count()

    # Clientes y contratos activos
    clientes_activos = Cliente.objects.filter(activo=True).count()
    contratos_activos = Contrato.objects.filter(estado='activo').count()

    # Planificaciones próxima semana
    proxima_semana = hoy + timedelta(days=7)
    planificaciones_proxima_semana = PlanificacionDieta.objects.filter(
        fecha__gte=hoy,
        fecha__lte=proxima_semana,
        estado__in=['pendiente', 'en_preparacion']
    ).count()

    context = {
        'hoy': hoy,
        'total_planificaciones_hoy': total_planificaciones_hoy,
        'planificaciones_pendientes': planificaciones_pendientes,
        'planificaciones_preparacion': planificaciones_preparacion,
        'planificaciones_completadas': planificaciones_completadas,
        'facturas_pendientes': facturas_pendientes,
        'facturas_vencidas': facturas_vencidas,
        'monto_pendiente': monto_pendiente,
        'total_rutas_hoy': total_rutas_hoy,
        'rutas_hoy': rutas_hoy[:5],
        'previsiones_recientes': previsiones_recientes,
        'clientes_activos': clientes_activos,
        'contratos_activos': contratos_activos,
        'planificaciones_proxima_semana': planificaciones_proxima_semana,
        'planificaciones_hoy_lista': planificaciones_hoy.select_related(
            'contrato__cliente', 'dieta'
        )[:5],
    }

    return render(request, 'base/dashboard.html', context)

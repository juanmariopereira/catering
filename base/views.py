"""
Vistas principales del proyecto.
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum
from datetime import date, timedelta, datetime

from planning.models import PlanificacionMenu
from billing.models import Factura
from routes.models import Ruta
from purchases.models import PrevisionCompra
from clients.models import Cliente
from contracts.models import Contrato


@login_required
def dashboard(request):
    """Dashboard principal con indicadores y menú de navegación."""
    hoy = timezone.now().date()

    # Menús planificados del día (fecha + plan)
    menus_hoy = PlanificacionMenu.objects.filter(fecha=hoy)
    total_planificaciones_hoy = menus_hoy.count()

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

    # Menús planificados próxima semana
    proxima_semana = hoy + timedelta(days=7)
    planificaciones_proxima_semana = PlanificacionMenu.objects.filter(
        fecha__gte=hoy,
        fecha__lte=proxima_semana,
    ).count()

    context = {
        'hoy': hoy,
        'total_planificaciones_hoy': total_planificaciones_hoy,
        'facturas_pendientes': facturas_pendientes,
        'facturas_vencidas': facturas_vencidas,
        'monto_pendiente': monto_pendiente,
        'total_rutas_hoy': total_rutas_hoy,
        'rutas_hoy': rutas_hoy[:5],
        'previsiones_recientes': previsiones_recientes,
        'clientes_activos': clientes_activos,
        'contratos_activos': contratos_activos,
        'planificaciones_proxima_semana': planificaciones_proxima_semana,
        'menus_hoy_lista': menus_hoy.select_related('plan')[:5],
    }

    return render(request, 'base/dashboard.html', context)


def page_not_found(request, exception):
    """Vista 404 amigable: recurso o registro no encontrado."""
    return render(request, '404.html', status=404)

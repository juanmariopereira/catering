"""
Vistas principales del proyecto.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy, reverse
from datetime import date, timedelta, datetime

from .models import Feriado
from .forms import FeriadoForm
from planning.models import PlanificacionMenu
from billing.models import Cobro, Pago
from routes.models import Ruta, RutaCliente
from purchases.models import PrevisionCompra
from clients.models import Cliente
from contracts.models import Contrato
from recipes.models import Receta


@login_required
def dashboard(request):
    """Dashboard principal con indicadores y menú de navegación."""
    hoy = timezone.now().date()

    # Menús planificados del día (fecha + plan)
    menus_hoy = PlanificacionMenu.objects.filter(fecha=hoy)
    total_planificaciones_hoy = menus_hoy.count()

    # Cobranza
    cobros_pendientes = Cobro.objects.filter(estado='pendiente').count()
    cobros_vencidos = Cobro.objects.filter(estado='vencida').count()
    monto_pendiente = Cobro.objects.filter(
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

    # Entregas (paradas) del día
    total_entregas_hoy = RutaCliente.objects.filter(ruta__fecha=hoy).count()

    # Recetas activas en catálogo
    recetas_activas = Receta.objects.filter(activa=True).count()

    # Cobrado este mes
    inicio_mes = hoy.replace(day=1)
    cobrado_mes = Pago.objects.filter(
        fecha_pago__gte=inicio_mes,
        fecha_pago__lte=hoy,
    ).aggregate(total=Sum('monto'))['total'] or 0

    context = {
        'hoy': hoy,
        'total_planificaciones_hoy': total_planificaciones_hoy,
        'cobros_pendientes': cobros_pendientes,
        'cobros_vencidos': cobros_vencidos,
        'monto_pendiente': monto_pendiente,
        'total_rutas_hoy': total_rutas_hoy,
        'rutas_hoy': rutas_hoy[:5],
        'previsiones_recientes': previsiones_recientes,
        'clientes_activos': clientes_activos,
        'contratos_activos': contratos_activos,
        'planificaciones_proxima_semana': planificaciones_proxima_semana,
        'menus_hoy_lista': menus_hoy.select_related('plan')[:5],
        'total_entregas_hoy': total_entregas_hoy,
        'recetas_activas': recetas_activas,
        'cobrado_mes': cobrado_mes,
    }

    return render(request, 'base/dashboard.html', context)


def page_not_found(request, exception):
    """Vista 404 amigable: recurso o registro no encontrado."""
    return render(request, '404.html', status=404)


# --- Gestión de Feriados ---

class FeriadoListView(LoginRequiredMixin, ListView):
    """Lista de feriados ordenados por fecha."""
    model = Feriado
    template_name = 'base/feriado_lista.html'
    context_object_name = 'feriados'
    paginate_by = 50

    def get_queryset(self):
        qs = super().get_queryset()
        año = self.request.GET.get('año')
        if año:
            try:
                y = int(año)
                qs = qs.filter(fecha__year=y)
            except ValueError:
                pass
        return qs.order_by('fecha')


class FeriadoCreateView(LoginRequiredMixin, CreateView):
    """Crear un nuevo feriado."""
    model = Feriado
    form_class = FeriadoForm
    template_name = 'base/feriado_form.html'
    success_url = reverse_lazy('feriado_lista')

    def form_valid(self, form):
        messages.success(self.request, 'Feriado creado correctamente.')
        return super().form_valid(form)


class FeriadoUpdateView(LoginRequiredMixin, UpdateView):
    """Editar un feriado."""
    model = Feriado
    form_class = FeriadoForm
    template_name = 'base/feriado_form.html'
    context_object_name = 'feriado'
    success_url = reverse_lazy('feriado_lista')

    def form_valid(self, form):
        messages.success(self.request, 'Feriado actualizado correctamente.')
        return super().form_valid(form)


class FeriadoDeleteView(LoginRequiredMixin, DeleteView):
    """Eliminar un feriado."""
    model = Feriado
    template_name = 'base/feriado_confirm_delete.html'
    context_object_name = 'feriado'
    success_url = reverse_lazy('feriado_lista')

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Feriado eliminado.')
        return super().delete(request, *args, **kwargs)

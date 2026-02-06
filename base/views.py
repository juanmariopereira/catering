"""
Vistas principales del proyecto.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Sum
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy, reverse
from datetime import date, timedelta, datetime

from .models import Feriado, es_feriado
from .forms import FeriadoForm
from planning.models import PlanificacionMenu
from billing.models import Cobro, Pago, _dias_vencimiento_por_frecuencia
from billing.utils import obtener_cobros_vencidos, periodo_hasta_segun_frecuencia
from routes.models import Ruta, RutaCliente
from purchases.models import PrevisionCompra
from clients.models import Cliente
from contracts.models import Contrato, q_filtro_estado
from recipes.models import Receta
from delivery.utils import contratos_con_entrega_en_fecha


@login_required
def dashboard(request):
    """Dashboard principal con indicadores y menú de navegación."""
    hoy = timezone.now().date()

    # Menús planificados del día (fecha + plan)
    menus_hoy = PlanificacionMenu.objects.filter(fecha=hoy)
    total_planificaciones_hoy = menus_hoy.count()

    # Cobranza
    cobros_pendientes = Cobro.objects.filter(estado='pendiente').count()
    cobros_vencidos = obtener_cobros_vencidos().count()
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
    contratos_activos = Contrato.objects.filter(q_filtro_estado('activo')).count()

    # Días útiles consecutivos a partir de mañana con menú para todos los planes que tienen entrega ese día.
    # Día útil = lunes a viernes y no feriado. Se saltan fines de semana y feriados; se corta solo al primer día útil sin menú completo.
    dias_menu_completo = 0
    d = hoy + timedelta(days=1)
    max_dias = 365
    dias_revisados = 0
    while dias_revisados < max_dias:
        if d.weekday() >= 5 or es_feriado(d):
            d += timedelta(days=1)
            dias_revisados += 1
            continue
        planes_con_entrega = set(
            contratos_con_entrega_en_fecha(d).values_list('plan_id', flat=True).distinct()
        )
        menus_plan_ids = set(
            PlanificacionMenu.objects.filter(fecha=d, plan_id__in=planes_con_entrega)
            .values_list('plan_id', flat=True)
        ) if planes_con_entrega else set()
        if planes_con_entrega and not (planes_con_entrega <= menus_plan_ids):
            break
        dias_menu_completo += 1
        d += timedelta(days=1)
        dias_revisados += 1

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

    # Gráfico de línea: pagos recibidos últimos 60 días por plan y total (periodicidad semanal)
    desde_60 = hoy - timedelta(days=59)  # 60 días inclusive
    from collections import defaultdict
    # Semanas: listas de inicio de cada semana que toca el rango [desde_60, hoy]
    semanas_inicio = []
    d = desde_60
    while d <= hoy:
        semanas_inicio.append(d)
        d += timedelta(days=7)
    total_por_semana = defaultdict(lambda: 0)
    por_plan_por_semana = defaultdict(lambda: defaultdict(lambda: 0))
    plan_nombres = {}
    pagos_por_dia_plan = (
        Pago.objects.filter(fecha_pago__gte=desde_60, fecha_pago__lte=hoy)
        .values('fecha_pago', 'cobro__contrato__plan_id', 'cobro__contrato__plan__nombre')
        .annotate(total=Sum('monto'))
    )
    for row in pagos_por_dia_plan:
        fd = row['fecha_pago']
        monto = float(row['total'] or 0)
        plan_id = row['cobro__contrato__plan_id']
        plan_nombre = row['cobro__contrato__plan__nombre'] or 'Sin plan'
        plan_nombres[plan_id] = plan_nombre
        # Asignar a la semana (inicio de la semana de 7 días que contiene fd)
        idx_semana = (fd - desde_60).days // 7
        if idx_semana < len(semanas_inicio):
            inicio_semana = semanas_inicio[idx_semana]
            total_por_semana[inicio_semana] += monto
            por_plan_por_semana[inicio_semana][plan_id] += monto
    chart_labels = [
        '{} - {}'.format(s.strftime('%d/%m'), (s + timedelta(days=6)).strftime('%d/%m'))
        for s in semanas_inicio
    ]
    chart_datasets = []
    colores_plan = ['#7CB342', '#1565c0', '#ff9800', '#9c27b0', '#00acc1', '#5d4037']
    for idx, plan_id in enumerate(sorted(plan_nombres.keys(), key=lambda x: (plan_nombres.get(x) or '', x))):
        chart_datasets.append({
            'label': plan_nombres[plan_id],
            'data': [por_plan_por_semana[s].get(plan_id, 0) for s in semanas_inicio],
            'borderColor': colores_plan[idx % len(colores_plan)],
            'backgroundColor': 'transparent',
            'tension': 0.2,
        })
    chart_datasets.append({
        'label': 'Total',
        'data': [total_por_semana[s] for s in semanas_inicio],
        'borderColor': '#1b5e20',
        'backgroundColor': 'transparent',
        'borderWidth': 2,
        'tension': 0.2,
    })

    # Gráfico de previsión de cobros: pendientes (por fecha venc.) + estimativa futuros (contratos activos) — próximos 2 meses
    horizonte_semanas = 8
    semanas_prevision = [hoy + timedelta(days=7 * i) for i in range(horizonte_semanas)]
    labels_prevision = [
        '{} - {}'.format(s.strftime('%d/%m'), (s + timedelta(days=6)).strftime('%d/%m'))
        for s in semanas_prevision
    ]
    # Asignar una fecha a la semana: usamos el índice (0, 1, 2...) para saber en qué semana cae una fecha
    def semana_index(f):
        d = (f - hoy).days
        if d < 0:
            return -1
        return min(d // 7, horizonte_semanas - 1)
    prev_pendiente_por_semana = defaultdict(lambda: 0)
    cobros_pend = Cobro.objects.filter(
        estado__in=['pendiente', 'vencida'],
        fecha_vencimiento__isnull=False,
    ).values('fecha_vencimiento', 'monto')
    for row in cobros_pend:
        fv = row['fecha_vencimiento']
        idx = semana_index(fv)
        if 0 <= idx < horizonte_semanas:
            prev_pendiente_por_semana[semanas_prevision[idx]] += float(row['monto'] or 0)
    # Estimativa: contratos activos (sin fecha_fin o fecha_fin >= hoy), generar períodos futuros
    prev_estimado_por_semana = defaultdict(lambda: 0)
    contratos_vigentes = Contrato.objects.filter(q_filtro_estado('activo')).filter(
        (Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=hoy))
    ).prefetch_related('cobros')
    horizonte_fin = hoy + timedelta(days=7 * horizonte_semanas)
    for contrato in contratos_vigentes:
        cobros_list = list(contrato.cobros.all())
        cobros_contrato = {(c.periodo_desde, c.periodo_hasta) for c in cobros_list}
        ultimo_cobro = max(cobros_list, key=lambda c: c.periodo_hasta) if cobros_list else None
        if ultimo_cobro:
            next_desde = ultimo_cobro.periodo_hasta + timedelta(days=1)
        else:
            next_desde = max(contrato.fecha_inicio, hoy)
        limite = horizonte_fin
        if contrato.fecha_fin:
            limite = min(limite, contrato.fecha_fin)
        while next_desde <= limite:
            periodo_hasta = periodo_hasta_segun_frecuencia(next_desde, contrato.frecuencia_pago)
            if contrato.fecha_fin and periodo_hasta > contrato.fecha_fin:
                periodo_hasta = contrato.fecha_fin
            if (next_desde, periodo_hasta) not in cobros_contrato:
                fecha_esperada_pago = periodo_hasta + timedelta(
                    days=_dias_vencimiento_por_frecuencia(contrato.frecuencia_pago)
                )
                idx = semana_index(fecha_esperada_pago)
                if 0 <= idx < horizonte_semanas:
                    monto = float(contrato.precio)
                    prev_estimado_por_semana[semanas_prevision[idx]] += monto
            next_desde = periodo_hasta + timedelta(days=1)
            if next_desde > limite:
                break
    datasets_prevision = [
        {
            'label': 'Cobros pendientes (previsión)',
            'data': [prev_pendiente_por_semana[s] for s in semanas_prevision],
            'borderColor': '#f57c00',
            'backgroundColor': 'transparent',
            'tension': 0.2,
        },
        {
            'label': 'Estimado futuros (contratos vigentes)',
            'data': [prev_estimado_por_semana[s] for s in semanas_prevision],
            'borderColor': '#1976d2',
            'backgroundColor': 'transparent',
            'tension': 0.2,
        },
        {
            'label': 'Total previsión',
            'data': [
                prev_pendiente_por_semana[s] + prev_estimado_por_semana[s]
                for s in semanas_prevision
            ],
            'borderColor': '#2e7d32',
            'backgroundColor': 'transparent',
            'borderWidth': 2,
            'tension': 0.2,
        },
    ]

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
        'dias_menu_completo': dias_menu_completo,
        'menus_hoy_lista': menus_hoy.select_related('plan')[:5],
        'total_entregas_hoy': total_entregas_hoy,
        'recetas_activas': recetas_activas,
        'cobrado_mes': cobrado_mes,
        'chart_pagos_config': {'labels': chart_labels, 'datasets': chart_datasets},
        'chart_prevision_config': {'labels': labels_prevision, 'datasets': datasets_prevision},
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

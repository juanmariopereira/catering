from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Q
from django.forms import inlineformset_factory
from datetime import date, timedelta
from collections import defaultdict
from .models import (
    PlanificacionMenu,
    PlanificacionMenuReceta,
    PlanificacionClienteSustituta,
    PlanificacionDieta,
    PlanificacionRecetaSustituta,
)
from .utils import (
    obtener_conflictos_menu_por_cliente,
    recetas_alternativas_para_momento,
)
from contracts.models import Contrato
from diets.models import TipoComida
from plans.models import Plan
from recipes.models import Receta

PlanificacionMenuRecetaFormSet = inlineformset_factory(
    PlanificacionMenu,
    PlanificacionMenuReceta,
    fields=('tipo_comida', 'receta', 'orden'),
    extra=5,
    can_delete=True,
)


@login_required
def resumen_por_fecha(request):
    """
    Cantidad de clientes por plan en una fecha específica.
    Sirve para saber cuántos clientes hay por dieta/plan antes de crear las planificaciones.
    """
    fecha_param = request.GET.get('fecha')
    if fecha_param:
        try:
            fecha = date.fromisoformat(fecha_param)
        except ValueError:
            fecha = timezone.now().date()
    else:
        fecha = timezone.now().date()

    # Contratos activos en esa fecha (estado activo, fecha dentro del rango)
    contratos_fecha = Contrato.objects.filter(
        estado='activo',
        fecha_inicio__lte=fecha,
    ).filter(
        Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=fecha)
    ).select_related('plan', 'cliente')

    # Agrupar por plan: plan -> [contratos]
    por_plan = defaultdict(list)
    for c in contratos_fecha:
        por_plan[c.plan].append(c)

    # PlanificacionMenu por (fecha, plan) para enlazar Editar/Crear menú
    menus_por_plan = {
        pm.plan_id: pm
        for pm in PlanificacionMenu.objects.filter(fecha=fecha).select_related('plan')
    }
    # Lista de (plan, cantidad, contratos, planificacion_menu) para el template (dieta no utilizada por ahora)
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

    # Avisos pendientes: clientes con ingredientes no deseados en el menú (para resumen rápido)
    avisos_pendientes = 0
    for r in resumen:
        if not r['planificacion_menu'] or not r['contratos']:
            continue
        for c in r['contratos']:
            if obtener_conflictos_menu_por_cliente(r['planificacion_menu'], c):
                avisos_pendientes += 1
    fecha_anterior = fecha - timedelta(days=1)
    fecha_siguiente = fecha + timedelta(days=1)

    context = {
        'fecha': fecha,
        'resumen': resumen,
        'fecha_anterior': fecha_anterior,
        'fecha_siguiente': fecha_siguiente,
        'total_clientes': sum(r['cantidad'] for r in resumen),
        'menus_creados': len([r for r in resumen if r['planificacion_menu']]),
        'avisos_pendientes': avisos_pendientes,
    }
    return render(request, 'planning/resumen_por_fecha.html', context)


@login_required
def clientes_reciben_fecha(request):
    """
    Lista de clientes por plan que recibirán sus comidas en una fecha.
    Si algún ingrediente del menú no es del agrado del cliente (parametrizado),
    se muestra un aviso y enlace para definir sustituciones (editar menú por cliente).
    """
    fecha_param = request.GET.get('fecha')
    if fecha_param:
        try:
            fecha = date.fromisoformat(fecha_param)
        except ValueError:
            fecha = timezone.now().date()
    else:
        fecha = timezone.now().date()

    menus_por_plan = {
        pm.plan_id: pm
        for pm in PlanificacionMenu.objects.filter(fecha=fecha).select_related('plan')
    }
    contratos_fecha = Contrato.objects.filter(
        estado='activo',
        fecha_inicio__lte=fecha,
    ).filter(
        Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=fecha)
    ).select_related('plan', 'cliente')

    filas = []
    for c in contratos_fecha:
        menu = menus_por_plan.get(c.plan_id)
        if not menu:
            continue
        conflictos = obtener_conflictos_menu_por_cliente(menu, c)
        tiene_aviso = len(conflictos) > 0
        filas.append({
            'plan': c.plan,
            'contrato': c,
            'cliente': c.cliente,
            'planificacion_menu': menu,
            'tiene_aviso': tiene_aviso,
            'conflictos_count': len(conflictos),
        })

    fecha_anterior = fecha - timedelta(days=1)
    fecha_siguiente = fecha + timedelta(days=1)
    context = {
        'fecha': fecha,
        'filas': filas,
        'fecha_anterior': fecha_anterior,
        'fecha_siguiente': fecha_siguiente,
    }
    return render(request, 'planning/clientes_reciben_fecha.html', context)


class PlanificacionMenuListView(LoginRequiredMixin, ListView):
    """Lista de planificaciones por fecha y plan (menús)."""
    model = PlanificacionMenu
    template_name = 'planning/planificacion_lista.html'
    context_object_name = 'planificaciones'
    paginate_by = 30

    def get_queryset(self):
        queryset = PlanificacionMenu.objects.all().select_related('plan')
        fecha_param = self.request.GET.get('fecha')
        if fecha_param:
            try:
                fecha = date.fromisoformat(fecha_param)
                queryset = queryset.filter(fecha=fecha)
            except ValueError:
                pass
        plan_id = self.request.GET.get('plan')
        if plan_id:
            queryset = queryset.filter(plan_id=plan_id)
        return queryset.order_by('-fecha', 'plan__nombre')


class PlanificacionMenuCreateView(LoginRequiredMixin, CreateView):
    """Crear menú planificado (fecha + plan). Redirige a editar para añadir recetas por momento."""
    model = PlanificacionMenu
    template_name = 'planning/planificacion_menu_form.html'
    fields = ['fecha', 'plan', 'notas']
    success_url = reverse_lazy('planning:lista')

    def get_initial(self):
        initial = super().get_initial()
        fecha_param = self.request.GET.get('fecha')
        plan_id = self.request.GET.get('plan')
        if fecha_param:
            try:
                initial['fecha'] = date.fromisoformat(fecha_param)
            except ValueError:
                pass
        if plan_id:
            initial['plan'] = plan_id
        return initial

    def form_valid(self, form):
        obj = form.save()
        messages.success(self.request, 'Menú creado. Añada las recetas por momento del día.')
        return redirect(reverse('planning:editar', args=[obj.pk]))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['planes'] = Plan.objects.filter(activo=True).order_by('nombre')
        return context


class PlanificacionMenuUpdateView(LoginRequiredMixin, UpdateView):
    """Editar menú: recetas por tipo_comida (formset) y sustituciones por cliente."""
    model = PlanificacionMenu
    template_name = 'planning/planificacion_menu_form.html'
    fields = ['fecha', 'plan', 'notas']
    success_url = reverse_lazy('planning:lista')
    context_object_name = 'planificacion_menu'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.object
        if self.request.POST:
            context['receta_formset'] = PlanificacionMenuRecetaFormSet(
                self.request.POST, instance=obj
            )
        else:
            context['receta_formset'] = PlanificacionMenuRecetaFormSet(instance=obj)
        # Contratos activos en esta fecha con este plan (para sustituciones por cliente)
        fecha = obj.fecha
        contratos = Contrato.objects.filter(
            plan=obj.plan,
            estado='activo',
            fecha_inicio__lte=fecha,
        ).filter(
            Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=fecha)
        ).select_related('cliente')
        context['contratos_fecha'] = contratos
        # Por cada contrato: conflictos (recetas del menú con ingredientes no gustados) y sustituciones actuales
        sustituciones_actuales = {
            (s.contrato_id, s.tipo_comida_id, s.receta_original_id): s.receta_sustituta_id
            for s in PlanificacionClienteSustituta.objects.filter(
                fecha=fecha, contrato__in=contratos
            ).select_related('tipo_comida', 'receta_original', 'receta_sustituta')
        }
        recetas_todas = list(Receta.objects.filter(activa=True).order_by('nombre'))
        clientes_conflictos = []
        for c in contratos:
            conflictos = obtener_conflictos_menu_por_cliente(obj, c)
            for cf in conflictos:
                cf['alternativas'] = recetas_alternativas_para_momento(
                    cf['tipo_comida'].id, cf['receta'].id, c.cliente_id,
                    categoria_preferida=cf['receta'].categoria,
                )
                ids_alt = {r.id for r in cf['alternativas']}
                cf['otras_recetas'] = [
                    r for r in recetas_todas
                    if r.id != cf['receta'].id and r.id not in ids_alt
                ]
                key = (c.id, cf['tipo_comida'].id, cf['receta'].id)
                cf['sustitucion_actual_id'] = sustituciones_actuales.get(key)
            clientes_conflictos.append({'contrato': c, 'conflictos': conflictos})
        context['clientes_conflictos'] = clientes_conflictos
        context['recetas_todas'] = recetas_todas
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        receta_formset = context['receta_formset']
        if receta_formset.is_valid():
            form.save()
            receta_formset.save()
            self._guardar_sustituciones_cliente()
            messages.success(self.request, 'Menú actualizado correctamente.')
            return redirect(self.get_success_url())
        return self.render_to_response(self.get_context_data(form=form))

    def _guardar_sustituciones_cliente(self):
        """Guardar PlanificacionClienteSustituta desde POST sustituir_contrato_X_tipo_Y_receta_Z."""
        for key in self.request.POST:
            if not key.startswith('sustituir_contrato_'):
                continue
            # sustituir_contrato_3_tipo_1_receta_5 -> contrato 3, tipo 1, receta 5
            parts = key.replace('sustituir_contrato_', '').split('_tipo_')
            if len(parts) != 2:
                continue
            try:
                contrato_id = int(parts[0])
            except ValueError:
                continue
            part2 = parts[1].split('_receta_')
            if len(part2) != 2:
                continue
            try:
                tipo_comida_id = int(part2[0])
                receta_original_id = int(part2[1])
            except ValueError:
                continue
            fecha = self.object.fecha
            receta_sustituta_id = self.request.POST.get(key, '').strip()
            if not receta_sustituta_id:
                PlanificacionClienteSustituta.objects.filter(
                    fecha=fecha,
                    contrato_id=contrato_id,
                    tipo_comida_id=tipo_comida_id,
                    receta_original_id=receta_original_id,
                ).delete()
                continue
            try:
                receta_sustituta_id = int(receta_sustituta_id)
            except (ValueError, TypeError):
                continue
            if receta_sustituta_id == receta_original_id:
                PlanificacionClienteSustituta.objects.filter(
                    fecha=fecha,
                    contrato_id=contrato_id,
                    tipo_comida_id=tipo_comida_id,
                    receta_original_id=receta_original_id,
                ).delete()
                continue
            PlanificacionClienteSustituta.objects.update_or_create(
                fecha=fecha,
                contrato_id=contrato_id,
                tipo_comida_id=tipo_comida_id,
                receta_original_id=receta_original_id,
                defaults={'receta_sustituta_id': receta_sustituta_id},
            )


class PlanificacionMenuDeleteView(LoginRequiredMixin, DeleteView):
    """Eliminar planificación menú (fecha + plan)."""
    model = PlanificacionMenu
    template_name = 'planning/planificacion_confirm_delete.html'
    success_url = reverse_lazy('planning:lista')
    context_object_name = 'planificacion_menu'

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Menú eliminado.')
        return super().delete(request, *args, **kwargs)


@login_required
def calendario_planificacion(request, year=None, month=None):
    """Vista para mostrar calendario de planificaciones"""
    if year and month:
        try:
            fecha = date(int(year), int(month), 1)
        except ValueError:
            fecha = timezone.now().date().replace(day=1)
    else:
        fecha = timezone.now().date().replace(day=1)
    
    # Calcular primer y último día del mes
    if fecha.month == 12:
        siguiente_mes = fecha.replace(year=fecha.year + 1, month=1)
    else:
        siguiente_mes = fecha.replace(month=fecha.month + 1)
    
    ultimo_dia = (siguiente_mes - timedelta(days=1)).day
    
    # Menús planificados por fecha (PlanificacionMenu)
    planificaciones = PlanificacionMenu.objects.filter(
        fecha__year=fecha.year,
        fecha__month=fecha.month
    ).select_related('plan')

    planificaciones_por_dia = {}
    for planificacion in planificaciones:
        dia = planificacion.fecha.day
        if dia not in planificaciones_por_dia:
            planificaciones_por_dia[dia] = []
        planificaciones_por_dia[dia].append(planificacion)
    
    # Calcular mes anterior y siguiente
    if fecha.month == 1:
        mes_anterior = fecha.replace(year=fecha.year - 1, month=12)
    else:
        mes_anterior = fecha.replace(month=fecha.month - 1)
    
    context = {
        'fecha': fecha,
        'mes_anterior': mes_anterior,
        'mes_siguiente': siguiente_mes,
        'ultimo_dia': ultimo_dia,
        'planificaciones_por_dia': planificaciones_por_dia,
    }
    
    return render(request, 'planning/calendario.html', context)

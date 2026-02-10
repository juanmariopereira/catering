from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.forms import inlineformset_factory
from datetime import date
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from .models import PlanificacionMenu, PlanificacionMenuReceta
from .forms import PlanificacionMenuForm, PlanificacionMenuRecetaForm
from .services import (
    get_resumen_por_fecha,
    get_clientes_reciben_fecha,
    get_contratos_sin_entregador_fecha,
    get_calendario_data,
    list_planificaciones_queryset,
    get_planificacion_list_context,
    get_planificacion_existente_fecha_plan,
    get_planificacion_menu_create_initial,
    get_planificacion_menu_create_context,
    get_recetas_por_tipo,
    get_recetas_del_menu,
    get_etiqueta_dieta_data,
    get_etiquetas_masivo_data,
    get_planificacion_menu_editar_context,
    guardar_sustituciones_from_post,
    guardar_dietas_personalizadas_from_post,
    actualizar_planificacion_menu,
    guardar_recetas_planificacion_menu,
    crear_planificacion_menu,
    crear_planificacion_menu_con_recetas,
)
from .services.ai_menu import sugerir_menu_ia

from plans.models import Plan

BasePlanificacionMenuRecetaFormSet = inlineformset_factory(
    PlanificacionMenu,
    PlanificacionMenuReceta,
    form=PlanificacionMenuRecetaForm,
    fields=('tipo_comida', 'receta', 'orden'),
    extra=1,
    can_delete=True,
)


class PlanificacionMenuRecetaFormSet(BasePlanificacionMenuRecetaFormSet):
    """Formset que pasa receta_counts al form para mostrar [N] clientes en el select."""

    def __init__(self, *args, receta_counts=None, **kwargs):
        self.receta_counts = receta_counts or {}
        super().__init__(*args, **kwargs)

    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        kwargs['receta_counts'] = self.receta_counts
        return kwargs


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
    context = get_resumen_por_fecha(fecha)
    return render(request, 'planning/resumen_por_fecha.html', context)


@login_required
def clientes_reciben_fecha(request):
    """
    Lista de clientes por plan que recibirán sus comidas en una fecha.
    Filtros: plan, entregador, cliente (texto), vigencia del contrato.
    """
    fecha_param = request.GET.get('fecha')
    if fecha_param:
        try:
            fecha = date.fromisoformat(fecha_param)
        except ValueError:
            fecha = timezone.now().date()
    else:
        fecha = timezone.now().date()
    context = get_clientes_reciben_fecha(
        fecha=fecha,
        filtro_plan=request.GET.get('plan', '').strip() or None,
        filtro_entregador=request.GET.get('entregador', '').strip() or None,
        filtro_cliente=request.GET.get('cliente', '').strip() or None,
        filtro_vigencia=request.GET.get('vigencia', '').strip() or None,
    )
    return render(request, 'planning/clientes_reciben_fecha.html', context)


@login_required
def contratos_sin_entregador_fecha(request):
    """
    Detalle de contratos que reciben menú en la fecha pero no tienen repartidor asignado.
    """
    fecha_param = request.GET.get('fecha')
    if fecha_param:
        try:
            fecha = date.fromisoformat(fecha_param)
        except ValueError:
            fecha = timezone.now().date()
    else:
        fecha = timezone.now().date()
    context = get_contratos_sin_entregador_fecha(fecha)
    return render(request, 'planning/contratos_sin_entregador_fecha.html', context)


@login_required
@require_http_methods(['POST'])
def sugerir_menu_ia_view(request):
    """
    Vista AJAX que sugiere un menú usando OpenAI.
    POST: fecha (YYYY-MM-DD), plan (ID)
    Returns: JSON { "ok": true, "recetas": [{ tipo_comida_id, receta_id, orden }] } o { "ok": false, "error": "..." }
    """
    fecha_str = request.POST.get('fecha')
    plan_id_str = request.POST.get('plan')

    if not fecha_str or not plan_id_str:
        return JsonResponse({'ok': False, 'error': 'Faltan fecha o plan.'}, status=400)

    try:
        fecha = date.fromisoformat(fecha_str)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Fecha inválida.'}, status=400)

    try:
        plan_id = int(plan_id_str)
    except (ValueError, TypeError):
        return JsonResponse({'ok': False, 'error': 'Plan inválido.'}, status=400)

    plan = get_object_or_404(Plan, pk=plan_id)
    idea_menu = (request.POST.get('idea_menu') or '').strip() or None

    try:
        recetas = sugerir_menu_ia(fecha, plan, request=request, idea_menu=idea_menu)
        return JsonResponse({'ok': True, 'recetas': recetas})
    except ValueError as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse(
            {'ok': False, 'error': f'Error al generar sugerencia: {e}'},
            status=500,
        )


class PlanificacionMenuListView(LoginRequiredMixin, ListView):
    """Lista de planificaciones por fecha y plan (menús)."""
    model = PlanificacionMenu
    template_name = 'planning/planificacion_lista.html'
    context_object_name = 'planificaciones'
    paginate_by = 30

    def get_queryset(self):
        g = self.request.GET
        return list_planificaciones_queryset(
            fecha_desde=g.get('fecha_desde'),
            fecha_hasta=g.get('fecha_hasta'),
            plan_id=g.get('plan'),
            sort_param=g.get('sort'),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_planificacion_list_context(self.request.GET))
        return context


class PlanificacionMenuCreateView(LoginRequiredMixin, CreateView):
    """Crear menú planificado (fecha + plan). Una sola planificación por (fecha, plan)."""
    model = PlanificacionMenu
    form_class = PlanificacionMenuForm
    template_name = 'planning/planificacion_menu_form.html'
    success_url = reverse_lazy('planning:lista')

    def get(self, request, *args, **kwargs):
        existente = get_planificacion_existente_fecha_plan(
            request.GET.get('fecha'),
            request.GET.get('plan'),
        )
        if existente:
            messages.info(
                request,
                f'Ya existe una planificación para el {existente.fecha.strftime("%d/%m/%Y")} con ese plan. Redirigido a edición.'
            )
            return redirect(reverse('planning:editar', args=[existente.pk]))
        return super().get(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        initial.update(get_planificacion_menu_create_initial(self.request.GET))
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        initial = self.get_initial()
        create_ctx = get_planificacion_menu_create_context(
            initial.get('fecha'),
            initial.get('plan'),
        )
        context.update(create_ctx)
        receta_counts = create_ctx['receta_counts']
        if self.request.POST:
            context['receta_formset'] = PlanificacionMenuRecetaFormSet(
                self.request.POST, instance=self.object, receta_counts=receta_counts
            )
        else:
            context['receta_formset'] = PlanificacionMenuRecetaFormSet(
                instance=self.object, receta_counts=receta_counts
            )
        return context

    def form_valid(self, form):
        planificacion = crear_planificacion_menu(form.cleaned_data)
        receta_counts = get_planificacion_menu_create_context(
            planificacion.fecha,
            planificacion.plan_id,
        )['receta_counts']
        receta_formset = PlanificacionMenuRecetaFormSet(
            self.request.POST,
            instance=planificacion,
            receta_counts=receta_counts,
        )
        if receta_formset.is_valid():
            guardar_recetas_planificacion_menu(
                planificacion,
                [f.cleaned_data for f in receta_formset if f.cleaned_data and not f.cleaned_data.get('DELETE')],
            )
            messages.success(
                self.request,
                'Menú creado con las recetas por momento del día. Puede editar sustituciones por cliente si lo necesita.'
            )
            return redirect(reverse('planning:editar', args=[planificacion.pk]))
        messages.warning(
            self.request,
            'Menú creado. Revise las recetas a continuación y guarde de nuevo si hizo cambios.'
        )
        return self.render_to_response(self.get_context_data(form=form))


class PlanificacionMenuUpdateView(LoginRequiredMixin, UpdateView):
    """Editar menú: recetas por tipo_comida (formset) y sustituciones por cliente."""
    model = PlanificacionMenu
    form_class = PlanificacionMenuForm
    template_name = 'planning/planificacion_menu_form.html'
    success_url = reverse_lazy('planning:lista')
    context_object_name = 'planificacion_menu'

    def get_queryset(self):
        g = self.request.GET
        return list_planificaciones_queryset(
            fecha_desde=g.get('fecha_desde'),
            fecha_hasta=g.get('fecha_hasta'),
            plan_id=g.get('plan'),
            sort_param=g.get('sort'),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.object
        editar_ctx = get_planificacion_menu_editar_context(obj)
        receta_counts = editar_ctx.pop('receta_counts')
        context.update(editar_ctx)
        if self.request.POST:
            context['receta_formset'] = PlanificacionMenuRecetaFormSet(
                self.request.POST, instance=obj, receta_counts=receta_counts
            )
        else:
            context['receta_formset'] = PlanificacionMenuRecetaFormSet(
                instance=obj, receta_counts=receta_counts
            )
        return context

    def form_valid(self, form):
        actualizar_planificacion_menu(self.object, form.cleaned_data)
        guardar_sustituciones_from_post(self.object, self.request.POST)
        guardar_dietas_personalizadas_from_post(self.object, self.request.POST)
        context = self.get_context_data(form=form)
        receta_formset = context['receta_formset']
        if receta_formset.is_valid():
            guardar_recetas_planificacion_menu(
                self.object,
                [f.cleaned_data for f in receta_formset if f.cleaned_data and not f.cleaned_data.get('DELETE')],
            )
            messages.success(self.request, 'Menú actualizado correctamente.')
            return redirect(self.get_success_url())
        messages.warning(
            self.request,
            'Menú y excepciones guardados. Revise los errores en «Recetas por momento del día» y guarde de nuevo si hace falta.'
        )
        return self.render_to_response(context)


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
    context = get_calendario_data(year=year, month=month)
    return render(request, 'planning/calendario.html', context)


@login_required
@require_http_methods(['GET'])
def recetas_por_tipo_ajax(request):
    """AJAX: devuelve recetas activas filtradas por tipo de comida (momentos_dia)."""
    recetas = get_recetas_por_tipo(request.GET.get('tipo_comida_id', '').strip())
    return JsonResponse({
        'recetas': [{'id': r[0], 'nombre': r[1]} for r in recetas],
    })


@login_required
@require_http_methods(['GET'])
def recetas_del_menu_ajax(request):
    """AJAX: devuelve recetas del menú de una planificación para un tipo de comida."""
    planificacion_id = request.GET.get('planificacion_id', '').strip()
    tipo_id = request.GET.get('tipo_comida_id', '').strip()
    recetas = get_recetas_del_menu(planificacion_id, tipo_id)
    return JsonResponse({
        'recetas': [{'id': r[0], 'nombre': r[1]} for r in recetas],
    })


@login_required
def etiqueta_dieta(request, planificacion_id, contrato_id):
    """
    Vista para imprimir la etiqueta de la dieta enviada a un cliente.
    """
    data, error = get_etiqueta_dieta_data(planificacion_id, contrato_id)
    if error:
        messages.warning(request, error)
        return redirect('planning:lista')
    return render(request, 'planning/etiqueta_dieta.html', data)


@login_required
@require_http_methods(['GET'])
def etiquetas_dieta_masivo(request):
    """
    Impresión masiva: una sola página con todas las etiquetas seleccionadas.
    GET ids: planificacion_id/contrato_id separados por coma (ej. ids=27/132,27/133,27/134).
    """
    ids_param = request.GET.get('ids', '').strip()
    if not ids_param:
        messages.warning(request, 'No se indicaron etiquetas.')
        return redirect('planning:clientes_por_fecha')
    etiquetas = get_etiquetas_masivo_data(ids_param)
    if not etiquetas:
        messages.warning(request, 'No hay etiquetas válidas para mostrar.')
        return redirect('planning:clientes_por_fecha')
    return render(request, 'planning/etiquetas_dieta_masivo.html', {'etiquetas': etiquetas})

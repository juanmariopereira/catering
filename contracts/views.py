from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, FormView
from django.urls import reverse_lazy, reverse
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required

from .models import Contrato, PausaContrato
from .forms import ContratoForm, PausaContratoForm, DiasExtraForm
from .services import (
    list_contratos_queryset,
    get_contrato_detalle_data,
    get_contrato_list_context,
    get_contrato_create_initial,
    get_contrato_create_context,
    get_cliente_direccion_data,
    get_ultimo_contrato_direccion_data,
    aplicar_dias_extra,
)


class ContratoListView(LoginRequiredMixin, ListView):
    model = Contrato
    template_name = 'contracts/contrato_lista.html'
    context_object_name = 'contratos'
    paginate_by = 50
    PER_PAGE_OPTIONS = (50, 500, 2000)

    def get_queryset(self):
        get = self.request.GET
        return list_contratos_queryset(
            busqueda=get.get('q', '').strip() or None,
            estado=get.get('estado') or None,
            plan_id=get.get('plan') or None,
            cliente_id=get.get('cliente') or None,
            vencimiento_desde=get.get('vencimiento_desde') or None,
            vencimiento_hasta=get.get('vencimiento_hasta') or None,
            sort_param=get.get('sort') or None,
        )

    def get_paginate_by(self, queryset):
        per = self.request.GET.get('per_page')
        try:
            n = int(per) if per else None
            if n is not None and n in self.PER_PAGE_OPTIONS:
                return n
        except (ValueError, TypeError):
            pass
        return self.paginate_by

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = self.get_queryset()
        list_ctx = get_contrato_list_context(
            self.request.GET,
            per_page_current=self.get_paginate_by(qs),
            per_page_options=self.PER_PAGE_OPTIONS,
        )
        context.update(list_ctx)
        return context


class ContratoCreateView(LoginRequiredMixin, CreateView):
    model = Contrato
    form_class = ContratoForm
    template_name = 'contracts/contrato_form.html'
    success_url = reverse_lazy('contracts:lista')

    def get_initial(self):
        initial = super().get_initial()
        initial.update(get_contrato_create_initial(self.request.GET.get('plan')))
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if not self.object:
            context.update(get_contrato_create_context())
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Contrato creado exitosamente.')
        return super().form_valid(form)


@login_required
@require_http_methods(['POST'])
def generar_mensaje_cliente_view(request):
    """
    Vista AJAX: genera mensaje personalizado para el cliente con IA.
    POST: contrato_id, tipo_mensaje (preguntar_dieta | plan_por_vencer | plan_vencido)
    Returns: JSON { "ok": true, "mensaje": "..." }
    """
    contrato_id = request.POST.get('contrato_id')
    tipo_mensaje = request.POST.get('tipo_mensaje')
    if not contrato_id or not tipo_mensaje:
        return JsonResponse({'ok': False, 'error': 'Faltan contrato_id o tipo_mensaje.'}, status=400)
    contrato = get_object_or_404(Contrato, pk=contrato_id)
    try:
        from .services.ai_mensajes import generar_mensaje_cliente_ia, TIPOS_MENSAJE
        tipos_validos = [t[0] for t in TIPOS_MENSAJE]
        if tipo_mensaje not in tipos_validos:
            return JsonResponse({'ok': False, 'error': 'Tipo de mensaje inválido.'}, status=400)
        mensaje = generar_mensaje_cliente_ia(contrato, tipo_mensaje, request=request)
        return JsonResponse({'ok': True, 'mensaje': mensaje})
    except ValueError as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(['GET'])
def ajax_direccion_cliente(request, cliente_id):
    """
    Devuelve la dirección y link_maps del cliente (para rellenar el formulario de contrato).
    GET: /contracts/ajax/cliente/<id>/direccion/
    """
    from clients.models import Cliente
    cliente = get_object_or_404(Cliente, pk=cliente_id)
    return JsonResponse(get_cliente_direccion_data(cliente))


@login_required
@require_http_methods(['GET'])
def ajax_ultimo_contrato_direccion(request, cliente_id):
    """
    Devuelve la dirección del último contrato activo del cliente (para copiar en nuevo contrato).
    GET: /contracts/ajax/cliente/<id>/ultimo-contrato-direccion/?exclude_contrato=<pk>
    """
    from clients.models import Cliente
    cliente = get_object_or_404(Cliente, pk=cliente_id)
    data = get_ultimo_contrato_direccion_data(
        cliente,
        exclude_contrato_pk=request.GET.get('exclude_contrato'),
    )
    return JsonResponse(data)


class ContratoDetailView(LoginRequiredMixin, DetailView):
    model = Contrato
    template_name = 'contracts/contrato_detalle.html'
    context_object_name = 'contrato'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_contrato_detalle_data(self.object))
        return context


class ContratoDiasExtraView(LoginRequiredMixin, FormView):
    """Vista para dar días extra de catering: extiende vigencia del contrato y del último cobro."""
    form_class = DiasExtraForm
    template_name = 'contracts/dias_extra_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.contrato = get_object_or_404(Contrato, pk=kwargs['pk'])
        if self.contrato.estado == 'cancelado':
            messages.error(request, 'No se pueden dar días extra a un contrato cancelado.')
            return redirect('contracts:detalle', pk=self.contrato.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['contrato'] = self.contrato
        return context

    def form_valid(self, form):
        dias_agregados = form.cleaned_data['dias_agregados']
        motivo = form.cleaned_data['motivo'].strip()
        try:
            aplicar_dias_extra(self.contrato, dias_agregados, motivo)
        except ValueError as e:
            messages.error(self.request, str(e))
            return redirect('contracts:detalle', pk=self.contrato.pk)
        messages.success(
            self.request,
            f'Se agregaron {dias_agregados} día(s) de catering. Vigencia del contrato y del cobro extendida. Motivo: {motivo}.',
        )
        return redirect('contracts:detalle', pk=self.contrato.pk)


class ContratoUpdateView(LoginRequiredMixin, UpdateView):
    model = Contrato
    form_class = ContratoForm
    template_name = 'contracts/contrato_form.html'
    context_object_name = 'contrato'

    def get_success_url(self):
        return reverse('contracts:detalle', args=[self.object.pk])

    def form_valid(self, form):
        messages.success(self.request, 'Contrato actualizado exitosamente.')
        return super().form_valid(form)


class ContratoDeleteView(LoginRequiredMixin, DeleteView):
    model = Contrato
    template_name = 'contracts/contrato_confirm_delete.html'
    success_url = reverse_lazy('contracts:lista')

    def form_valid(self, form):
        messages.success(self.request, 'Contrato eliminado exitosamente.')
        return super().form_valid(form)


class PausaContratoCreateView(LoginRequiredMixin, CreateView):
    model = PausaContrato
    form_class = PausaContratoForm
    template_name = 'contracts/pausa_form.html'
    context_object_name = 'pausa'

    def dispatch(self, request, *args, **kwargs):
        self.contrato = get_object_or_404(Contrato, pk=kwargs['contrato_pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['contrato'] = self.contrato
        return context

    def form_valid(self, form):
        form.instance.contrato = self.contrato
        messages.success(self.request, 'Pausa añadida correctamente.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('contracts:detalle', args=[self.object.contrato_id])


class PausaContratoUpdateView(LoginRequiredMixin, UpdateView):
    model = PausaContrato
    form_class = PausaContratoForm
    template_name = 'contracts/pausa_form.html'
    context_object_name = 'pausa'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['contrato'] = self.object.contrato
        return context

    def get_success_url(self):
        return reverse('contracts:detalle', args=[self.object.contrato_id])

    def form_valid(self, form):
        messages.success(self.request, 'Pausa actualizada correctamente.')
        return super().form_valid(form)


class PausaContratoDeleteView(LoginRequiredMixin, DeleteView):
    model = PausaContrato
    template_name = 'contracts/pausa_confirm_delete.html'
    context_object_name = 'pausa'

    def get_success_url(self):
        return reverse('contracts:detalle', args=[self.object.contrato_id])

    def form_valid(self, form):
        messages.success(self.request, 'Pausa eliminada.')
        return super().form_valid(form)

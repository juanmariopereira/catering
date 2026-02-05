from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy, reverse
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required

from .models import Contrato, PausaContrato
from .forms import ContratoForm, PausaContratoForm
from plans.models import Plan
from clients.models import Cliente
from billing.models import Cobro


class ContratoListView(LoginRequiredMixin, ListView):
    model = Contrato
    template_name = 'contracts/contrato_lista.html'
    context_object_name = 'contratos'
    paginate_by = 30

    def get_queryset(self):
        queryset = super().get_queryset()
        busqueda = self.request.GET.get('q')
        if busqueda:
            queryset = queryset.filter(
                Q(cliente__nombre__icontains=busqueda) | Q(plan__nombre__icontains=busqueda)
            )
        estado = self.request.GET.get('estado')
        if estado:
            queryset = queryset.filter(estado=estado)
        return queryset.select_related('cliente', 'plan').order_by('-fecha_creacion')


class ContratoCreateView(LoginRequiredMixin, CreateView):
    model = Contrato
    form_class = ContratoForm
    template_name = 'contracts/contrato_form.html'
    success_url = reverse_lazy('contracts:lista')

    def get_initial(self):
        initial = super().get_initial()
        plan_id = self.request.GET.get('plan')
        if plan_id:
            try:
                plan = Plan.objects.get(pk=plan_id, activo=True)
                initial['plan'] = plan.pk
                initial['precio'] = plan.precio_base
            except Plan.DoesNotExist:
                pass
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if not self.object:
            context['plan_precios'] = {str(p.id): str(p.precio_base) for p in Plan.objects.filter(activo=True)}
            context['clientes_datos'] = {
                str(c.id): {'direccion': c.direccion or '', 'link_maps': c.link_maps or ''}
                for c in Cliente.objects.all()
            }
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


class ContratoDetailView(LoginRequiredMixin, DetailView):
    model = Contrato
    template_name = 'contracts/contrato_detalle.html'
    context_object_name = 'contrato'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['pausas'] = self.object.pausas.all().order_by('-fecha_inicio')
        context['cobros'] = (
            Cobro.objects.filter(contrato=self.object)
            .prefetch_related('pagos')
            .order_by('-periodo_hasta', '-numero_cobro')
        )
        return context


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

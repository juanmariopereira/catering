from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.db.models import Q, Max
from django.urls import reverse_lazy, reverse
from django.shortcuts import redirect
from django.contrib import messages
from django.forms import inlineformset_factory

from .models import Cliente, IngredienteNoGustado


IngredienteNoGustadoFormSet = inlineformset_factory(
    Cliente,
    IngredienteNoGustado,
    fields=['ingrediente', 'motivo'],
    extra=2,
    can_delete=True,
)


class ClienteListView(LoginRequiredMixin, ListView):
    model = Cliente
    template_name = 'clients/cliente_lista.html'
    context_object_name = 'clientes'
    paginate_by = 30
    PER_PAGE_OPTIONS = (30, 50, 100, 500)

    ORDER_FIELDS = {
        'nombre': 'nombre',
        '-nombre': '-nombre',
        'email': 'email',
        '-email': '-email',
        'estado': 'activo',
        '-estado': '-activo',
        'ultimo_contrato': 'ultimo_contrato_fecha',
        '-ultimo_contrato': '-ultimo_contrato_fecha',
    }

    def get_queryset(self):
        queryset = super().get_queryset()
        busqueda = self.request.GET.get('q')
        if busqueda:
            queryset = queryset.filter(
                Q(nombre__icontains=busqueda) | Q(email__icontains=busqueda) | Q(telefono__icontains=busqueda)
            )
        activo = self.request.GET.get('activo')
        if activo is not None and activo != '':
            queryset = queryset.filter(activo=activo == '1')

        queryset = queryset.annotate(
            ultimo_contrato_fecha=Max('contratos__fecha_creacion')
        )
        order = (self.request.GET.get('order') or 'nombre').strip()
        if order in self.ORDER_FIELDS:
            order_field = self.ORDER_FIELDS[order]
            queryset = queryset.order_by(order_field)
        else:
            queryset = queryset.order_by('nombre')
        return queryset

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
        get = self.request.GET.copy()
        get.pop('order', None)
        get.pop('page', None)
        context['query_base'] = get.urlencode()
        context['order_current'] = (self.request.GET.get('order') or 'nombre').strip()
        context['per_page_current'] = self.get_paginate_by(self.get_queryset())
        context['per_page_options'] = self.PER_PAGE_OPTIONS
        return context


class ClienteCreateView(LoginRequiredMixin, CreateView):
    model = Cliente
    template_name = 'clients/cliente_form.html'
    fields = ['nombre', 'email', 'telefono', 'direccion', 'link_maps', 'titular', 'activo', 'notas']
    success_url = reverse_lazy('clients:lista')

    def form_valid(self, form):
        messages.success(self.request, 'Cliente creado exitosamente.')
        return super().form_valid(form)


class ClienteDetailView(LoginRequiredMixin, DetailView):
    model = Cliente
    template_name = 'clients/cliente_detalle.html'
    context_object_name = 'cliente'

    def get_context_data(self, **kwargs):
        from django.db.models import Q
        from contracts.models import Contrato
        from billing.models import Factura
        context = super().get_context_data(**kwargs)
        cliente = self.object
        # Contratos del cliente y de sus dependientes (activos e inactivos)
        contratos_todos = (
            Contrato.objects.filter(
                Q(cliente=cliente) | Q(cliente__titular=cliente)
            )
            .select_related('cliente', 'plan')
            .order_by('-fecha_creacion')
        )
        # Primera factura pendiente o vencida por contrato (para botón Cobrar)
        factura_pendiente_por_contrato = {}
        if contratos_todos:
            ids = [c.pk for c in contratos_todos]
            for f in Factura.objects.filter(
                contrato_id__in=ids,
                estado__in=['pendiente', 'vencida']
            ).order_by('contrato_id', 'periodo_desde'):
                if f.contrato_id not in factura_pendiente_por_contrato:
                    factura_pendiente_por_contrato[f.contrato_id] = f
        context['contratos_todos'] = contratos_todos
        context['factura_pendiente_por_contrato'] = factura_pendiente_por_contrato
        return context


class ClienteUpdateView(LoginRequiredMixin, UpdateView):
    model = Cliente
    template_name = 'clients/cliente_form.html'
    fields = ['nombre', 'email', 'telefono', 'direccion', 'link_maps', 'titular', 'activo', 'notas']
    context_object_name = 'cliente'

    def get_success_url(self):
        return reverse('clients:detalle', args=[self.object.pk])

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if self.object and self.object.pk:
            form.fields['titular'].queryset = form.fields['titular'].queryset.exclude(pk=self.object.pk)
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['formset'] = IngredienteNoGustadoFormSet(
                self.request.POST, instance=self.object
            )
        else:
            context['formset'] = IngredienteNoGustadoFormSet(instance=self.object)
        return context

    def form_valid(self, form):
        self.object = form.save()
        formset = IngredienteNoGustadoFormSet(self.request.POST, instance=self.object)
        if formset.is_valid():
            formset.save()
            messages.success(self.request, 'Cliente e ingredientes no gustados guardados correctamente.')
            return redirect(self.get_success_url())
        return self.render_to_response(
            self.get_context_data(form=form, formset=formset)
        )


class ClienteDeleteView(LoginRequiredMixin, DeleteView):
    model = Cliente
    template_name = 'clients/cliente_confirm_delete.html'
    success_url = reverse_lazy('clients:lista')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from contracts.models import Contrato
        cliente = self.object
        context['contratos_activos'] = Contrato.objects.filter(
            cliente=cliente, estado='activo'
        ).select_related('plan').order_by('-fecha_creacion')
        context['dependientes_con_contratos_activos'] = Cliente.objects.filter(
            titular=cliente
        ).filter(contratos__estado='activo').distinct()
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Cliente eliminado exitosamente.')
        return super().form_valid(form)

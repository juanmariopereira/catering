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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        get = self.request.GET.copy()
        get.pop('order', None)
        get.pop('page', None)
        context['query_base'] = get.urlencode()
        context['order_current'] = (self.request.GET.get('order') or 'nombre').strip()
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

    def form_valid(self, form):
        messages.success(self.request, 'Cliente eliminado exitosamente.')
        return super().form_valid(form)

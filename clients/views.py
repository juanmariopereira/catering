from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy, reverse
from django.shortcuts import redirect
from django.contrib import messages
from django.forms import inlineformset_factory

from .models import Cliente, IngredienteNoGustado
from .services import (
    list_clientes_queryset,
    get_cliente_detalle_data,
    get_cliente_delete_context,
    save_cliente_con_ingredientes_no_gustados,
)

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

    def get_queryset(self):
        busqueda = self.request.GET.get('q')
        activo = self.request.GET.get('activo')
        order = (self.request.GET.get('order') or 'nombre').strip()
        return list_clientes_queryset(busqueda=busqueda, activo=activo, order=order)

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
    fields = ['nombre', 'email', 'telefono', 'direccion', 'link_maps', 'latitud', 'longitud', 'titular', 'activo', 'notas']
    success_url = reverse_lazy('clients:lista')

    def form_valid(self, form):
        messages.success(self.request, 'Cliente creado exitosamente.')
        return super().form_valid(form)


class ClienteDetailView(LoginRequiredMixin, DetailView):
    model = Cliente
    template_name = 'clients/cliente_detalle.html'
    context_object_name = 'cliente'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_cliente_detalle_data(self.object))
        return context


class ClienteUpdateView(LoginRequiredMixin, UpdateView):
    model = Cliente
    template_name = 'clients/cliente_form.html'
    fields = ['nombre', 'email', 'telefono', 'direccion', 'link_maps', 'latitud', 'longitud', 'titular', 'activo', 'notas']
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
        formset = IngredienteNoGustadoFormSet(self.request.POST, instance=self.object)
        if formset.is_valid():
            save_cliente_con_ingredientes_no_gustados(
                self.object,
                form.cleaned_data,
                [f.cleaned_data for f in formset if f.cleaned_data and not f.cleaned_data.get('DELETE')],
            )
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
        context.update(get_cliente_delete_context(self.object))
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Cliente eliminado exitosamente.')
        return super().form_valid(form)

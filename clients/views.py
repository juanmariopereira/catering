from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.db.models import Q
from django.urls import reverse_lazy
from django.contrib import messages

from .models import Cliente


class ClienteListView(LoginRequiredMixin, ListView):
    model = Cliente
    template_name = 'clients/cliente_lista.html'
    context_object_name = 'clientes'
    paginate_by = 30

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
        return queryset.order_by('nombre')


class ClienteCreateView(LoginRequiredMixin, CreateView):
    model = Cliente
    template_name = 'clients/cliente_form.html'
    fields = ['nombre', 'email', 'telefono', 'direcciones', 'activo', 'notas']
    success_url = reverse_lazy('clients:lista')

    def form_valid(self, form):
        messages.success(self.request, 'Cliente creado exitosamente.')
        return super().form_valid(form)


class ClienteUpdateView(LoginRequiredMixin, UpdateView):
    model = Cliente
    template_name = 'clients/cliente_form.html'
    fields = ['nombre', 'email', 'telefono', 'direcciones', 'activo', 'notas']
    success_url = reverse_lazy('clients:lista')

    def form_valid(self, form):
        messages.success(self.request, 'Cliente actualizado exitosamente.')
        return super().form_valid(form)


class ClienteDeleteView(LoginRequiredMixin, DeleteView):
    model = Cliente
    template_name = 'clients/cliente_confirm_delete.html'
    success_url = reverse_lazy('clients:lista')

    def form_valid(self, form):
        messages.success(self.request, 'Cliente eliminado exitosamente.')
        return super().form_valid(form)

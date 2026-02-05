from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Q

from .models import Entregador


class EntregadorListView(LoginRequiredMixin, ListView):
    model = Entregador
    template_name = 'routes/entregador_lista.html'
    context_object_name = 'entregadores'
    paginate_by = 30

    def get_queryset(self):
        queryset = super().get_queryset()
        busqueda = self.request.GET.get('q')
        if busqueda:
            queryset = queryset.filter(
                Q(nombre__icontains=busqueda) | Q(telefono__icontains=busqueda) | Q(vehiculo__icontains=busqueda)
            )
        activo = self.request.GET.get('activo')
        if activo is not None and activo != '':
            queryset = queryset.filter(activo=activo == '1')
        return queryset.order_by('nombre')


class EntregadorCreateView(LoginRequiredMixin, CreateView):
    model = Entregador
    template_name = 'routes/entregador_form.html'
    fields = ['nombre', 'telefono', 'vehiculo', 'activo', 'notas']
    success_url = reverse_lazy('routes:entregador_lista')

    def form_valid(self, form):
        messages.success(self.request, 'Entregador creado exitosamente.')
        return super().form_valid(form)


class EntregadorUpdateView(LoginRequiredMixin, UpdateView):
    model = Entregador
    template_name = 'routes/entregador_form.html'
    fields = ['nombre', 'telefono', 'vehiculo', 'activo', 'notas']
    success_url = reverse_lazy('routes:entregador_lista')

    def form_valid(self, form):
        messages.success(self.request, 'Entregador actualizado exitosamente.')
        return super().form_valid(form)


class EntregadorDeleteView(LoginRequiredMixin, DeleteView):
    model = Entregador
    template_name = 'routes/entregador_confirm_delete.html'
    success_url = reverse_lazy('routes:entregador_lista')

    def form_valid(self, form):
        messages.success(self.request, 'Entregador eliminado exitosamente.')
        return super().form_valid(form)

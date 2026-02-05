from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Q

from .models import Contrato


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
    template_name = 'contracts/contrato_form.html'
    fields = ['cliente', 'plan', 'fecha_inicio', 'fecha_fin', 'precio', 'frecuencia_pago',
              'direccion_entrega', 'horario_entrega', 'dias_entrega', 'estado', 'notas']
    success_url = reverse_lazy('contracts:lista')

    def form_valid(self, form):
        messages.success(self.request, 'Contrato creado exitosamente.')
        return super().form_valid(form)


class ContratoUpdateView(LoginRequiredMixin, UpdateView):
    model = Contrato
    template_name = 'contracts/contrato_form.html'
    fields = ['cliente', 'plan', 'fecha_inicio', 'fecha_fin', 'precio', 'frecuencia_pago',
              'direccion_entrega', 'horario_entrega', 'dias_entrega', 'estado', 'notas']
    success_url = reverse_lazy('contracts:lista')

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

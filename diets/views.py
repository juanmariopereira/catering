from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Q

from .models import Dieta


class DietaListView(LoginRequiredMixin, ListView):
    model = Dieta
    template_name = 'diets/dieta_lista.html'
    context_object_name = 'dietas'
    paginate_by = 30

    def get_queryset(self):
        queryset = super().get_queryset()
        busqueda = self.request.GET.get('q')
        if busqueda:
            queryset = queryset.filter(Q(nombre__icontains=busqueda) | Q(descripcion__icontains=busqueda))
        activa = self.request.GET.get('activa')
        if activa is not None and activa != '':
            queryset = queryset.filter(activa=activa == '1')
        plan_id = self.request.GET.get('plan')
        if plan_id:
            queryset = queryset.filter(plan_id=plan_id)
        return queryset.select_related('plan').order_by('nombre')


class DietaCreateView(LoginRequiredMixin, CreateView):
    model = Dieta
    template_name = 'diets/dieta_form.html'
    fields = ['nombre', 'descripcion', 'plan', 'activa']
    success_url = reverse_lazy('diets:lista')

    def form_valid(self, form):
        messages.success(self.request, 'Dieta creada exitosamente.')
        return super().form_valid(form)


class DietaUpdateView(UpdateView):
    model = Dieta
    template_name = 'diets/dieta_form.html'
    fields = ['nombre', 'descripcion', 'plan', 'activa']
    success_url = reverse_lazy('diets:lista')

    def form_valid(self, form):
        messages.success(self.request, 'Dieta actualizada exitosamente.')
        return super().form_valid(form)


class DietaDeleteView(LoginRequiredMixin, DeleteView):
    model = Dieta
    template_name = 'diets/dieta_confirm_delete.html'
    success_url = reverse_lazy('diets:lista')

    def form_valid(self, form):
        messages.success(self.request, 'Dieta eliminada exitosamente.')
        return super().form_valid(form)

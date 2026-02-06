from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Q

from .models import Plan


class PlanListView(LoginRequiredMixin, ListView):
    model = Plan
    template_name = 'plans/plan_lista.html'
    context_object_name = 'planes'
    paginate_by = 30

    def get_queryset(self):
        queryset = super().get_queryset()
        busqueda = self.request.GET.get('q')
        if busqueda:
            queryset = queryset.filter(Q(nombre__icontains=busqueda) | Q(descripcion__icontains=busqueda))
        activo = self.request.GET.get('activo')
        if activo is not None and activo != '':
            queryset = queryset.filter(activo=activo == '1')
        return queryset.order_by('nombre')


class PlanCreateView(LoginRequiredMixin, CreateView):
    model = Plan
    template_name = 'plans/plan_form.html'
    fields = ['nombre', 'descripcion', 'precio_base', 'dias_vencimiento_cobro', 'activo']
    success_url = reverse_lazy('plans:lista')

    def form_valid(self, form):
        messages.success(self.request, 'Plan creado exitosamente.')
        return super().form_valid(form)


class PlanUpdateView(LoginRequiredMixin, UpdateView):
    model = Plan
    template_name = 'plans/plan_form.html'
    fields = ['nombre', 'descripcion', 'precio_base', 'dias_vencimiento_cobro', 'activo']
    success_url = reverse_lazy('plans:lista')

    def form_valid(self, form):
        messages.success(self.request, 'Plan actualizado exitosamente.')
        return super().form_valid(form)


class PlanDeleteView(LoginRequiredMixin, DeleteView):
    model = Plan
    template_name = 'plans/plan_confirm_delete.html'
    success_url = reverse_lazy('plans:lista')

    def form_valid(self, form):
        messages.success(self.request, 'Plan eliminado exitosamente.')
        return super().form_valid(form)

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Q

from .models import Receta, Ingrediente


class RecetaListView(LoginRequiredMixin, ListView):
    model = Receta
    template_name = 'recipes/receta_lista.html'
    context_object_name = 'recetas'
    paginate_by = 30

    def get_queryset(self):
        queryset = super().get_queryset()
        busqueda = self.request.GET.get('q')
        if busqueda:
            queryset = queryset.filter(Q(nombre__icontains=busqueda) | Q(descripcion__icontains=busqueda))
        categoria = self.request.GET.get('categoria')
        if categoria:
            queryset = queryset.filter(categoria=categoria)
        activa = self.request.GET.get('activa')
        if activa is not None and activa != '':
            queryset = queryset.filter(activa=activa == '1')
        return queryset.order_by('categoria', 'nombre')


class RecetaCreateView(CreateView):
    model = Receta
    template_name = 'recipes/receta_form.html'
    fields = ['nombre', 'descripcion', 'categoria', 'info_nutricional', 'activa']
    success_url = reverse_lazy('recipes:lista')

    def form_valid(self, form):
        messages.success(self.request, 'Receta creada exitosamente.')
        return super().form_valid(form)


class RecetaUpdateView(LoginRequiredMixin, UpdateView):
    model = Receta
    template_name = 'recipes/receta_form.html'
    fields = ['nombre', 'descripcion', 'categoria', 'info_nutricional', 'activa']
    success_url = reverse_lazy('recipes:lista')

    def form_valid(self, form):
        messages.success(self.request, 'Receta actualizada exitosamente.')
        return super().form_valid(form)


class RecetaDeleteView(LoginRequiredMixin, DeleteView):
    model = Receta
    template_name = 'recipes/receta_confirm_delete.html'
    success_url = reverse_lazy('recipes:lista')

    def form_valid(self, form):
        messages.success(self.request, 'Receta eliminada exitosamente.')
        return super().form_valid(form)


class IngredienteListView(LoginRequiredMixin, ListView):
    model = Ingrediente
    template_name = 'recipes/ingrediente_lista.html'
    context_object_name = 'ingredientes'
    paginate_by = 30

    def get_queryset(self):
        queryset = super().get_queryset()
        busqueda = self.request.GET.get('q')
        if busqueda:
            queryset = queryset.filter(nombre__icontains=busqueda)
        activo = self.request.GET.get('activo')
        if activo is not None and activo != '':
            queryset = queryset.filter(activo=activo == '1')
        return queryset.order_by('nombre')


class IngredienteCreateView(LoginRequiredMixin, CreateView):
    model = Ingrediente
    template_name = 'recipes/ingrediente_form.html'
    fields = ['nombre', 'unidad_medida', 'activo']
    success_url = reverse_lazy('recipes:ingrediente_lista')

    def form_valid(self, form):
        messages.success(self.request, 'Ingrediente creado exitosamente.')
        return super().form_valid(form)


class IngredienteUpdateView(LoginRequiredMixin, UpdateView):
    model = Ingrediente
    template_name = 'recipes/ingrediente_form.html'
    fields = ['nombre', 'unidad_medida', 'activo']
    success_url = reverse_lazy('recipes:ingrediente_lista')

    def form_valid(self, form):
        messages.success(self.request, 'Ingrediente actualizado exitosamente.')
        return super().form_valid(form)


class IngredienteDeleteView(LoginRequiredMixin, DeleteView):
    model = Ingrediente
    template_name = 'recipes/ingrediente_confirm_delete.html'
    success_url = reverse_lazy('recipes:ingrediente_lista')

    def form_valid(self, form):
        messages.success(self.request, 'Ingrediente eliminado exitosamente.')
        return super().form_valid(form)

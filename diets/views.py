from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy, reverse
from django.shortcuts import redirect
from django.contrib import messages
from django.db.models import Q
from django.forms import inlineformset_factory

from .models import Dieta, DietaReceta


DietaRecetaFormSet = inlineformset_factory(
    Dieta,
    DietaReceta,
    fields=['tipo_comida', 'receta', 'orden'],
    extra=15,
    can_delete=True,
)


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
            queryset = queryset.filter(planes=plan_id)
        return queryset.prefetch_related('planes').order_by('nombre')


class DietaCreateView(LoginRequiredMixin, CreateView):
    model = Dieta
    template_name = 'diets/dieta_form.html'
    fields = ['nombre', 'descripcion', 'planes', 'activa']
    context_object_name = 'dieta'

    def get_success_url(self):
        return reverse('diets:editar', args=[self.object.pk])

    def form_valid(self, form):
        messages.success(self.request, 'Dieta creada. Agregue las recetas a continuación.')
        return super().form_valid(form)


class DietaUpdateView(LoginRequiredMixin, UpdateView):
    model = Dieta
    template_name = 'diets/dieta_form.html'
    fields = ['nombre', 'descripcion', 'planes', 'activa']
    context_object_name = 'dieta'

    def get_success_url(self):
        return reverse('diets:editar', args=[self.object.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['formset'] = DietaRecetaFormSet(
                self.request.POST, instance=self.object
            )
        else:
            context['formset'] = DietaRecetaFormSet(instance=self.object)
        return context

    def form_valid(self, form):
        self.object = form.save()
        formset = DietaRecetaFormSet(self.request.POST, instance=self.object)
        if formset.is_valid():
            formset.save()
            messages.success(self.request, 'Dieta y recetas guardadas correctamente.')
            return redirect(self.get_success_url())
        return self.render_to_response(
            self.get_context_data(form=form, formset=formset)
        )


class DietaDeleteView(LoginRequiredMixin, DeleteView):
    model = Dieta
    template_name = 'diets/dieta_confirm_delete.html'
    success_url = reverse_lazy('diets:lista')

    def form_valid(self, form):
        messages.success(self.request, 'Dieta eliminada exitosamente.')
        return super().form_valid(form)

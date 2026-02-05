from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy, reverse
from django.shortcuts import redirect
from django.contrib import messages
from django.db.models import Q
from django.forms import inlineformset_factory
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required

from .models import Dieta, DietaReceta
from .services.ai_dietas import sugerir_dieta_personalizada, OBJETIVOS_VALIDOS


@login_required
@require_http_methods(['POST'])
def sugerir_dieta_view(request):
    """
    Vista AJAX: sugiere una dieta personalizada con IA.
    POST: objetivo, plan_id (opcional)
    Returns: JSON { "ok": true, "recetas": [{ tipo_comida_id, receta_id, orden }] }
    """
    objetivo = request.POST.get('objetivo', 'equilibrado').strip().lower()
    plan_id = request.POST.get('plan_id')
    if objetivo not in OBJETIVOS_VALIDOS:
        objetivo = 'equilibrado'
    try:
        plan_id = int(plan_id) if plan_id else None
    except (ValueError, TypeError):
        plan_id = None

    try:
        recetas = sugerir_dieta_personalizada(objetivo, plan_id, request=request)
        return JsonResponse({'ok': True, 'recetas': recetas})
    except ValueError as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


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
        from plans.models import Plan
        context['planes'] = Plan.objects.filter(activo=True).order_by('nombre')
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

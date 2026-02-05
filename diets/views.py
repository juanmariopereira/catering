from datetime import date

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy, reverse
from django.shortcuts import redirect, render
from django.contrib import messages
from django.db.models import Q
from django.forms import inlineformset_factory
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from .models import Dieta, DietaReceta, TipoComida
from .services.ai_dietas import sugerir_dieta_personalizada, OBJETIVOS_VALIDOS

# Día de la semana: Python weekday() 0=lunes, 6=domingo -> valor en contrato.dias_entrega
DIA_SEMANA_NOMBRE = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo']


@login_required
def composicion_por_fecha(request):
    """
    Pantalla para ver la composición de la dieta que se envía a cada contrato, por fecha.
    Por defecto muestra la fecha actual; se puede cambiar con el parámetro GET fecha (YYYY-MM-DD).
    Solo se listan contratos activos en esa fecha que tienen entrega ese día (dias_entrega).
    La composición viene del menú planificado (PlanificacionMenu) y sustituciones por cliente.
    """
    fecha_param = request.GET.get('fecha')
    if fecha_param:
        try:
            fecha = date.fromisoformat(fecha_param)
        except ValueError:
            fecha = timezone.now().date()
    else:
        fecha = timezone.now().date()

    from contracts.models import contratos_activos_en_fecha
    from planning.models import PlanificacionMenu, PlanificacionMenuReceta, PlanificacionClienteSustituta

    dia_semana = DIA_SEMANA_NOMBRE[fecha.weekday()]
    contratos = (
        contratos_activos_en_fecha(fecha)
        .filter(dias_entrega__contains=[dia_semana])
        .select_related('cliente', 'plan')
        .order_by('cliente__nombre')
    )

    # Filtros opcionales: cliente, plan, tipo de comida
    cliente_id = request.GET.get('cliente')
    if cliente_id:
        try:
            contratos = contratos.filter(cliente_id=int(cliente_id))
        except (ValueError, TypeError):
            pass
    plan_id = request.GET.get('plan')
    if plan_id:
        try:
            contratos = contratos.filter(plan_id=int(plan_id))
        except (ValueError, TypeError):
            pass

    # Listas para los selects (clientes y planes que tienen entrega ese día)
    from clients.models import Cliente
    from plans.models import Plan
    contratos_base = contratos_activos_en_fecha(fecha).filter(dias_entrega__contains=[dia_semana])
    clientes_fecha = Cliente.objects.filter(
        pk__in=contratos_base.values_list('cliente_id', flat=True).distinct()
    ).order_by('nombre')
    planes_fecha = Plan.objects.filter(
        pk__in=contratos_base.values_list('plan_id', flat=True).distinct()
    ).order_by('nombre')
    tipos_comida = TipoComida.objects.all().order_by('orden', 'nombre')

    menus_por_plan = {
        pm.plan_id: pm
        for pm in PlanificacionMenu.objects.filter(fecha=fecha).select_related('plan').prefetch_related(
            'recetas__tipo_comida', 'recetas__receta'
        )
    }

    sustituciones = {
        (s.contrato_id, s.tipo_comida_id, s.receta_original_id): s.receta_sustituta
        for s in PlanificacionClienteSustituta.objects.filter(
            fecha=fecha, contrato__in=contratos
        ).select_related('receta_sustituta')
    }

    # Código único de entrega por contrato (RutaCliente para esta fecha)
    from routes.models import RutaCliente
    codigos_entrega = dict(
        RutaCliente.objects.filter(
            ruta__fecha=fecha, contrato__in=contratos
        ).values_list('contrato_id', 'codigo_entrega')
    )

    filas = []
    for c in contratos:
        menu = menus_por_plan.get(c.plan_id)
        composicion = []
        if menu:
            for pmr in menu.recetas.all().order_by('tipo_comida__orden', 'orden'):
                receta_final = sustituciones.get((c.id, pmr.tipo_comida_id, pmr.receta_id)) or pmr.receta
                es_sustituta = receta_final != pmr.receta
                composicion.append({
                    'tipo_comida': pmr.tipo_comida,
                    'receta': receta_final,
                    'es_sustituta': es_sustituta,
                })
        filas.append({
            'contrato': c,
            'cliente': c.cliente,
            'plan': c.plan,
            'menu': menu,
            'composicion': composicion,
            'codigo_entrega': codigos_entrega.get(c.id) or '',
        })

    # Filtro por tipo de comida: solo filas que incluyen esa comida; opcionalmente mostrar solo esa fila en la tabla
    comida_id = request.GET.get('comida')
    if comida_id:
        try:
            tid = int(comida_id)
            filas_filtradas = []
            for f in filas:
                compo = f['composicion']
                matching = [item for item in compo if item['tipo_comida'].id == tid]
                if matching:
                    filas_filtradas.append({
                        **f,
                        'composicion': matching,
                    })
            filas = filas_filtradas
        except (ValueError, TypeError):
            pass

    from base.models import es_feriado, get_feriado
    context = {
        'fecha': fecha,
        'filas': filas,
        'es_feriado': es_feriado(fecha),
        'feriado': get_feriado(fecha),
        'clientes_fecha': clientes_fecha,
        'planes_fecha': planes_fecha,
        'tipos_comida': tipos_comida,
        'filtro_cliente': request.GET.get('cliente', ''),
        'filtro_plan': request.GET.get('plan', ''),
        'filtro_comida': request.GET.get('comida', ''),
    }
    return render(request, 'diets/composicion_por_fecha.html', context)


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

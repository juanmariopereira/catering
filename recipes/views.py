from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy, reverse
from django.shortcuts import redirect, render
from django.contrib import messages
from django.db.models import Q
from django.forms import inlineformset_factory

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required

from .forms import IngredienteForm
from .models import TipoReceta, UnidadMedida, Receta, Ingrediente, RecetaIngrediente
from .services.ai_nutricion import (
    estimar_info_nutricional_ingrediente,
    calcular_info_nutricional_receta,
    estimar_info_nutricional_receta_ia,
    sugerir_descripcion_receta_ia,
    sugerir_ingredientes_receta_ia,
    importar_receta_desde_texto_ia,
    obtener_alergenos_receta,
)


@login_required
@require_http_methods(['POST'])
def sugerir_nutricion_ingrediente_view(request):
    """
    Vista AJAX: estima info nutricional de un ingrediente con IA.
    POST: nombre, unidad_medida_id
    Returns: JSON { "ok": true, "info_nutricional": {...} }
    """
    nombre = request.POST.get('nombre', '').strip()
    unidad_id = request.POST.get('unidad_medida')
    if not nombre:
        return JsonResponse({'ok': False, 'error': 'Falta el nombre del ingrediente.'}, status=400)
    if not unidad_id:
        return JsonResponse({'ok': False, 'error': 'Falta la unidad de medida.'}, status=400)
    try:
        unidad = UnidadMedida.objects.get(pk=unidad_id)
        unidad_nombre = unidad.simbolo or unidad.nombre or 'unidad'
    except (UnidadMedida.DoesNotExist, ValueError, TypeError):
        return JsonResponse({'ok': False, 'error': 'Unidad de medida inválida.'}, status=400)

    try:
        info = estimar_info_nutricional_ingrediente(nombre, unidad_nombre, request=request)
        if not info:
            return JsonResponse({'ok': False, 'error': 'No se pudo estimar la información nutricional.'}, status=400)
        return JsonResponse({'ok': True, 'info_nutricional': info})
    except ValueError as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(['POST'])
def calcular_nutricion_receta_view(request):
    """
    Vista AJAX: calcula info nutricional de una receta desde sus ingredientes.
    POST: receta_id
    Returns: JSON { "ok": true, "info_nutricional": {...} }
    """
    receta_id = request.POST.get('receta_id')
    if not receta_id:
        return JsonResponse({'ok': False, 'error': 'Falta el ID de la receta.'}, status=400)
    try:
        receta = get_object_or_404(Receta, pk=receta_id)
    except (ValueError, TypeError):
        return JsonResponse({'ok': False, 'error': 'Receta inválida.'}, status=400)

    info = calcular_info_nutricional_receta(receta)
    if not info:
        return JsonResponse({'ok': False, 'error': 'No hay ingredientes con información nutricional para calcular.'}, status=400)
    return JsonResponse({'ok': True, 'info_nutricional': info})


@login_required
@require_http_methods(['POST'])
def sugerir_nutricion_receta_view(request):
    """
    Vista AJAX: estima info nutricional de una receta con IA cuando no puede calcularse.
    POST: receta_id
    Returns: JSON { "ok": true, "info_nutricional": {...} }
    """
    receta_id = request.POST.get('receta_id')
    if not receta_id:
        return JsonResponse({'ok': False, 'error': 'Falta el ID de la receta.'}, status=400)
    receta = get_object_or_404(Receta, pk=receta_id)
    try:
        info = estimar_info_nutricional_receta_ia(receta, request=request)
        if not info:
            return JsonResponse({'ok': False, 'error': 'No se pudo estimar.'}, status=400)
        return JsonResponse({'ok': True, 'info_nutricional': info})
    except ValueError as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(['POST'])
def sugerir_descripcion_receta_view(request):
    """
    Vista AJAX: sugiere descripción de una receta con IA.
    POST: receta_id
    Returns: JSON { "ok": true, "descripcion": "..." }
    """
    receta_id = request.POST.get('receta_id')
    if not receta_id:
        return JsonResponse({'ok': False, 'error': 'Falta el ID de la receta.'}, status=400)
    receta = get_object_or_404(Receta, pk=receta_id)
    try:
        descripcion = sugerir_descripcion_receta_ia(receta, request=request)
        if not descripcion:
            return JsonResponse({'ok': False, 'error': 'No se pudo generar la descripción.'}, status=400)
        return JsonResponse({'ok': True, 'descripcion': descripcion})
    except ValueError as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(['POST'])
def sugerir_ingredientes_receta_view(request):
    """
    Vista AJAX: sugiere ingredientes para una receta con IA.
    POST: receta_id
    Returns: JSON { "ok": true, "ingredientes": [{ ingrediente_id, cantidad, unidad_medida_id }] }
    """
    receta_id = request.POST.get('receta_id')
    if not receta_id:
        return JsonResponse({'ok': False, 'error': 'Falta el ID de la receta.'}, status=400)
    receta = get_object_or_404(Receta, pk=receta_id)
    try:
        ingredientes, no_encontrados, catalogo_vacio = sugerir_ingredientes_receta_ia(receta, request=request)
        if not ingredientes and not no_encontrados:
            if catalogo_vacio:
                resp = {'ok': True, 'ingredientes': [], 'no_encontrados': []}
                resp['nota_descripcion'] = 'No hay ingredientes en el catálogo. No se pudieron generar sugerencias. Añada ingredientes al catálogo primero.'
                return JsonResponse(resp)
            return JsonResponse({'ok': False, 'error': 'No se generaron sugerencias.'}, status=400)
        resp = {'ok': True, 'ingredientes': ingredientes, 'no_encontrados': no_encontrados}
        if no_encontrados:
            lista_ing = ', '.join(f"{x['nombre']} ({x['cantidad']} {x['unidad']})" for x in no_encontrados)
            if catalogo_vacio:
                texto = f'No hay ingredientes en el catálogo. Ingredientes sugeridos por la IA (añadir manualmente al catálogo): {lista_ing}'
            else:
                texto = f'Ingredientes sugeridos no disponibles en el catálogo: {lista_ing}'
            resp['nota_descripcion'] = texto
        return JsonResponse(resp)
    except ValueError as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@login_required
def importar_receta_view(request):
    """
    Importa una receta pegando texto. La IA extrae nombre, descripción, tipos,
    momentos e ingredientes. Crea la receta y redirige a editar.
    """
    if request.method != 'POST':
        return render(request, 'recipes/receta_importar.html')

    texto = (request.POST.get('texto_receta') or '').strip()
    if not texto or len(texto) < 10:
        messages.error(request, 'Pega el texto completo de la receta (mínimo 10 caracteres).')
        return render(request, 'recipes/receta_importar.html', {'texto_receta': texto})

    try:
        data = importar_receta_desde_texto_ia(texto, request=request)
    except ValueError as e:
        messages.error(request, str(e))
        return render(request, 'recipes/receta_importar.html', {'texto_receta': texto})
    except Exception as e:
        messages.error(request, f'Error al importar: {e}')
        return render(request, 'recipes/receta_importar.html', {'texto_receta': texto})

    if not data.get('nombre'):
        messages.error(request, 'No se pudo extraer la receta del texto.')
        return render(request, 'recipes/receta_importar.html', {'texto_receta': texto})

    descripcion = data.get('descripcion', '')
    if data.get('nota_descripcion'):
        descripcion = (descripcion + '\n\n' + data['nota_descripcion']).strip()

    receta = Receta.objects.create(
        nombre=data['nombre'],
        descripcion=descripcion or None,
        info_nutricional={},
        activa=True,
    )
    receta.tipos_receta.set(data.get('tipos_receta_ids', []))
    receta.momentos_dia.set(data.get('momentos_dia_ids', []))

    for ing in data.get('ingredientes', []):
        RecetaIngrediente.objects.create(
            receta=receta,
            ingrediente_id=ing['ingrediente_id'],
            cantidad=ing['cantidad'],
            unidad_medida_id=ing['unidad_medida_id'],
        )

    num_ing = len(data.get('ingredientes', []))
    num_no = len(data.get('no_encontrados', []))
    msg = f'Receta "{receta.nombre}" importada con {num_ing} ingredientes.'
    if num_no:
        msg += f' {num_no} ingredientes no están en el catálogo (ver descripción).'
    messages.success(request, msg)
    return redirect('recipes:editar', pk=receta.pk)


RecetaIngredienteFormSet = inlineformset_factory(
    Receta,
    RecetaIngrediente,
    fields=['ingrediente', 'cantidad', 'unidad_medida'],
    extra=3,
    can_delete=True,
)


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
        tipo_receta_id = self.request.GET.get('tipo_receta')
        if tipo_receta_id:
            queryset = queryset.filter(tipos_receta_id=tipo_receta_id)
        momento_id = self.request.GET.get('momento')
        if momento_id:
            queryset = queryset.filter(momentos_dia_id=momento_id)
        activa = self.request.GET.get('activa')
        if activa is not None and activa != '':
            queryset = queryset.filter(activa=activa == '1')
        return queryset.order_by('nombre')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tipos_receta'] = TipoReceta.objects.filter(activo=True).order_by('orden', 'nombre')
        from diets.models import TipoComida
        context['momentos_dia'] = TipoComida.objects.all().order_by('orden', 'nombre')
        return context


class RecetaDetailView(LoginRequiredMixin, DetailView):
    model = Receta
    template_name = 'recipes/receta_detalle.html'
    context_object_name = 'receta'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['alergenos'] = obtener_alergenos_receta(self.object)
        return context


class RecetaCreateView(LoginRequiredMixin, CreateView):
    model = Receta
    template_name = 'recipes/receta_form.html'
    fields = ['nombre', 'descripcion', 'tipos_receta', 'momentos_dia', 'info_nutricional', 'activa', 'producido_en_cocina']

    def get_success_url(self):
        return reverse('recipes:editar', args=[self.object.pk])

    def form_valid(self, form):
        messages.success(self.request, 'Receta creada. Agregue los ingredientes y cantidades a continuación.')
        return super().form_valid(form)


class RecetaUpdateView(LoginRequiredMixin, UpdateView):
    model = Receta
    template_name = 'recipes/receta_form.html'
    fields = ['nombre', 'descripcion', 'tipos_receta', 'momentos_dia', 'info_nutricional', 'activa', 'producido_en_cocina']

    def get_success_url(self):
        return reverse('recipes:editar', args=[self.object.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if 'ingredientes_formset' in kwargs:
            context['ingredientes_formset'] = kwargs['ingredientes_formset']
        elif self.request.POST:
            context['ingredientes_formset'] = RecetaIngredienteFormSet(
                self.request.POST, instance=self.object
            )
        else:
            context['ingredientes_formset'] = RecetaIngredienteFormSet(instance=self.object)
        return context

    def form_valid(self, form):
        self.object = form.save()
        formset = RecetaIngredienteFormSet(self.request.POST, instance=self.object)
        if formset.is_valid():
            formset.save()
            messages.success(self.request, 'Receta e ingredientes guardados correctamente.')
            return redirect(self.get_success_url())
        else:
            return self.render_to_response(
                self.get_context_data(form=form, ingredientes_formset=formset)
            )


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
    form_class = IngredienteForm
    template_name = 'recipes/ingrediente_form.html'
    success_url = reverse_lazy('recipes:ingrediente_lista')

    def form_valid(self, form):
        messages.success(self.request, 'Ingrediente creado exitosamente.')
        return super().form_valid(form)


class IngredienteUpdateView(LoginRequiredMixin, UpdateView):
    model = Ingrediente
    form_class = IngredienteForm
    template_name = 'recipes/ingrediente_form.html'
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


# TipoReceta (parametrizable: Comida, Masa, Postre, Bebida, Fruta, etc.)
class TipoRecetaListView(LoginRequiredMixin, ListView):
    model = TipoReceta
    template_name = 'recipes/tiporeceta_lista.html'
    context_object_name = 'tipos'
    paginate_by = 30

    def get_queryset(self):
        return TipoReceta.objects.all().order_by('orden', 'nombre')


class TipoRecetaCreateView(LoginRequiredMixin, CreateView):
    model = TipoReceta
    template_name = 'recipes/tiporeceta_form.html'
    fields = ['nombre', 'orden', 'activo']
    success_url = reverse_lazy('recipes:tipo_receta_lista')

    def form_valid(self, form):
        messages.success(self.request, 'Tipo de receta creado.')
        return super().form_valid(form)


class TipoRecetaUpdateView(LoginRequiredMixin, UpdateView):
    model = TipoReceta
    template_name = 'recipes/tiporeceta_form.html'
    fields = ['nombre', 'orden', 'activo']
    success_url = reverse_lazy('recipes:tipo_receta_lista')
    context_object_name = 'tiporeceta'

    def form_valid(self, form):
        messages.success(self.request, 'Tipo de receta actualizado.')
        return super().form_valid(form)


class TipoRecetaDeleteView(LoginRequiredMixin, DeleteView):
    model = TipoReceta
    template_name = 'recipes/tiporeceta_confirm_delete.html'
    success_url = reverse_lazy('recipes:tipo_receta_lista')
    context_object_name = 'tiporeceta'

    def form_valid(self, form):
        messages.success(self.request, 'Tipo de receta eliminado.')
        return super().form_valid(form)


# UnidadMedida (parametrizable: kg, gr, lt, un, etc.)
class UnidadMedidaListView(LoginRequiredMixin, ListView):
    model = UnidadMedida
    template_name = 'recipes/unidadmedida_lista.html'
    context_object_name = 'unidades'
    paginate_by = 30

    def get_queryset(self):
        return UnidadMedida.objects.all().order_by('orden', 'nombre')


class UnidadMedidaCreateView(LoginRequiredMixin, CreateView):
    model = UnidadMedida
    template_name = 'recipes/unidadmedida_form.html'
    fields = ['nombre', 'simbolo', 'orden', 'activo']
    success_url = reverse_lazy('recipes:unidad_medida_lista')

    def form_valid(self, form):
        messages.success(self.request, 'Unidad de medida creada.')
        return super().form_valid(form)


class UnidadMedidaUpdateView(LoginRequiredMixin, UpdateView):
    model = UnidadMedida
    template_name = 'recipes/unidadmedida_form.html'
    fields = ['nombre', 'simbolo', 'orden', 'activo']
    success_url = reverse_lazy('recipes:unidad_medida_lista')
    context_object_name = 'unidad'

    def form_valid(self, form):
        messages.success(self.request, 'Unidad de medida actualizada.')
        return super().form_valid(form)


class UnidadMedidaDeleteView(LoginRequiredMixin, DeleteView):
    model = UnidadMedida
    template_name = 'recipes/unidadmedida_confirm_delete.html'
    success_url = reverse_lazy('recipes:unidad_medida_lista')
    context_object_name = 'unidad'

    def form_valid(self, form):
        messages.success(self.request, 'Unidad de medida eliminada.')
        return super().form_valid(form)

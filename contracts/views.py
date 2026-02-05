from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy, reverse
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q, Case, When, Value, IntegerField, Exists, OuterRef, Min, F
from django.db.models.functions import Coalesce
from datetime import date as date_type
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from .models import Contrato, PausaContrato, q_filtro_estado
from .forms import ContratoForm, PausaContratoForm
from plans.models import Plan
from clients.models import Cliente
from billing.models import Cobro


def _parse_sort(sort_param):
    """'cliente:desc,plan:asc' -> [('cliente', 'desc'), ('plan', 'asc')]"""
    result = []
    if not sort_param or not sort_param.strip():
        return result
    valid_cols = {'cliente', 'plan', 'estado', 'vencimiento', 'fecha_inicio'}
    for part in sort_param.strip().split(','):
        part = part.strip()
        if ':' in part:
            col, dir_ = part.split(':', 1)
            col, dir_ = col.strip(), dir_.strip().lower()
            if col in valid_cols and dir_ in ('asc', 'desc'):
                result.append((col, dir_))
    return result


def _next_sort(current_parsed, column):
    """Ciclo: (ninguno) -> desc -> asc -> (ninguno). Devuelve (nueva_lista, nueva_dirección_para_columna)."""
    current_dir = next((d for c, d in current_parsed if c == column), None)
    if current_dir == 'desc':
        new_parsed = [(c, 'asc' if c == column else d) for c, d in current_parsed]
        return new_parsed, 'asc'
    if current_dir == 'asc':
        new_parsed = [(c, d) for c, d in current_parsed if c != column]
        return new_parsed, None
    new_parsed = current_parsed + [(column, 'desc')]
    return new_parsed, 'desc'


def _sort_to_string(parsed):
    return ','.join(f'{c}:{d}' for c, d in parsed)


SORTABLE_COLUMNS = [
    ('cliente', 'Cliente'),
    ('plan', 'Plan'),
    ('fecha_inicio', 'Fecha Inicio'),
    ('vencimiento', 'Fecha vencimiento'),
    ('estado', 'Estado'),
]


class ContratoListView(LoginRequiredMixin, ListView):
    model = Contrato
    template_name = 'contracts/contrato_lista.html'
    context_object_name = 'contratos'
    paginate_by = 50
    PER_PAGE_OPTIONS = (50, 500, 2000)

    def get_queryset(self):
        queryset = super().get_queryset()
        busqueda = self.request.GET.get('q', '').strip()
        if busqueda:
            queryset = queryset.filter(
                Q(cliente__nombre__icontains=busqueda) | Q(plan__nombre__icontains=busqueda)
            )
        estado = self.request.GET.get('estado')
        if estado:
            queryset = queryset.filter(q_filtro_estado(estado))
        plan_id = self.request.GET.get('plan')
        if plan_id:
            queryset = queryset.filter(plan_id=plan_id)
        cliente_id = self.request.GET.get('cliente')
        if cliente_id:
            queryset = queryset.filter(cliente_id=cliente_id)
        vencimiento_desde = self.request.GET.get('vencimiento_desde')
        vencimiento_hasta = self.request.GET.get('vencimiento_hasta')
        if vencimiento_desde:
            queryset = queryset.filter(fecha_fin__gte=vencimiento_desde)
        if vencimiento_hasta:
            queryset = queryset.filter(fecha_fin__lte=vencimiento_hasta)
        queryset = queryset.select_related('cliente', 'plan')

        sort_parsed = _parse_sort(self.request.GET.get('sort', ''))
        hoy = timezone.now().date()

        if not sort_parsed:
            # Orden por defecto: estado (pendiente de pago, activo, inactivo) + vencimiento cobro más antiguo (asc)
            cobro_vigente = Cobro.objects.filter(contrato_id=OuterRef('pk'), periodo_hasta__gte=hoy)
            cobros_pendientes = Cobro.objects.filter(
                contrato_id=OuterRef('pk'),
                estado__in=['pendiente', 'vencida'],
            )
            queryset = queryset.annotate(
                tiene_cobro_vigente=Exists(cobro_vigente),
                tiene_cobros_pendientes=Exists(cobros_pendientes),
                min_vencimiento=Min(
                    'cobros__fecha_vencimiento',
                    filter=Q(cobros__estado__in=['pendiente', 'vencida']),
                ),
            )
            queryset = queryset.annotate(
                estado_orden_default=Case(
                    When(fecha_cancelacion__isnull=False, then=Value(3)),
                    When(fecha_pausa__isnull=False, fecha_reanudacion__isnull=True, then=Value(3)),
                    When(
                        Q(fecha_fin__isnull=False) & Q(fecha_fin__lt=hoy) & Q(tiene_cobro_vigente=False),
                        then=Value(3),
                    ),
                    When(tiene_cobros_pendientes=True, then=Value(1)),
                    default=Value(2),
                    output_field=IntegerField(),
                ),
            )
            queryset = queryset.annotate(
                orden_vencimiento=Coalesce(F('min_vencimiento'), Value(date_type(9999, 12, 31))),
            )
            queryset = queryset.order_by('estado_orden_default', 'orden_vencimiento', '-fecha_creacion')
            return queryset

        # Orden por columnas elegidas (prioridad = orden de clic)
        sort_columns = [c for c, _ in sort_parsed]
        if 'estado' in sort_columns:
            cobro_vigente = Cobro.objects.filter(contrato_id=OuterRef('pk'), periodo_hasta__gte=hoy)
            queryset = queryset.annotate(tiene_cobro_vigente=Exists(cobro_vigente))
            queryset = queryset.annotate(
                estado_orden=Case(
                    When(fecha_cancelacion__isnull=False, then=Value(4)),
                    When(fecha_pausa__isnull=False, fecha_reanudacion__isnull=True, then=Value(3)),
                    When(
                        Q(fecha_fin__isnull=False) & Q(fecha_fin__lt=hoy) & Q(tiene_cobro_vigente=False),
                        then=Value(2),
                    ),
                    default=Value(1),
                    output_field=IntegerField(),
                ),
            )
        order_by_list = []
        for col, dir_ in sort_parsed:
            prefix = '' if dir_ == 'asc' else '-'
            if col == 'cliente':
                order_by_list.append(f'{prefix}cliente__nombre')
            elif col == 'plan':
                order_by_list.append(f'{prefix}plan__nombre')
            elif col == 'fecha_inicio':
                order_by_list.append(f'{prefix}fecha_inicio')
            elif col == 'vencimiento':
                order_by_list.append(f'{prefix}fecha_fin')
            elif col == 'estado':
                order_by_list.append(f'{prefix}estado_orden')
        order_by_list.append('-fecha_creacion')
        return queryset.order_by(*order_by_list)

    def get_paginate_by(self, queryset):
        per = self.request.GET.get('per_page')
        try:
            n = int(per) if per else None
            if n is not None and n in self.PER_PAGE_OPTIONS:
                return n
        except (ValueError, TypeError):
            pass
        return self.paginate_by

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['planes'] = Plan.objects.filter(activo=True).order_by('nombre')
        context['clientes'] = Cliente.objects.order_by('nombre')
        get_copy = self.request.GET.copy()
        if 'page' in get_copy:
            get_copy.pop('page')
        context['query_string'] = get_copy.urlencode()
        get_no_sort = self.request.GET.copy()
        get_no_sort.pop('sort', None)
        get_no_sort.pop('page', None)
        context['query_base_no_sort'] = get_no_sort.urlencode()
        sort_parsed = _parse_sort(self.request.GET.get('sort', ''))
        sort_headers = []
        for col_key, col_label in SORTABLE_COLUMNS:
            next_parsed, next_dir = _next_sort(sort_parsed, col_key)
            next_sort = _sort_to_string(next_parsed) if next_parsed else ''
            current_dir = next((d for c, d in sort_parsed if c == col_key), None)
            sort_headers.append({
                'sortable': True,
                'key': col_key,
                'label': col_label,
                'direction': current_dir,
                'next_sort': next_sort,
            })
        # Orden de la tabla: Cliente, Plan, Fecha Inicio, Fecha vencimiento, Precio, Estado, Acciones
        context['table_headers'] = [
            sort_headers[0],
            sort_headers[1],
            sort_headers[2],
            sort_headers[3],
            {'sortable': False, 'label': 'Precio'},
            sort_headers[4],
            {'sortable': False, 'label': 'Acciones'},
        ]
        context['sort_headers'] = sort_headers
        context['per_page_current'] = self.get_paginate_by(self.get_queryset())
        context['per_page_options'] = self.PER_PAGE_OPTIONS
        return context


class ContratoCreateView(LoginRequiredMixin, CreateView):
    model = Contrato
    form_class = ContratoForm
    template_name = 'contracts/contrato_form.html'
    success_url = reverse_lazy('contracts:lista')

    def get_initial(self):
        initial = super().get_initial()
        plan_id = self.request.GET.get('plan')
        if plan_id:
            try:
                plan = Plan.objects.get(pk=plan_id, activo=True)
                initial['plan'] = plan.pk
                initial['precio'] = plan.precio_base
            except Plan.DoesNotExist:
                pass
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if not self.object:
            context['plan_precios'] = {str(p.id): str(p.precio_base) for p in Plan.objects.filter(activo=True)}
            context['clientes_datos'] = {
                str(c.id): {'direccion': c.direccion or '', 'link_maps': c.link_maps or ''}
                for c in Cliente.objects.all()
            }
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Contrato creado exitosamente.')
        return super().form_valid(form)


@login_required
@require_http_methods(['POST'])
def generar_mensaje_cliente_view(request):
    """
    Vista AJAX: genera mensaje personalizado para el cliente con IA.
    POST: contrato_id, tipo_mensaje (preguntar_dieta | plan_por_vencer | plan_vencido)
    Returns: JSON { "ok": true, "mensaje": "..." }
    """
    contrato_id = request.POST.get('contrato_id')
    tipo_mensaje = request.POST.get('tipo_mensaje')
    if not contrato_id or not tipo_mensaje:
        return JsonResponse({'ok': False, 'error': 'Faltan contrato_id o tipo_mensaje.'}, status=400)
    contrato = get_object_or_404(Contrato, pk=contrato_id)
    try:
        from .services.ai_mensajes import generar_mensaje_cliente_ia, TIPOS_MENSAJE
        tipos_validos = [t[0] for t in TIPOS_MENSAJE]
        if tipo_mensaje not in tipos_validos:
            return JsonResponse({'ok': False, 'error': 'Tipo de mensaje inválido.'}, status=400)
        mensaje = generar_mensaje_cliente_ia(contrato, tipo_mensaje, request=request)
        return JsonResponse({'ok': True, 'mensaje': mensaje})
    except ValueError as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


class ContratoDetailView(LoginRequiredMixin, DetailView):
    model = Contrato
    template_name = 'contracts/contrato_detalle.html'
    context_object_name = 'contrato'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['pausas'] = self.object.pausas.all().order_by('-fecha_inicio')
        context['cobros'] = (
            Cobro.objects.filter(contrato=self.object)
            .prefetch_related('pagos')
            .order_by('-periodo_hasta', '-numero_cobro')
        )
        return context


class ContratoUpdateView(LoginRequiredMixin, UpdateView):
    model = Contrato
    form_class = ContratoForm
    template_name = 'contracts/contrato_form.html'
    context_object_name = 'contrato'

    def get_success_url(self):
        return reverse('contracts:detalle', args=[self.object.pk])

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


class PausaContratoCreateView(LoginRequiredMixin, CreateView):
    model = PausaContrato
    form_class = PausaContratoForm
    template_name = 'contracts/pausa_form.html'
    context_object_name = 'pausa'

    def dispatch(self, request, *args, **kwargs):
        self.contrato = get_object_or_404(Contrato, pk=kwargs['contrato_pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['contrato'] = self.contrato
        return context

    def form_valid(self, form):
        form.instance.contrato = self.contrato
        messages.success(self.request, 'Pausa añadida correctamente.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('contracts:detalle', args=[self.object.contrato_id])


class PausaContratoUpdateView(LoginRequiredMixin, UpdateView):
    model = PausaContrato
    form_class = PausaContratoForm
    template_name = 'contracts/pausa_form.html'
    context_object_name = 'pausa'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['contrato'] = self.object.contrato
        return context

    def get_success_url(self):
        return reverse('contracts:detalle', args=[self.object.contrato_id])

    def form_valid(self, form):
        messages.success(self.request, 'Pausa actualizada correctamente.')
        return super().form_valid(form)


class PausaContratoDeleteView(LoginRequiredMixin, DeleteView):
    model = PausaContrato
    template_name = 'contracts/pausa_confirm_delete.html'
    context_object_name = 'pausa'

    def get_success_url(self):
        return reverse('contracts:detalle', args=[self.object.contrato_id])

    def form_valid(self, form):
        messages.success(self.request, 'Pausa eliminada.')
        return super().form_valid(form)

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Sum, F, Case, When, Value, IntegerField
from django.db.models.functions import Coalesce
from datetime import date, timedelta

from .models import Cobro, Pago
from .utils import obtener_cobros_vencidos, periodo_hasta_segun_frecuencia
from contracts.models import Contrato, q_filtro_estado
from plans.models import Plan
from clients.models import Cliente


def _cobro_parse_sort(sort_param):
    """'cliente:desc,monto:asc' -> [('cliente', 'desc'), ('monto', 'asc')]"""
    result = []
    if not sort_param or not sort_param.strip():
        return result
    valid_cols = {'numero', 'cliente', 'periodo', 'vencimiento', 'monto', 'estado'}
    for part in sort_param.strip().split(','):
        part = part.strip()
        if ':' in part:
            col, dir_ = part.split(':', 1)
            col, dir_ = col.strip(), dir_.strip().lower()
            if col in valid_cols and dir_ in ('asc', 'desc'):
                result.append((col, dir_))
    return result


def _cobro_next_sort(current_parsed, column):
    """Ciclo: (ninguno) -> desc -> asc -> (ninguno)."""
    current_dir = next((d for c, d in current_parsed if c == column), None)
    if current_dir == 'desc':
        new_parsed = [(c, 'asc' if c == column else d) for c, d in current_parsed]
        return new_parsed, 'asc'
    if current_dir == 'asc':
        new_parsed = [(c, d) for c, d in current_parsed if c != column]
        return new_parsed, None
    new_parsed = current_parsed + [(column, 'desc')]
    return new_parsed, 'desc'


def _cobro_sort_to_string(parsed):
    return ','.join(f'{c}:{d}' for c, d in parsed)


COBRO_SORTABLE_COLUMNS = [
    ('numero', 'Número'),
    ('cliente', 'Cliente'),
    ('periodo', 'Período'),
    ('vencimiento', 'Vencimiento'),
    ('monto', 'Monto'),
    ('estado', 'Estado'),
]


class CobroListView(LoginRequiredMixin, ListView):
    """Vista para listar cobros con filtros, búsqueda, ordenación y paginación."""
    model = Cobro
    template_name = 'billing/cobro_lista.html'
    context_object_name = 'cobros'
    paginate_by = 50
    PER_PAGE_OPTIONS = (50, 500, 2000)

    def get_queryset(self):
        queryset = super().get_queryset().select_related('contrato', 'contrato__cliente', 'contrato__plan')

        busqueda = self.request.GET.get('q', '').strip()
        if busqueda:
            queryset = queryset.filter(
                Q(contrato__cliente__nombre__icontains=busqueda)
                | Q(contrato__plan__nombre__icontains=busqueda)
                | Q(numero_cobro__icontains=busqueda)
            )

        estado = self.request.GET.get('estado')
        if estado:
            queryset = queryset.filter(estado=estado)

        plan_id = self.request.GET.get('plan')
        if plan_id:
            queryset = queryset.filter(contrato__plan_id=plan_id)

        cliente_id = self.request.GET.get('cliente')
        if cliente_id:
            queryset = queryset.filter(contrato__cliente_id=cliente_id)

        fecha_desde = self.request.GET.get('fecha_desde')
        if fecha_desde:
            try:
                queryset = queryset.filter(periodo_desde__gte=date.fromisoformat(fecha_desde))
            except ValueError:
                pass
        fecha_hasta = self.request.GET.get('fecha_hasta')
        if fecha_hasta:
            try:
                queryset = queryset.filter(periodo_hasta__lte=date.fromisoformat(fecha_hasta))
            except ValueError:
                pass

        vencimiento_desde = self.request.GET.get('vencimiento_desde')
        if vencimiento_desde:
            try:
                queryset = queryset.filter(fecha_vencimiento__gte=date.fromisoformat(vencimiento_desde))
            except ValueError:
                pass
        vencimiento_hasta = self.request.GET.get('vencimiento_hasta')
        if vencimiento_hasta:
            try:
                queryset = queryset.filter(fecha_vencimiento__lte=date.fromisoformat(vencimiento_hasta))
            except ValueError:
                pass

        sort_parsed = _cobro_parse_sort(self.request.GET.get('sort', ''))

        if not sort_parsed:
            # Orden por defecto: estado (vencida, pendiente, pagada) + fecha_vencimiento (asc)
            queryset = queryset.annotate(
                estado_orden_default=Case(
                    When(estado='vencida', then=Value(1)),
                    When(estado='pendiente', then=Value(2)),
                    When(estado='pagada', then=Value(3)),
                    default=Value(2),
                    output_field=IntegerField(),
                ),
                orden_vencimiento=Coalesce(F('fecha_vencimiento'), Value(date(9999, 12, 31))),
            )
            return queryset.order_by('estado_orden_default', 'orden_vencimiento', '-numero_cobro', '-pk')

        # Orden por columnas elegidas
        if 'estado' in [c for c, _ in sort_parsed]:
            queryset = queryset.annotate(
                estado_orden=Case(
                    When(estado='vencida', then=Value(1)),
                    When(estado='pendiente', then=Value(2)),
                    When(estado='pagada', then=Value(3)),
                    default=Value(2),
                    output_field=IntegerField(),
                ),
            )
        order_by_list = []
        for col, dir_ in sort_parsed:
            prefix = '' if dir_ == 'asc' else '-'
            if col == 'numero':
                order_by_list.append(f'{prefix}numero_cobro')
            elif col == 'cliente':
                order_by_list.append(f'{prefix}contrato__cliente__nombre')
            elif col == 'periodo':
                order_by_list.append(f'{prefix}periodo_hasta')
            elif col == 'vencimiento':
                order_by_list.append(f'{prefix}fecha_vencimiento')
            elif col == 'monto':
                order_by_list.append(f'{prefix}monto')
            elif col == 'estado':
                order_by_list.append(f'{prefix}estado_orden')
        order_by_list.append('-pk')
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
        sort_parsed = _cobro_parse_sort(self.request.GET.get('sort', ''))
        sort_headers = []
        for col_key, col_label in COBRO_SORTABLE_COLUMNS:
            next_parsed, next_dir = _cobro_next_sort(sort_parsed, col_key)
            next_sort = _cobro_sort_to_string(next_parsed) if next_parsed else ''
            current_dir = next((d for c, d in sort_parsed if c == col_key), None)
            sort_headers.append({
                'sortable': True,
                'key': col_key,
                'label': col_label,
                'direction': current_dir,
                'next_sort': next_sort,
            })
        context['table_headers'] = sort_headers + [{'sortable': False, 'label': 'Acciones'}]
        context['per_page_current'] = self.get_paginate_by(self.get_queryset())
        context['per_page_options'] = self.PER_PAGE_OPTIONS
        return context


class CobroCreateView(LoginRequiredMixin, CreateView):
    """Vista para crear un nuevo cobro"""
    model = Cobro
    template_name = 'billing/cobro_form.html'
    fields = ['contrato', 'periodo_desde', 'periodo_hasta', 'monto', 'fecha_vencimiento', 'notas']
    success_url = reverse_lazy('billing:cobro_lista')

    def get_initial(self):
        initial = super().get_initial()
        hoy = timezone.now().date()
        initial['periodo_desde'] = hoy
        contrato_id = self.request.GET.get('contrato')
        if contrato_id:
            try:
                contrato = Contrato.objects.get(pk=contrato_id)
                initial['contrato'] = contrato
                initial['periodo_hasta'] = periodo_hasta_segun_frecuencia(
                    hoy, contrato.frecuencia_pago
                )
                initial['monto'] = contrato.precio
            except (Contrato.DoesNotExist, ValueError, TypeError):
                pass
        return initial

    def form_valid(self, form):
        messages.success(self.request, 'Cobro creado correctamente.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['contratos'] = Contrato.objects.filter(q_filtro_estado('activo'))
        return context


class CobroDetailView(LoginRequiredMixin, DetailView):
    model = Cobro
    template_name = 'billing/cobro_detalle.html'
    context_object_name = 'cobro'


class CobroUpdateView(LoginRequiredMixin, UpdateView):
    model = Cobro
    template_name = 'billing/cobro_form.html'
    fields = ['contrato', 'periodo_desde', 'periodo_hasta', 'monto', 'fecha_vencimiento', 'notas']

    def get_success_url(self):
        return reverse('billing:cobro_detalle', args=[self.object.pk])

    def form_valid(self, form):
        messages.success(self.request, 'Cobro actualizado correctamente.')
        return super().form_valid(form)


class CobroDeleteView(LoginRequiredMixin, DeleteView):
    model = Cobro
    template_name = 'billing/cobro_confirm_delete.html'
    success_url = reverse_lazy('billing:cobro_lista')

    def form_valid(self, form):
        messages.success(self.request, 'Cobro eliminado correctamente.')
        return super().form_valid(form)


class PagoCreateView(LoginRequiredMixin, CreateView):
    """Vista para registrar un pago"""
    model = Pago
    template_name = 'billing/pago_form.html'
    fields = ['cobro', 'fecha_pago', 'monto', 'metodo_pago', 'referencia', 'notas']

    def get_success_url(self):
        return reverse('billing:cobro_detalle', args=[self.object.cobro_id])

    def get_initial(self):
        initial = super().get_initial()
        initial['fecha_pago'] = timezone.now().date()
        cobro_id = self.request.GET.get('cobro')
        if cobro_id:
            try:
                cobro = Cobro.objects.get(id=cobro_id)
                initial['cobro'] = cobro
                initial['monto'] = cobro.monto_pendiente()
            except Cobro.DoesNotExist:
                pass
        return initial

    def form_valid(self, form):
        pago = form.save()
        messages.success(self.request, f'Pago de Bs. {pago.monto} registrado correctamente.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cobro_id = self.request.GET.get('cobro')
        if cobro_id:
            context['cobro'] = get_object_or_404(Cobro, id=cobro_id)
        return context


class PagoListView(LoginRequiredMixin, ListView):
    model = Pago
    template_name = 'billing/pago_lista.html'
    context_object_name = 'pagos'
    paginate_by = 50

    def get_queryset(self):
        qs = super().get_queryset().select_related('cobro', 'cobro__contrato__cliente')
        cobro_id = self.request.GET.get('cobro')
        if cobro_id:
            qs = qs.filter(cobro_id=cobro_id)
        return qs.order_by('-fecha_pago', '-fecha_creacion')


class PagoUpdateView(LoginRequiredMixin, UpdateView):
    model = Pago
    template_name = 'billing/pago_form.html'
    fields = ['cobro', 'fecha_pago', 'monto', 'metodo_pago', 'referencia', 'notas']

    def get_success_url(self):
        return reverse('billing:cobro_detalle', args=[self.object.cobro_id])

    def form_valid(self, form):
        messages.success(self.request, 'Pago actualizado correctamente.')
        return super().form_valid(form)


class PagoDeleteView(LoginRequiredMixin, DeleteView):
    model = Pago
    template_name = 'billing/pago_confirm_delete.html'

    def get_success_url(self):
        return reverse('billing:cobro_detalle', args=[self.object.cobro_id])

    def form_valid(self, form):
        messages.success(self.request, 'Pago eliminado correctamente.')
        return super().form_valid(form)


@login_required
def dashboard_cobranza(request):
    """Dashboard de cobranza con estadísticas, alertas y accesos rápidos"""
    hoy = timezone.now().date()
    inicio_mes = hoy.replace(day=1)

    total_cobros = Cobro.objects.count()
    cobros_pendientes = Cobro.objects.filter(estado='pendiente').count()
    cobros_pagados = Cobro.objects.filter(estado='pagada').count()
    cobros_vencidos = obtener_cobros_vencidos().count()

    monto_total_pendiente = Cobro.objects.filter(
        estado__in=['pendiente', 'vencida']
    ).aggregate(total=Sum('monto'))['total'] or 0

    monto_total_pagado = Cobro.objects.filter(
        estado='pagada'
    ).aggregate(total=Sum('monto'))['total'] or 0

    cobrado_este_mes = Pago.objects.filter(
        fecha_pago__gte=inicio_mes,
        fecha_pago__lte=hoy,
    ).aggregate(total=Sum('monto'))['total'] or 0

    ultimos_pagos = (
        Pago.objects.select_related('cobro', 'cobro__contrato', 'cobro__contrato__cliente')
        .order_by('-fecha_pago', '-fecha_creacion')[:12]
    )

    cobros_vencidos_lista = obtener_cobros_vencidos()[:10]

    fecha_limite = hoy + timedelta(days=7)
    cobros_proximos_vencer = Cobro.objects.filter(
        estado='pendiente',
        fecha_vencimiento__lte=fecha_limite,
        fecha_vencimiento__gte=hoy,
    ).select_related('contrato', 'contrato__cliente').order_by('fecha_vencimiento')[:10]

    contratos_activos = Contrato.objects.filter(q_filtro_estado('activo')).count()

    context = {
        'total_cobros': total_cobros,
        'cobros_pendientes': cobros_pendientes,
        'cobros_pagados': cobros_pagados,
        'cobros_vencidos': cobros_vencidos,
        'monto_total_pendiente': monto_total_pendiente,
        'monto_total_pagado': monto_total_pagado,
        'cobrado_este_mes': cobrado_este_mes,
        'ultimos_pagos': ultimos_pagos,
        'cobros_vencidos_lista': cobros_vencidos_lista,
        'cobros_proximos_vencer': cobros_proximos_vencer,
        'contratos_activos': contratos_activos,
    }

    return render(request, 'billing/dashboard.html', context)


@login_required
def reporte_cobranza(request):
    """Vista para generar reportes de cobranza (por cobros, no facturas)."""
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    estado = request.GET.get('estado')
    cliente_id = request.GET.get('cliente')

    cobros = Cobro.objects.select_related('contrato', 'contrato__cliente', 'contrato__plan').all()

    if fecha_desde:
        try:
            fd = date.fromisoformat(fecha_desde)
            cobros = cobros.filter(periodo_desde__gte=fd)
        except ValueError:
            pass

    if fecha_hasta:
        try:
            fh = date.fromisoformat(fecha_hasta)
            cobros = cobros.filter(periodo_hasta__lte=fh)
        except ValueError:
            pass

    if estado:
        cobros = cobros.filter(estado=estado)

    if cliente_id:
        cobros = cobros.filter(contrato__cliente_id=cliente_id)

    cobros = cobros.order_by('-periodo_hasta', '-pk')

    total_monto = cobros.aggregate(total=Sum('monto'))['total'] or 0
    total_pagado = sum(c.calcular_monto_pagado() for c in cobros)
    total_pendiente = total_monto - total_pagado

    context = {
        'cobros': cobros,
        'total_monto': total_monto,
        'total_pagado': total_pagado,
        'total_pendiente': total_pendiente,
        'fecha_desde': fecha_desde or '',
        'fecha_hasta': fecha_hasta or '',
        'estado': estado or '',
        'clientes': Cliente.objects.order_by('nombre'),
    }

    return render(request, 'billing/reporte.html', context)

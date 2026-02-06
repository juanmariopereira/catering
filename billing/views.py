from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.utils import timezone
import json
from django.db.models import Q, Sum, F, Case, When, Value, IntegerField
from django.db.models.functions import Coalesce
from datetime import date, timedelta

from .models import Cobro, Pago
from .utils import (
    fecha_vencimiento_default,
    dias_vencimiento_para_contrato,
    obtener_cobros_vencidos,
    periodo_hasta_segun_frecuencia,
)
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
                contrato = Contrato.objects.select_related('plan').get(pk=contrato_id)
                initial['contrato'] = contrato
                periodo_hasta = periodo_hasta_segun_frecuencia(hoy, contrato.frecuencia_pago)
                initial['periodo_hasta'] = periodo_hasta
                initial['monto'] = contrato.precio
                initial['fecha_vencimiento'] = fecha_vencimiento_default(contrato, periodo_hasta)
            except (Contrato.DoesNotExist, ValueError, TypeError):
                pass
        return initial

    def form_valid(self, form):
        messages.success(self.request, 'Cobro creado correctamente.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contratos = Contrato.objects.filter(q_filtro_estado('activo')).select_related('plan')
        context['contratos'] = contratos
        context['contratos_dias_vencimiento_json'] = json.dumps(
            {str(c.id): dias_vencimiento_para_contrato(c) for c in contratos}
        )
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contratos = Contrato.objects.filter(q_filtro_estado('activo')).select_related('plan')
        context['contratos_dias_vencimiento_json'] = json.dumps(
            {str(c.id): dias_vencimiento_para_contrato(c) for c in contratos}
        )
        return context

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


@login_required
def estado_cuentas_por_cliente(request):
    """Reporte detallado de estado de cuentas agrupado por cliente."""
    from decimal import Decimal

    cliente_id = request.GET.get('cliente')
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')

    # Clientes que tienen al menos un contrato con cobros
    contratos = (
        Contrato.objects.select_related('cliente', 'plan')
        .prefetch_related('cobros__pagos')
        .order_by('cliente__nombre', '-fecha_inicio')
    )
    if cliente_id:
        contratos = contratos.filter(cliente_id=cliente_id)

    fd = None
    fh = None
    if fecha_desde:
        try:
            fd = date.fromisoformat(fecha_desde)
        except ValueError:
            pass
    if fecha_hasta:
        try:
            fh = date.fromisoformat(fecha_hasta)
        except ValueError:
            pass

    def cobros_filtrados(contrato):
        cobros = sorted(contrato.cobros.all(), key=lambda c: (c.periodo_hasta or date.min, c.pk), reverse=True)
        if fd is not None:
            cobros = [c for c in cobros if c.periodo_desde >= fd]
        if fh is not None:
            cobros = [c for c in cobros if (c.periodo_hasta or date.min) <= fh]
        return cobros

    # Agrupar por cliente
    clientes_data = []
    cliente_actual = None
    bloque_cliente = None

    for contrato in contratos:
        cobros = cobros_filtrados(contrato)
        if not cobros and not cliente_id:
            continue
        if contrato.cliente != cliente_actual:
            if bloque_cliente and (bloque_cliente['contratos'] or cliente_id):
                clientes_data.append(bloque_cliente)
            cliente_actual = contrato.cliente
            bloque_cliente = {
                'cliente': contrato.cliente,
                'contratos': [],
                'total_monto': Decimal('0'),
                'total_pagado': Decimal('0'),
                'total_pendiente': Decimal('0'),
            }
        sub_monto = sum(c.monto for c in cobros)
        sub_pagado = sum(c.calcular_monto_pagado() for c in cobros)
        sub_pendiente = sub_monto - sub_pagado
        bloque_cliente['contratos'].append({
            'contrato': contrato,
            'cobros': cobros,
            'subtotal_monto': sub_monto,
            'subtotal_pagado': sub_pagado,
            'subtotal_pendiente': sub_pendiente,
        })
        bloque_cliente['total_monto'] += sub_monto
        bloque_cliente['total_pagado'] += sub_pagado
        bloque_cliente['total_pendiente'] += sub_pendiente
    if bloque_cliente and (bloque_cliente['contratos'] or cliente_id):
        clientes_data.append(bloque_cliente)

    total_general_monto = sum(b['total_monto'] for b in clientes_data)
    total_general_pagado = sum(b['total_pagado'] for b in clientes_data)
    total_general_pendiente = sum(b['total_pendiente'] for b in clientes_data)

    context = {
        'clientes_data': clientes_data,
        'total_general_monto': total_general_monto,
        'total_general_pagado': total_general_pagado,
        'total_general_pendiente': total_general_pendiente,
        'clientes': Cliente.objects.order_by('nombre'),
        'fecha_desde': fecha_desde or '',
        'fecha_hasta': fecha_hasta or '',
        'cliente_id': cliente_id or '',
    }
    return render(request, 'billing/estado_cuentas.html', context)


@login_required
def estado_cuentas_cliente_detalle(request, cliente_id):
    """Detalle de estado de cuentas para un cliente: contratos, cobros y pagos."""
    from decimal import Decimal

    cliente = get_object_or_404(Cliente, pk=cliente_id)
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')

    contratos = (
        Contrato.objects.filter(cliente=cliente)
        .select_related('plan')
        .prefetch_related('cobros__pagos')
        .order_by('-fecha_inicio')
    )

    fd = None
    fh = None
    if fecha_desde:
        try:
            fd = date.fromisoformat(fecha_desde)
        except ValueError:
            pass
    if fecha_hasta:
        try:
            fh = date.fromisoformat(fecha_hasta)
        except ValueError:
            pass

    def cobros_filtrados(contrato):
        cobros = sorted(contrato.cobros.all(), key=lambda c: (c.periodo_hasta or date.min, c.pk), reverse=True)
        if fd is not None:
            cobros = [c for c in cobros if c.periodo_desde >= fd]
        if fh is not None:
            cobros = [c for c in cobros if (c.periodo_hasta or date.min) <= fh]
        return cobros

    bloque_cliente = {
        'cliente': cliente,
        'contratos': [],
        'total_monto': Decimal('0'),
        'total_pagado': Decimal('0'),
        'total_pendiente': Decimal('0'),
    }
    for contrato in contratos:
        cobros = cobros_filtrados(contrato)
        sub_monto = sum(c.monto for c in cobros)
        sub_pagado = sum(c.calcular_monto_pagado() for c in cobros)
        sub_pendiente = sub_monto - sub_pagado
        bloque_cliente['contratos'].append({
            'contrato': contrato,
            'cobros': cobros,
            'subtotal_monto': sub_monto,
            'subtotal_pagado': sub_pagado,
            'subtotal_pendiente': sub_pendiente,
        })
        bloque_cliente['total_monto'] += sub_monto
        bloque_cliente['total_pagado'] += sub_pagado
        bloque_cliente['total_pendiente'] += sub_pendiente

    context = {
        'cliente': cliente,
        'bloque': bloque_cliente,
        'fecha_desde': fecha_desde or '',
        'fecha_hasta': fecha_hasta or '',
    }
    return render(request, 'billing/estado_cuentas_cliente_detalle.html', context)


@login_required
def reporte_ventas(request):
    """Reporte detallado de ventas: contratos creados y pagos en el rango de fechas. Por defecto últimos 30 días."""
    hoy = timezone.now().date()
    default_desde = hoy - timedelta(days=30)

    fecha_desde_str = request.GET.get('fecha_desde')
    fecha_hasta_str = request.GET.get('fecha_hasta')
    cliente_id = request.GET.get('cliente')
    plan_id = request.GET.get('plan')

    try:
        fecha_desde = date.fromisoformat(fecha_desde_str) if fecha_desde_str else default_desde
    except ValueError:
        fecha_desde = default_desde
    try:
        fecha_hasta = date.fromisoformat(fecha_hasta_str) if fecha_hasta_str else hoy
    except ValueError:
        fecha_hasta = hoy
    if fecha_desde > fecha_hasta:
        fecha_desde, fecha_hasta = fecha_hasta, fecha_desde

    # Contratos creados en el período
    contratos = (
        Contrato.objects.select_related('cliente', 'plan')
        .filter(
            fecha_creacion__date__gte=fecha_desde,
            fecha_creacion__date__lte=fecha_hasta,
        )
        .order_by('-fecha_creacion')
    )
    if cliente_id:
        contratos = contratos.filter(cliente_id=cliente_id)
    if plan_id:
        contratos = contratos.filter(plan_id=plan_id)
    contratos = list(contratos)

    total_contratos_precio = sum(c.precio for c in contratos)

    # Pagos en el período
    pagos = (
        Pago.objects.select_related('cobro', 'cobro__contrato', 'cobro__contrato__cliente', 'cobro__contrato__plan')
        .filter(
            fecha_pago__gte=fecha_desde,
            fecha_pago__lte=fecha_hasta,
        )
        .order_by('-fecha_pago', '-fecha_creacion')
    )
    if cliente_id:
        pagos = pagos.filter(cobro__contrato__cliente_id=cliente_id)
    if plan_id:
        pagos = pagos.filter(cobro__contrato__plan_id=plan_id)
    pagos = list(pagos)

    total_pagos = sum(p.monto for p in pagos)

    context = {
        'contratos': contratos,
        'pagos': pagos,
        'total_contratos': len(contratos),
        'total_contratos_precio': total_contratos_precio,
        'total_pagos': total_pagos,
        'fecha_desde': fecha_desde.isoformat(),
        'fecha_hasta': fecha_hasta.isoformat(),
        'clientes': Cliente.objects.order_by('nombre'),
        'planes': Plan.objects.filter(activo=True).order_by('nombre'),
        'cliente_id': cliente_id or '',
        'plan_id': plan_id or '',
    }
    return render(request, 'billing/reporte_ventas.html', context)

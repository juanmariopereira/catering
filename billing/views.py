from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Sum, F
from datetime import date, timedelta
from .models import Cobro, Pago
from .utils import obtener_cobros_vencidos
from contracts.models import Contrato


class CobroListView(LoginRequiredMixin, ListView):
    """Vista para listar cobros"""
    model = Cobro
    template_name = 'billing/cobro_lista.html'
    context_object_name = 'cobros'
    paginate_by = 30

    def get_queryset(self):
        queryset = super().get_queryset()
        estado = self.request.GET.get('estado')
        if estado:
            queryset = queryset.filter(estado=estado)
        cliente_id = self.request.GET.get('cliente')
        if cliente_id:
            queryset = queryset.filter(contrato__cliente_id=cliente_id)
        fecha_desde = self.request.GET.get('fecha_desde')
        fecha_hasta = self.request.GET.get('fecha_hasta')
        if fecha_desde:
            try:
                fecha = date.fromisoformat(fecha_desde)
                queryset = queryset.filter(periodo_desde__gte=fecha)
            except ValueError:
                pass
        if fecha_hasta:
            try:
                fecha = date.fromisoformat(fecha_hasta)
                queryset = queryset.filter(periodo_hasta__lte=fecha)
            except ValueError:
                pass
        return queryset.order_by('-periodo_hasta', '-numero_cobro')


class CobroCreateView(LoginRequiredMixin, CreateView):
    """Vista para crear un nuevo cobro"""
    model = Cobro
    template_name = 'billing/cobro_form.html'
    fields = ['contrato', 'periodo_desde', 'periodo_hasta', 'monto', 'fecha_vencimiento', 'notas']
    success_url = reverse_lazy('billing:cobro_lista')

    def get_initial(self):
        initial = super().get_initial()
        contrato_id = self.request.GET.get('contrato')
        if contrato_id:
            try:
                contrato = Contrato.objects.get(pk=contrato_id)
                initial['contrato'] = contrato
            except (Contrato.DoesNotExist, ValueError, TypeError):
                pass
        return initial

    def form_valid(self, form):
        messages.success(self.request, 'Cobro creado correctamente.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['contratos'] = Contrato.objects.filter(estado='activo')
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
        messages.success(self.request, f'Pago de {pago.monto} registrado correctamente.')
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
    cobros_vencidos = Cobro.objects.filter(estado='vencida').count()

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

    contratos_activos = Contrato.objects.filter(estado='activo').count()

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
    """Vista para generar reportes de cobranza"""
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    estado = request.GET.get('estado')
    cliente_id = request.GET.get('cliente')

    cobros = Cobro.objects.all()

    if fecha_desde:
        try:
            fecha = date.fromisoformat(fecha_desde)
            cobros = cobros.filter(periodo_desde__gte=fecha)
        except ValueError:
            pass

    if fecha_hasta:
        try:
            fecha = date.fromisoformat(fecha_hasta)
            cobros = cobros.filter(periodo_hasta__lte=fecha)
        except ValueError:
            pass

    if estado:
        cobros = cobros.filter(estado=estado)

    if cliente_id:
        cobros = cobros.filter(contrato__cliente_id=cliente_id)

    cobros = cobros.order_by('-periodo_hasta')

    total_monto = cobros.aggregate(total=Sum('monto'))['total'] or 0
    total_pagado = sum(c.calcular_monto_pagado() for c in cobros)
    total_pendiente = total_monto - total_pagado

    context = {
        'cobros': cobros,
        'total_monto': total_monto,
        'total_pagado': total_pagado,
        'total_pendiente': total_pendiente,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'estado': estado,
    }

    return render(request, 'billing/reporte.html', context)

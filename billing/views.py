from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Sum, F
from datetime import date, timedelta
from .models import Factura, Pago
from .utils import obtener_facturas_vencidas
from contracts.models import Contrato


class FacturaListView(LoginRequiredMixin, ListView):
    """Vista para listar facturas"""
    model = Factura
    template_name = 'billing/factura_lista.html'
    context_object_name = 'facturas'
    paginate_by = 30

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtrar por estado si se proporciona
        estado = self.request.GET.get('estado')
        if estado:
            queryset = queryset.filter(estado=estado)
        
        # Filtrar por cliente si se proporciona
        cliente_id = self.request.GET.get('cliente')
        if cliente_id:
            queryset = queryset.filter(contrato__cliente_id=cliente_id)
        
        # Filtrar por rango de fechas si se proporciona
        fecha_desde = self.request.GET.get('fecha_desde')
        fecha_hasta = self.request.GET.get('fecha_hasta')
        
        if fecha_desde:
            try:
                fecha = date.fromisoformat(fecha_desde)
                queryset = queryset.filter(fecha_emision__gte=fecha)
            except ValueError:
                pass
        
        if fecha_hasta:
            try:
                fecha = date.fromisoformat(fecha_hasta)
                queryset = queryset.filter(fecha_emision__lte=fecha)
            except ValueError:
                pass
        
        return queryset.order_by('-fecha_emision', '-numero_factura')


class FacturaCreateView(LoginRequiredMixin, CreateView):
    """Vista para crear una nueva factura"""
    model = Factura
    template_name = 'billing/factura_form.html'
    fields = ['contrato', 'fecha_emision', 'fecha_vencimiento', 'monto', 'periodo_desde', 'periodo_hasta', 'notas']
    success_url = reverse_lazy('billing:factura_lista')

    def form_valid(self, form):
        messages.success(self.request, 'Factura creada exitosamente.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['contratos'] = Contrato.objects.filter(estado='activo')
        return context


class FacturaDetailView(LoginRequiredMixin, DetailView):
    model = Factura
    template_name = 'billing/factura_detalle.html'
    context_object_name = 'factura'


class FacturaUpdateView(LoginRequiredMixin, UpdateView):
    model = Factura
    template_name = 'billing/factura_form.html'
    fields = ['contrato', 'fecha_emision', 'fecha_vencimiento', 'monto', 'periodo_desde', 'periodo_hasta', 'notas']

    def get_success_url(self):
        return reverse('billing:factura_detalle', args=[self.object.pk])

    def form_valid(self, form):
        messages.success(self.request, 'Factura actualizada exitosamente.')
        return super().form_valid(form)


class FacturaDeleteView(LoginRequiredMixin, DeleteView):
    model = Factura
    template_name = 'billing/factura_confirm_delete.html'
    success_url = reverse_lazy('billing:factura_lista')

    def form_valid(self, form):
        messages.success(self.request, 'Factura eliminada exitosamente.')
        return super().form_valid(form)


class PagoCreateView(LoginRequiredMixin, CreateView):
    """Vista para registrar un pago"""
    model = Pago
    template_name = 'billing/pago_form.html'
    fields = ['factura', 'fecha_pago', 'monto', 'metodo_pago', 'referencia', 'notas']

    def get_success_url(self):
        factura_id = self.object.factura_id
        return reverse('billing:factura_detalle', args=[factura_id])

    def get_initial(self):
        initial = super().get_initial()
        initial['fecha_pago'] = timezone.now().date()
        factura_id = self.request.GET.get('factura')
        if factura_id:
            try:
                factura = Factura.objects.get(id=factura_id)
                initial['factura'] = factura
                initial['monto'] = factura.monto_pendiente()
            except Factura.DoesNotExist:
                pass
        return initial

    def form_valid(self, form):
        pago = form.save()
        messages.success(self.request, f'Pago de {pago.monto} registrado exitosamente.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        factura_id = self.request.GET.get('factura')
        if factura_id:
            context['factura'] = get_object_or_404(Factura, id=factura_id)
        return context


class PagoListView(LoginRequiredMixin, ListView):
    model = Pago
    template_name = 'billing/pago_lista.html'
    context_object_name = 'pagos'
    paginate_by = 50

    def get_queryset(self):
        qs = super().get_queryset().select_related('factura', 'factura__contrato__cliente')
        factura_id = self.request.GET.get('factura')
        if factura_id:
            qs = qs.filter(factura_id=factura_id)
        return qs.order_by('-fecha_pago', '-fecha_creacion')


class PagoUpdateView(LoginRequiredMixin, UpdateView):
    model = Pago
    template_name = 'billing/pago_form.html'
    fields = ['factura', 'fecha_pago', 'monto', 'metodo_pago', 'referencia', 'notas']

    def get_success_url(self):
        return reverse('billing:factura_detalle', args=[self.object.factura_id])

    def form_valid(self, form):
        messages.success(self.request, 'Pago actualizado exitosamente.')
        return super().form_valid(form)


class PagoDeleteView(LoginRequiredMixin, DeleteView):
    model = Pago
    template_name = 'billing/pago_confirm_delete.html'

    def get_success_url(self):
        return reverse('billing:factura_detalle', args=[self.object.factura_id])

    def form_valid(self, form):
        messages.success(self.request, 'Pago eliminado exitosamente.')
        return super().form_valid(form)


@login_required
def dashboard_cobranza(request):
    """Dashboard de cobranza con estadísticas, alertas y accesos rápidos"""
    hoy = timezone.now().date()
    inicio_mes = hoy.replace(day=1)

    # Estadísticas generales
    total_facturas = Factura.objects.count()
    facturas_pendientes = Factura.objects.filter(estado='pendiente').count()
    facturas_pagadas = Factura.objects.filter(estado='pagada').count()
    facturas_vencidas = Factura.objects.filter(estado='vencida').count()

    # Montos
    monto_total_pendiente = Factura.objects.filter(
        estado__in=['pendiente', 'vencida']
    ).aggregate(total=Sum('monto'))['total'] or 0

    monto_total_pagado = Factura.objects.filter(
        estado='pagada'
    ).aggregate(total=Sum('monto'))['total'] or 0

    # Cobrado este mes
    cobrado_este_mes = Pago.objects.filter(
        fecha_pago__gte=inicio_mes,
        fecha_pago__lte=hoy,
    ).aggregate(total=Sum('monto'))['total'] or 0

    # Últimos pagos (actividad reciente)
    ultimos_pagos = (
        Pago.objects.select_related('factura', 'factura__contrato', 'factura__contrato__cliente')
        .order_by('-fecha_pago', '-fecha_creacion')[:12]
    )

    # Facturas vencidas
    facturas_vencidas_lista = obtener_facturas_vencidas()[:10]

    # Próximas a vencer (próximos 7 días)
    fecha_limite = hoy + timedelta(days=7)
    facturas_proximas_vencer = Factura.objects.filter(
        estado='pendiente',
        fecha_vencimiento__lte=fecha_limite,
        fecha_vencimiento__gte=hoy,
    ).select_related('contrato', 'contrato__cliente').order_by('fecha_vencimiento')[:10]

    # Contratos activos (para contexto / enlaces)
    contratos_activos = Contrato.objects.filter(estado='activo').count()

    context = {
        'total_facturas': total_facturas,
        'facturas_pendientes': facturas_pendientes,
        'facturas_pagadas': facturas_pagadas,
        'facturas_vencidas': facturas_vencidas,
        'monto_total_pendiente': monto_total_pendiente,
        'monto_total_pagado': monto_total_pagado,
        'cobrado_este_mes': cobrado_este_mes,
        'ultimos_pagos': ultimos_pagos,
        'facturas_vencidas_lista': facturas_vencidas_lista,
        'facturas_proximas_vencer': facturas_proximas_vencer,
        'contratos_activos': contratos_activos,
    }

    return render(request, 'billing/dashboard.html', context)


@login_required
def reporte_cobranza(request):
    """Vista para generar reportes de cobranza"""
    # Obtener parámetros de filtro
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    estado = request.GET.get('estado')
    cliente_id = request.GET.get('cliente')
    
    facturas = Factura.objects.all()
    
    if fecha_desde:
        try:
            fecha = date.fromisoformat(fecha_desde)
            facturas = facturas.filter(fecha_emision__gte=fecha)
        except ValueError:
            pass
    
    if fecha_hasta:
        try:
            fecha = date.fromisoformat(fecha_hasta)
            facturas = facturas.filter(fecha_emision__lte=fecha)
        except ValueError:
            pass
    
    if estado:
        facturas = facturas.filter(estado=estado)
    
    if cliente_id:
        facturas = facturas.filter(contrato__cliente_id=cliente_id)
    
    facturas = facturas.order_by('-fecha_emision')
    
    # Calcular totales
    total_monto = facturas.aggregate(total=Sum('monto'))['total'] or 0
    total_pagado = sum(factura.calcular_monto_pagado() for factura in facturas)
    total_pendiente = total_monto - total_pagado
    
    context = {
        'facturas': facturas,
        'total_monto': total_monto,
        'total_pagado': total_pagado,
        'total_pendiente': total_pendiente,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'estado': estado,
    }
    
    return render(request, 'billing/reporte.html', context)

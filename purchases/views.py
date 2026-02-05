from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.utils import timezone
from datetime import date, timedelta
import csv
from .models import PrevisionCompra
from .forms import PrevisionCompraForm


class PrevisionCompraListView(LoginRequiredMixin, ListView):
    """Vista para listar previsiones de compra"""
    model = PrevisionCompra
    template_name = 'purchases/prevision_lista.html'
    context_object_name = 'previsiones'
    paginate_by = 30

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtrar por rango de fechas si se proporciona
        fecha_desde = self.request.GET.get('fecha_desde')
        fecha_hasta = self.request.GET.get('fecha_hasta')
        
        if fecha_desde:
            try:
                fecha = date.fromisoformat(fecha_desde)
                queryset = queryset.filter(fecha_desde__gte=fecha)
            except ValueError:
                pass
        
        if fecha_hasta:
            try:
                fecha = date.fromisoformat(fecha_hasta)
                queryset = queryset.filter(fecha_hasta__lte=fecha)
            except ValueError:
                pass
        
        return queryset.order_by('-fecha_generacion')


class PrevisionCompraCreateView(LoginRequiredMixin, CreateView):
    """Vista para crear una nueva previsión de compra"""
    model = PrevisionCompra
    form_class = PrevisionCompraForm
    template_name = 'purchases/prevision_form.html'
    success_url = reverse_lazy('purchases:lista')

    def get_initial(self):
        initial = super().get_initial()
        manana = date.today() + timedelta(days=1)
        initial['fecha_desde'] = manana
        initial['fecha_hasta'] = manana
        return initial

    def form_valid(self, form):
        prevision = form.save()
        # Calcular items automáticamente
        prevision.calcular_items()
        messages.success(
            self.request,
            f'Previsión creada exitosamente con {prevision.items.count()} items.'
        )
        return super().form_valid(form)


class PrevisionCompraDetailView(LoginRequiredMixin, DetailView):
    """Vista para ver el detalle de una previsión de compra"""
    model = PrevisionCompra
    template_name = 'purchases/prevision_detalle.html'
    context_object_name = 'prevision'

    def get_context_data(self, **kwargs):
        from purchases.utils import agrupar_items_prevision_por_tipo
        context = super().get_context_data(**kwargs)
        items_qs = (
            self.object.items
            .select_related('ingrediente', 'ingrediente__tipo_ingrediente', 'unidad_medida')
            .order_by('ingrediente__nombre')
        )
        context['items_por_tipo'] = agrupar_items_prevision_por_tipo(items_qs)
        return context


class PrevisionCompraUpdateView(LoginRequiredMixin, UpdateView):
    """Vista para editar una previsión de compra (fechas y notas; items se recalculan)"""
    model = PrevisionCompra
    form_class = PrevisionCompraForm
    template_name = 'purchases/prevision_form.html'
    context_object_name = 'prevision'

    def get_success_url(self):
        return reverse('purchases:detalle', args=[self.object.pk])

    def form_valid(self, form):
        self.object = form.save()
        self.object.calcular_items()
        messages.success(self.request, 'Previsión actualizada. Los ítems se han recalculado.')
        return redirect(self.get_success_url())


class PrevisionCompraDeleteView(LoginRequiredMixin, DeleteView):
    model = PrevisionCompra
    template_name = 'purchases/prevision_confirm_delete.html'
    context_object_name = 'prevision'
    success_url = reverse_lazy('purchases:lista')

    def form_valid(self, form):
        messages.success(self.request, 'Previsión eliminada.')
        return super().form_valid(form)


@login_required
def exportar_excel(request, prevision_id):
    """Exporta una previsión de compra a formato Excel (CSV)"""
    prevision = get_object_or_404(PrevisionCompra, id=prevision_id)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="prevision_compra_{prevision.fecha_desde}_{prevision.fecha_hasta}.csv"'
    
    from purchases.utils import (
        prevision_cantidad_display,
        prevision_unidad_display,
        prevision_medida_por_unidad_item_display,
        agrupar_items_prevision_por_tipo,
    )

    writer = csv.writer(response)
    writer.writerow(['Tipo', 'Ingrediente', 'Cantidad Total', 'Unidad de Medida', 'Medida por unidad'])

    items_qs = prevision.items.select_related(
        'ingrediente', 'ingrediente__tipo_ingrediente', 'unidad_medida'
    ).order_by('ingrediente__nombre')
    items_por_tipo = agrupar_items_prevision_por_tipo(items_qs)

    for grupo in items_por_tipo:
        for item in grupo['items']:
            writer.writerow([
                grupo['tipo_nombre'],
                item.ingrediente.nombre,
                prevision_cantidad_display(item.cantidad_total, item.unidad_medida),
                prevision_unidad_display(item.cantidad_total, item.unidad_medida),
                prevision_medida_por_unidad_item_display(item) or '',
            ])

    return response


@login_required
def exportar_pdf(request, prevision_id):
    """Exporta una previsión de compra a formato PDF"""
    from purchases.utils import agrupar_items_prevision_por_tipo
    # Nota: Para PDF real necesitarías instalar reportlab o weasyprint
    # Por ahora, retornamos una vista HTML que se puede imprimir como PDF
    prevision = get_object_or_404(PrevisionCompra, id=prevision_id)
    items_qs = prevision.items.select_related(
        'ingrediente', 'ingrediente__tipo_ingrediente', 'unidad_medida'
    ).order_by('ingrediente__nombre')
    context = {
        'prevision': prevision,
        'items_por_tipo': agrupar_items_prevision_por_tipo(items_qs),
    }
    return render(request, 'purchases/prevision_pdf.html', context)


@login_required
def prevision_checklist_imprimible(request, prevision_id):
    """
    Reporte imprimible tipo checklist para la previsión de compra.
    Muestra los ítems agrupados por tipo con casilla para marcar al comprar.
    """
    from purchases.utils import agrupar_items_prevision_por_tipo
    prevision = get_object_or_404(PrevisionCompra, id=prevision_id)
    items_qs = prevision.items.select_related(
        'ingrediente', 'ingrediente__tipo_ingrediente', 'unidad_medida'
    ).order_by('ingrediente__nombre')
    context = {
        'prevision': prevision,
        'items_por_tipo': agrupar_items_prevision_por_tipo(items_qs),
    }
    return render(request, 'purchases/prevision_checklist_imprimible.html', context)

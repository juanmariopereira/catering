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
    template_name = 'purchases/prevision_form.html'
    fields = ['fecha_desde', 'fecha_hasta', 'notas']
    success_url = reverse_lazy('purchases:lista')

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


class PrevisionCompraUpdateView(LoginRequiredMixin, UpdateView):
    """Vista para editar una previsión de compra (fechas y notas; items se recalculan)"""
    model = PrevisionCompra
    template_name = 'purchases/prevision_form.html'
    fields = ['fecha_desde', 'fecha_hasta', 'notas']
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
    
    writer = csv.writer(response)
    writer.writerow(['Ingrediente', 'Cantidad Total', 'Unidad de Medida'])
    
    for item in prevision.items.all().order_by('ingrediente__nombre'):
        writer.writerow([
            item.ingrediente.nombre,
            item.cantidad_total,
            item.unidad_medida
        ])
    
    return response


@login_required
def exportar_pdf(request, prevision_id):
    """Exporta una previsión de compra a formato PDF"""
    # Nota: Para PDF real necesitarías instalar reportlab o weasyprint
    # Por ahora, retornamos una vista HTML que se puede imprimir como PDF
    prevision = get_object_or_404(PrevisionCompra, id=prevision_id)
    
    context = {
        'prevision': prevision,
        'items': prevision.items.all().order_by('ingrediente__nombre'),
    }
    
    return render(request, 'purchases/prevision_pdf.html', context)

from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, DetailView
from django.utils import timezone
from datetime import date, timedelta
from .models import DetalleCocina


class DetalleCocinaListView(ListView):
    """Vista para listar detalles de cocina por fecha"""
    model = DetalleCocina
    template_name = 'kitchen/detalle_lista.html'
    context_object_name = 'detalles'
    paginate_by = 30

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtrar por fecha si se proporciona
        fecha_param = self.request.GET.get('fecha')
        if fecha_param:
            try:
                fecha = date.fromisoformat(fecha_param)
                queryset = queryset.filter(fecha=fecha)
            except ValueError:
                pass
        
        return queryset.order_by('-fecha')


def detalle_cocina_fecha(request, fecha_str=None):
    """
    Vista para mostrar el detalle de platos a elaborar en una fecha específica
    """
    if fecha_str:
        try:
            fecha = date.fromisoformat(fecha_str)
        except ValueError:
            fecha = timezone.now().date()
    else:
        fecha = timezone.now().date()

    # Obtener recetas a preparar para esta fecha
    recetas_info = DetalleCocina.obtener_recetas_por_fecha(fecha)

    # Obtener o crear el detalle de cocina
    detalle_cocina, created = DetalleCocina.objects.get_or_create(fecha=fecha)

    context = {
        'fecha': fecha,
        'detalle_cocina': detalle_cocina,
        'recetas_info': recetas_info,
        'fecha_anterior': fecha - timedelta(days=1),
        'fecha_siguiente': fecha + timedelta(days=1),
    }

    return render(request, 'kitchen/detalle_fecha.html', context)

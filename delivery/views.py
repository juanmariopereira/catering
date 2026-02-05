from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView
from django.utils import timezone
from datetime import date
from routes.models import Ruta, Entregador


class RutaListView(ListView):
    """Vista para listar rutas de entrega"""
    model = Ruta
    template_name = 'delivery/ruta_lista.html'
    context_object_name = 'rutas'
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
        
        # Filtrar por entregador si se proporciona
        entregador_id = self.request.GET.get('entregador')
        if entregador_id:
            queryset = queryset.filter(entregador_id=entregador_id)
        
        return queryset.order_by('-fecha', 'entregador')


def ruta_imprimible(request, ruta_id):
    """
    Vista para mostrar una ruta de entrega en formato imprimible
    """
    ruta = get_object_or_404(Ruta, id=ruta_id)
    
    # Obtener clientes de la ruta ordenados por orden de entrega
    ruta_clientes = ruta.ruta_clientes.all().order_by('orden_entrega')
    
    context = {
        'ruta': ruta,
        'ruta_clientes': ruta_clientes,
    }
    
    return render(request, 'delivery/ruta_imprimible.html', context)


def ruta_por_fecha_entregador(request, fecha_str, entregador_id):
    """
    Vista para mostrar ruta de entrega por fecha y entregador
    """
    try:
        fecha = date.fromisoformat(fecha_str)
    except ValueError:
        fecha = timezone.now().date()
    
    entregador = get_object_or_404(Entregador, id=entregador_id)
    
    # Obtener o crear la ruta
    ruta, created = Ruta.objects.get_or_create(
        fecha=fecha,
        entregador=entregador,
        defaults={'activa': True}
    )
    
    # Obtener clientes de la ruta ordenados por orden de entrega
    ruta_clientes = ruta.ruta_clientes.all().order_by('orden_entrega')
    
    context = {
        'ruta': ruta,
        'entregador': entregador,
        'fecha': fecha,
        'ruta_clientes': ruta_clientes,
    }
    
    return render(request, 'delivery/ruta_imprimible.html', context)

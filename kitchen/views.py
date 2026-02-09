from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, UpdateView
from django.urls import reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import date, timedelta
from .models import DetalleCocina


class DetalleCocinaListView(LoginRequiredMixin, ListView):
    """Vista para listar detalles de cocina por fecha"""
    model = DetalleCocina
    template_name = 'kitchen/detalle_lista.html'
    context_object_name = 'detalles'
    paginate_by = 30

    def get_queryset(self):
        queryset = super().get_queryset()
        fecha_desde = self.request.GET.get('fecha_desde')
        if fecha_desde:
            try:
                fd = date.fromisoformat(fecha_desde)
                queryset = queryset.filter(fecha__gte=fd)
            except ValueError:
                pass
        fecha_hasta = self.request.GET.get('fecha_hasta')
        if fecha_hasta:
            try:
                fh = date.fromisoformat(fecha_hasta)
                queryset = queryset.filter(fecha__lte=fh)
            except ValueError:
                pass
        return queryset.order_by('-fecha')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        get_copy = self.request.GET.copy()
        if 'page' in get_copy:
            get_copy.pop('page')
        context['query_string'] = get_copy.urlencode()
        context['hoy'] = timezone.now().date()
        return context


class DetalleCocinaUpdateView(LoginRequiredMixin, UpdateView):
    """Vista para editar solo las notas del detalle de cocina."""
    model = DetalleCocina
    template_name = 'kitchen/detalle_cocina_form.html'
    fields = ['notas']
    context_object_name = 'detalle_cocina'

    def get_success_url(self):
        fecha_str = self.object.fecha.strftime('%Y-%m-%d')
        return reverse('kitchen:detalle_fecha', args=[fecha_str])

    def form_valid(self, form):
        messages.success(self.request, 'Notas guardadas.')
        return super().form_valid(form)


@login_required
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
    from planning.utils import resumen_cocina_por_momento
    from delivery.utils import contratos_en_ruta_fecha
    from routes.models import PlantillaRutaCliente
    resumen_momento = resumen_cocina_por_momento(fecha)

    # Códigos de entrega por contrato en esta fecha (desde plantilla)
    ids_en_ruta = contratos_en_ruta_fecha(fecha)
    rutas_clientes_fecha = dict(
        PlantillaRutaCliente.objects.filter(contrato_id__in=ids_en_ruta).values_list('contrato_id', 'codigo_entrega')
    )

    for item in recetas_info:
        for p in item.get('planificaciones', []):
            c = p.get('contrato')
            cid = c.id if c else None
            p['codigo_entrega'] = rutas_clientes_fecha.get(cid) if cid else None
            # Hora de entrega pactada en el contrato
            p['hora_entrega'] = (c.horario_entrega.strftime('%H:%M') if c and c.horario_entrega and hasattr(c.horario_entrega, 'strftime') else '')

    # Obtener o crear el detalle de cocina
    detalle_cocina, created = DetalleCocina.objects.get_or_create(fecha=fecha)

    from base.models import es_feriado, get_feriado
    context = {
        'fecha': fecha,
        'detalle_cocina': detalle_cocina,
        'recetas_info': recetas_info,
        'resumen_momento': resumen_momento,
        'fecha_anterior': fecha - timedelta(days=1),
        'fecha_siguiente': fecha + timedelta(days=1),
        'es_feriado': es_feriado(fecha),
        'feriado': get_feriado(fecha),
    }

    return render(request, 'kitchen/detalle_fecha.html', context)

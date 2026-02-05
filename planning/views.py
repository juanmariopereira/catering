from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib import messages
from django.utils import timezone
from datetime import date, timedelta
from .models import PlanificacionDieta
from .utils import sugerir_recetas_alternativas
from contracts.models import Contrato
from diets.models import Dieta


class PlanificacionDietaListView(ListView):
    """Vista para listar planificaciones de dietas"""
    model = PlanificacionDieta
    template_name = 'planning/planificacion_lista.html'
    context_object_name = 'planificaciones'
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
        
        # Filtrar por contrato si se proporciona
        contrato_id = self.request.GET.get('contrato')
        if contrato_id:
            queryset = queryset.filter(contrato_id=contrato_id)
        
        return queryset.order_by('-fecha', 'contrato')


class PlanificacionDietaCreateView(CreateView):
    """Vista para crear una nueva planificación de dieta"""
    model = PlanificacionDieta
    template_name = 'planning/planificacion_form.html'
    fields = ['fecha', 'contrato', 'dieta', 'estado', 'notas']
    success_url = reverse_lazy('planning:lista')

    def form_valid(self, form):
        # Obtener sugerencias de recetas alternativas antes de guardar
        planificacion = form.save(commit=False)
        
        # Verificar si hay ingredientes que no le gustan al cliente
        recetas_alternativas = sugerir_recetas_alternativas(
            planificacion.dieta.id,
            planificacion.contrato.cliente.id
        )
        
        if recetas_alternativas:
            planificacion.recetas_alternativas = recetas_alternativas
            messages.warning(
                self.request,
                f'Se encontraron recetas con ingredientes que no le gustan al cliente. '
                f'Se sugieren {len(recetas_alternativas)} recetas alternativas.'
            )
        
        planificacion.save()
        messages.success(self.request, 'Planificación creada exitosamente.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['contratos'] = Contrato.objects.filter(estado='activo')
        context['dietas'] = Dieta.objects.filter(activa=True)
        return context


class PlanificacionDietaUpdateView(UpdateView):
    """Vista para actualizar una planificación de dieta"""
    model = PlanificacionDieta
    template_name = 'planning/planificacion_form.html'
    fields = ['fecha', 'contrato', 'dieta', 'estado', 'notas']
    success_url = reverse_lazy('planning:lista')

    def form_valid(self, form):
        # Actualizar sugerencias de recetas alternativas
        planificacion = form.save(commit=False)
        
        recetas_alternativas = sugerir_recetas_alternativas(
            planificacion.dieta.id,
            planificacion.contrato.cliente.id
        )
        
        if recetas_alternativas:
            planificacion.recetas_alternativas = recetas_alternativas
            messages.warning(
                self.request,
                f'Se encontraron recetas con ingredientes que no le gustan al cliente. '
                f'Se sugieren {len(recetas_alternativas)} recetas alternativas.'
            )
        else:
            planificacion.recetas_alternativas = []
        
        planificacion.save()
        messages.success(self.request, 'Planificación actualizada exitosamente.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['contratos'] = Contrato.objects.filter(estado='activo')
        context['dietas'] = Dieta.objects.filter(activa=True)
        return context


class PlanificacionDietaDeleteView(DeleteView):
    """Vista para eliminar una planificación de dieta"""
    model = PlanificacionDieta
    template_name = 'planning/planificacion_confirm_delete.html'
    success_url = reverse_lazy('planning:lista')

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Planificación eliminada exitosamente.')
        return super().delete(request, *args, **kwargs)


def calendario_planificacion(request, year=None, month=None):
    """Vista para mostrar calendario de planificaciones"""
    if year and month:
        try:
            fecha = date(int(year), int(month), 1)
        except ValueError:
            fecha = timezone.now().date().replace(day=1)
    else:
        fecha = timezone.now().date().replace(day=1)
    
    # Calcular primer y último día del mes
    if fecha.month == 12:
        siguiente_mes = fecha.replace(year=fecha.year + 1, month=1)
    else:
        siguiente_mes = fecha.replace(month=fecha.month + 1)
    
    ultimo_dia = (siguiente_mes - timedelta(days=1)).day
    
    # Obtener planificaciones del mes
    planificaciones = PlanificacionDieta.objects.filter(
        fecha__year=fecha.year,
        fecha__month=fecha.month
    )
    
    # Crear diccionario de planificaciones por día para el template
    planificaciones_por_dia = {}
    for planificacion in planificaciones:
        dia = planificacion.fecha.day
        if dia not in planificaciones_por_dia:
            planificaciones_por_dia[dia] = []
        planificaciones_por_dia[dia].append(planificacion)
    
    # Calcular mes anterior y siguiente
    if fecha.month == 1:
        mes_anterior = fecha.replace(year=fecha.year - 1, month=12)
    else:
        mes_anterior = fecha.replace(month=fecha.month - 1)
    
    context = {
        'fecha': fecha,
        'mes_anterior': mes_anterior,
        'mes_siguiente': siguiente_mes,
        'ultimo_dia': ultimo_dia,
        'planificaciones_por_dia': planificaciones_por_dia,
    }
    
    return render(request, 'planning/calendario.html', context)

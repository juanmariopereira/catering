from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.forms import inlineformset_factory
from django.utils import timezone
from django.db.models import Max
from datetime import date
from routes.models import Ruta, RutaCliente, Entregador
from contracts.models import Contrato, q_filtro_estado, contratos_activos_en_fecha
from .forms import RutaForm


BaseRutaClienteFormSet = inlineformset_factory(
    Ruta,
    RutaCliente,
    fields=['contrato', 'orden_entrega'],
    extra=1,
    can_delete=True,
)


class RutaClienteFormSet(BaseRutaClienteFormSet):
    """
    Formset que limita el select de contratos a: activos en la fecha de la ruta,
    que no estén asignados a otro entregador ese día, más los ya en esta ruta.
    """
    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance')
        if instance and instance.pk and getattr(instance, 'fecha', None):
            fecha = instance.fecha
            activos = contratos_activos_en_fecha(fecha).select_related('cliente', 'plan')
            # Contratos asignados a otra ruta (otro entregador) en la misma fecha
            ya_otra_ruta = set(
                RutaCliente.objects.filter(ruta__fecha=fecha)
                .exclude(ruta_id=instance.pk)
                .values_list('contrato_id', flat=True)
            )
            qs = activos.exclude(pk__in=ya_otra_ruta).order_by('cliente__nombre')
            self.form.base_fields['contrato'].queryset = qs
        super().__init__(*args, **kwargs)


class RutaListView(LoginRequiredMixin, ListView):
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


class RutaCreateView(LoginRequiredMixin, CreateView):
    """Vista para crear una ruta (luego se edita para agregar clientes)."""
    model = Ruta
    form_class = RutaForm
    template_name = 'delivery/ruta_form.html'
    context_object_name = 'ruta'

    def get_success_url(self):
        return reverse('delivery:ruta_editar', args=[self.object.pk])

    def form_valid(self, form):
        messages.success(self.request, 'Ruta creada. Agregue los clientes a continuación.')
        return super().form_valid(form)


class RutaUpdateView(LoginRequiredMixin, UpdateView):
    """Vista para editar ruta y sus clientes (orden de entrega)."""
    model = Ruta
    form_class = RutaForm
    template_name = 'delivery/ruta_form.html'
    context_object_name = 'ruta'

    def get_success_url(self):
        return reverse('delivery:lista')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['formset'] = RutaClienteFormSet(
                self.request.POST, instance=self.object
            )
        else:
            context['formset'] = RutaClienteFormSet(instance=self.object)
        return context

    def form_valid(self, form):
        self.object = form.save()
        formset = RutaClienteFormSet(self.request.POST, instance=self.object)
        if formset.is_valid():
            formset.save()
            messages.success(self.request, 'Ruta y clientes guardados correctamente.')
            return redirect(self.get_success_url())
        return self.render_to_response(
            self.get_context_data(form=form, formset=formset)
        )


class RutaDeleteView(LoginRequiredMixin, DeleteView):
    model = Ruta
    template_name = 'delivery/ruta_confirm_delete.html'
    context_object_name = 'ruta'
    success_url = reverse_lazy('delivery:lista')

    def form_valid(self, form):
        messages.success(self.request, 'Ruta eliminada.')
        return super().form_valid(form)


@login_required
def ruta_cargar_ultima(request, pk):
    """
    Añade a la ruta actual los contratos que este entregador llevó en su última ruta
    (solo los que siguen activos). Redirige a la edición de la ruta.
    """
    ruta = get_object_or_404(Ruta, pk=pk)
    # Última ruta del mismo entregador (excluyendo la actual)
    ultima_ruta = (
        Ruta.objects.filter(entregador=ruta.entregador)
        .exclude(pk=ruta.pk)
        .order_by('-fecha')
        .first()
    )
    if not ultima_ruta:
        messages.info(request, 'Este entregador no tiene otra ruta anterior. No hay clientes que cargar.')
        return redirect('delivery:ruta_editar', pk=ruta.pk)
    # Contratos de esa ruta, en orden
    ruta_clientes_ultima = ultima_ruta.ruta_clientes.all().order_by('orden_entrega')
    contrato_ids_ultima = [rc.contrato_id for rc in ruta_clientes_ultima]
    if not contrato_ids_ultima:
        messages.info(request, 'La última ruta de este entregador no tenía clientes.')
        return redirect('delivery:ruta_editar', pk=ruta.pk)
    # Solo contratos activos
    contratos_activos = Contrato.objects.filter(pk__in=contrato_ids_ultima).filter(
        q_filtro_estado('activo')
    )
    contratos_activos_ids = set(contratos_activos.values_list('pk', flat=True))
    # Orden igual que en la última ruta, pero solo los activos
    ya_en_ruta = set(
        ruta.ruta_clientes.values_list('contrato_id', flat=True)
    )
    max_orden = ruta.ruta_clientes.aggregate(m=Max('orden_entrega'))['m'] or 0
    creados = 0
    for rc in ruta_clientes_ultima:
        if rc.contrato_id not in contratos_activos_ids or rc.contrato_id in ya_en_ruta:
            continue
        max_orden += 1
        RutaCliente.objects.create(
            ruta=ruta,
            contrato_id=rc.contrato_id,
            orden_entrega=max_orden,
        )
        ya_en_ruta.add(rc.contrato_id)
        creados += 1
    if creados:
        messages.success(
            request,
            f'Se añadieron {creados} cliente(s) de la última ruta de {ruta.entregador.nombre} (solo activos).',
        )
    else:
        messages.info(
            request,
            'No se añadió ninguno: ya estaban en la ruta o ya no están activos.',
        )
    return redirect('delivery:ruta_editar', pk=ruta.pk)


@login_required
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


@login_required
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

    from base.models import es_feriado, get_feriado
    context = {
        'ruta': ruta,
        'entregador': entregador,
        'fecha': fecha,
        'ruta_clientes': ruta_clientes,
        'es_feriado': es_feriado(fecha),
        'feriado': get_feriado(fecha),
    }
    
    return render(request, 'delivery/ruta_imprimible.html', context)

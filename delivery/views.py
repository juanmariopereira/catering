from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.forms import inlineformset_factory
from django.utils import timezone
from datetime import date
from routes.models import Ruta, RutaCliente, Entregador


RutaClienteFormSet = inlineformset_factory(
    Ruta,
    RutaCliente,
    fields=['contrato', 'orden_entrega'],
    extra=5,
    can_delete=True,
)


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
    template_name = 'delivery/ruta_form.html'
    fields = ['fecha', 'entregador', 'activa', 'notas']
    context_object_name = 'ruta'

    def get_success_url(self):
        return reverse('delivery:ruta_editar', args=[self.object.pk])

    def form_valid(self, form):
        messages.success(self.request, 'Ruta creada. Agregue los clientes a continuación.')
        return super().form_valid(form)


class RutaUpdateView(LoginRequiredMixin, UpdateView):
    """Vista para editar ruta y sus clientes (orden de entrega)."""
    model = Ruta
    template_name = 'delivery/ruta_form.html'
    fields = ['fecha', 'entregador', 'activa', 'notas']
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

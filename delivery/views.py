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
from .utils import (
    contratos_con_entrega_en_fecha,
    contratos_sin_ruta_en_fecha,
)


BaseRutaClienteFormSet = inlineformset_factory(
    Ruta,
    RutaCliente,
    fields=['contrato', 'orden_entrega'],
    extra=0,
    can_delete=True,
)


class RutaClienteFormSet(BaseRutaClienteFormSet):
    """
    Formset que limita el select de contratos a: activos en la fecha con entrega ese día,
    que no estén asignados a otro entregador ese día, más los ya en esta ruta.
    Usa contratos_con_entrega_en_fecha para reducir el tamaño del queryset (solo los que tienen entrega ese día).
    """
    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance')
        if instance and instance.pk and getattr(instance, 'fecha', None):
            fecha = instance.fecha
            # Contratos que ya están en esta ruta (siempre opciones válidas para no romper filas existentes)
            ids_en_esta_ruta = set(
                instance.ruta_clientes.values_list('contrato_id', flat=True)
            )
            # Solo contratos con entrega ese día (menos filas que contratos_activos_en_fecha)
            activos = contratos_con_entrega_en_fecha(fecha).select_related('cliente', 'plan')
            # Contratos asignados a otra ruta (otro entregador) en la misma fecha
            ya_otra_ruta = set(
                RutaCliente.objects.filter(ruta__fecha=fecha)
                .exclude(ruta_id=instance.pk)
                .values_list('contrato_id', flat=True)
            )
            disponibles = activos.exclude(pk__in=ya_otra_ruta)
            # Incluir siempre los que ya están en esta ruta para que no salga "obligatorio" / invalid choice
            if ids_en_esta_ruta:
                ya_en_ruta = Contrato.objects.filter(pk__in=ids_en_esta_ruta).select_related('cliente', 'plan')
                disponibles = (disponibles | ya_en_ruta).distinct()
            qs = disponibles.order_by('cliente__nombre')
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
        fecha_param = self.request.GET.get('fecha')
        fecha = timezone.now().date()
        if fecha_param:
            try:
                fecha = date.fromisoformat(fecha_param)
            except ValueError:
                pass
        queryset = queryset.filter(fecha=fecha)

        entregador_id = self.request.GET.get('entregador')
        if entregador_id:
            queryset = queryset.filter(entregador_id=entregador_id)

        return queryset.order_by('-fecha', 'entregador')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['entregadores'] = Entregador.objects.filter(activo=True).order_by('nombre')
        fecha_param = self.request.GET.get('fecha')
        fecha = timezone.now().date()
        if fecha_param:
            try:
                fecha = date.fromisoformat(fecha_param)
            except ValueError:
                pass
        sin_ruta = list(contratos_sin_ruta_en_fecha(fecha))
        con_entrega = contratos_con_entrega_en_fecha(fecha).count()
        context['fecha_seleccionada'] = fecha
        context['contratos_sin_ruta'] = sin_ruta
        context['total_con_entrega'] = con_entrega
        context['cantidad_sin_ruta'] = len(sin_ruta)
        context['cantidad_con_ruta'] = con_entrega - len(sin_ruta)
        return context


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

    def get_queryset(self):
        return Ruta.objects.select_related('entregador').prefetch_related('ruta_clientes')

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


def _get_or_create_ruta(fecha, entregador):
    """Obtiene o crea la ruta para fecha + entregador."""
    ruta, _ = Ruta.objects.get_or_create(
        fecha=fecha,
        entregador=entregador,
        defaults={'activa': True},
    )
    return ruta


def _asignar_contratos_a_rutas(fecha, contratos_ids, rutas):
    """
    Asigna los contratos (por id) a las rutas existentes, repartiendo en round-robin.
    rutas: lista de Ruta para esa fecha (orden estable).
    Modifica la BD; devuelve cuántos se asignaron.
    """
    if not rutas or not contratos_ids:
        return 0
    ya_asignados = set(
        RutaCliente.objects.filter(ruta__fecha=fecha).values_list('contrato_id', flat=True)
    )
    pendientes = [cid for cid in contratos_ids if cid not in ya_asignados]
    if not pendientes:
        return 0
    # Orden de rutas por (cantidad actual ascendente) para equilibrar
    counts = {r.id: r.ruta_clientes.count() for r in rutas}
    orden_rutas = sorted(rutas, key=lambda r: (counts[r.id], r.entregador.nombre))
    asignados = 0
    for i, contrato_id in enumerate(pendientes):
        ruta = orden_rutas[i % len(orden_rutas)]
        max_orden = ruta.ruta_clientes.aggregate(m=Max('orden_entrega'))['m'] or 0
        RutaCliente.objects.create(
            ruta=ruta,
            contrato_id=contrato_id,
            orden_entrega=max_orden + 1,
        )
        asignados += 1
    return asignados


@login_required
def generar_rutas(request):
    """
    Genera rutas para una fecha a partir de la configuración de una fecha anterior
    (mismo entregador → mismos contratos que sigan activos y con entrega ese día).
    Si hay contratos sin asignar (nuevos o que no estaban en la fecha origen),
    se reparten entre las rutas existentes.
    """
    if request.method != 'POST':
        # GET: formulario con fecha y opcional fecha_origen
        return render(request, 'delivery/generar_rutas_form.html', {
            'entregadores': Entregador.objects.filter(activo=True).order_by('nombre'),
        })

    fecha_str = request.POST.get('fecha')
    fecha_origen_str = request.POST.get('fecha_origen') or ''
    if not fecha_str:
        messages.error(request, 'Indica la fecha para la que generar las rutas.')
        return redirect('delivery:generar_rutas')

    try:
        fecha = date.fromisoformat(fecha_str)
    except ValueError:
        messages.error(request, 'Fecha inválida.')
        return redirect('delivery:generar_rutas')

    fecha_origen = None
    if fecha_origen_str:
        try:
            fecha_origen = date.fromisoformat(fecha_origen_str)
        except ValueError:
            pass

    entregadores_activos = list(Entregador.objects.filter(activo=True).order_by('nombre'))
    if not entregadores_activos:
        messages.warning(request, 'No hay entregadores activos.')
        return redirect('delivery:lista')

    # 1) Si hay fecha origen: copiar estructura (ruta por entregador, mismos contratos que apliquen)
    if fecha_origen:
        rutas_origen = list(Ruta.objects.filter(fecha=fecha_origen).select_related('entregador'))
        for ruta_orig in rutas_origen:
            ruta = _get_or_create_ruta(fecha, ruta_orig.entregador)
            for rc in ruta_orig.ruta_clientes.all().order_by('orden_entrega'):
                contrato = rc.contrato
                if not contrato.activo_en_fecha(fecha):
                    continue
                dia_semana = ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo'][fecha.weekday()]
                if not contrato.dias_entrega or dia_semana not in contrato.dias_entrega:
                    continue
                if ruta.ruta_clientes.filter(contrato_id=rc.contrato_id).exists():
                    continue
                max_orden = ruta.ruta_clientes.aggregate(m=Max('orden_entrega'))['m'] or 0
                RutaCliente.objects.create(
                    ruta=ruta,
                    contrato_id=rc.contrato_id,
                    orden_entrega=max_orden + 1,
                )

    # 2) Asegurar al menos una ruta por entregador activo para esa fecha
    rutas_fecha = []
    for e in entregadores_activos:
        r = _get_or_create_ruta(fecha, e)
        rutas_fecha.append(r)

    # 3) Contratos con entrega ese día que aún no están en ninguna ruta
    sin_ruta = contratos_sin_ruta_en_fecha(fecha)
    ids_sin_ruta = list(sin_ruta.values_list('pk', flat=True))
    asignados = _asignar_contratos_a_rutas(fecha, ids_sin_ruta, rutas_fecha)

    if asignados > 0:
        messages.success(
            request,
            f'Rutas generadas para el {fecha.strftime("%d/%m/%Y")}. '
            f'Se asignaron {asignados} contrato(s) que no tenían ruta.',
        )
    elif fecha_origen:
        messages.success(
            request,
            f'Rutas generadas para el {fecha.strftime("%d/%m/%Y")}. '
            'Todos los contratos con entrega ya estaban asignados.',
        )
    else:
        messages.success(
            request,
            f'Rutas generadas para el {fecha.strftime("%d/%m/%Y")}. '
            'Se creó una ruta por entregador; asigna clientes desde la lista o edita cada ruta.',
        )
    return redirect(reverse('delivery:lista') + '?fecha=' + fecha_str)


@login_required
def asignar_pendientes(request):
    """
    Asigna a rutas los contratos que tienen entrega en la fecha pero no están en ninguna ruta
    (p. ej. contratos nuevos cuando las rutas ya existían). Reparte entre las rutas existentes
    o crea una por entregador si no hay ninguna.
    """
    if request.method != 'POST':
        messages.error(request, 'Acción no permitida.')
        return redirect('delivery:lista')

    fecha_str = request.POST.get('fecha')
    if not fecha_str:
        messages.error(request, 'Falta la fecha.')
        return redirect('delivery:lista')

    try:
        fecha = date.fromisoformat(fecha_str)
    except ValueError:
        messages.error(request, 'Fecha inválida.')
        return redirect('delivery:lista')

    sin_ruta = list(contratos_sin_ruta_en_fecha(fecha))
    if not sin_ruta:
        messages.info(request, 'No hay contratos pendientes de asignar para esa fecha.')
        return redirect(reverse('delivery:lista') + '?fecha=' + fecha_str)

    rutas_fecha = list(Ruta.objects.filter(fecha=fecha).select_related('entregador'))
    if not rutas_fecha:
        # Crear una ruta por entregador activo y repartir
        for e in Entregador.objects.filter(activo=True).order_by('nombre'):
            rutas_fecha.append(_get_or_create_ruta(fecha, e))

    ids_sin_ruta = [c.id for c in sin_ruta]
    asignados = _asignar_contratos_a_rutas(fecha, ids_sin_ruta, rutas_fecha)

    messages.success(
        request,
        f'Se asignaron {asignados} contrato(s) pendientes a las rutas del {fecha.strftime("%d/%m/%Y")}.',
    )
    return redirect(reverse('delivery:lista') + '?fecha=' + fecha_str)


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

from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.forms import inlineformset_factory
from django.utils import timezone
from django.db.models import Case, IntegerField, Max, Value, When, Q
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from datetime import date, timedelta
from routes.models import Ruta, RutaCliente, Entregador
from contracts.models import Contrato, q_filtro_estado, contratos_activos_en_fecha
from .forms import RutaForm, PuntoPartidaEntregaForm
from .models import PuntoPartidaEntrega
from .utils import (
    contratos_con_entrega_en_fecha,
    contratos_sin_ruta_en_fecha,
)
from .services.google_maps_ruta import optimizar_orden_entregas, get_geometria_ruta_calles


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
                ids_disponibles = set(disponibles.values_list('pk', flat=True))
                todos_los_ids = ids_disponibles | ids_en_esta_ruta
                qs = Contrato.objects.filter(pk__in=todos_los_ids).select_related('cliente', 'plan')
            else:
                qs = disponibles
            # Primero los que no tienen ruta asignada, luego por nombre de cliente
            ids_sin_ruta = set(
                contratos_sin_ruta_en_fecha(fecha).values_list('pk', flat=True)
            )
            qs = qs.annotate(
                sin_ruta=Case(
                    When(pk__in=ids_sin_ruta, then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            ).order_by('-sin_ruta', 'cliente__nombre')
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
        # Contratos sin coordenadas (para mostrar aviso en cada fila del formset)
        if self.object and self.object.pk and getattr(self.object, 'fecha', None):
            ids_en_ruta = set(
                self.object.ruta_clientes.values_list('contrato_id', flat=True)
            )
            ids_disponibles = set(
                contratos_con_entrega_en_fecha(self.object.fecha).values_list('pk', flat=True)
            )
            contract_ids = ids_en_ruta | ids_disponibles
            context['contratos_sin_coordenadas'] = set(
                Contrato.objects.filter(pk__in=contract_ids).filter(
                    Q(latitud__isnull=True) | Q(longitud__isnull=True)
                ).values_list('pk', flat=True)
            )
        else:
            context['contratos_sin_coordenadas'] = set()
        return context

    def form_valid(self, form):
        self.object = form.save()
        formset = RutaClienteFormSet(self.request.POST, instance=self.object)
        if formset.is_valid():
            formset.save()
            # Optimizar orden de entrega con Google Maps (solo rutas presente/futuras)
            hoy = timezone.now().date()
            res = {}
            if self.object.fecha >= hoy:
                res = optimizar_orden_entregas(self.object, request=self.request)
            else:
                res = {'optimizados': 0, 'sin_coordenadas': 0}
            messages.success(self.request, 'Ruta y clientes guardados correctamente.')
            if res.get('optimizados', 0) > 0:
                messages.success(
                    self.request,
                    f"Se optimizó el orden de {res['optimizados']} entrega(s) según Google Maps.",
                )
            if res.get('sin_coordenadas', 0) > 0:
                messages.warning(
                    self.request,
                    f"{res['sin_coordenadas']} cliente(s) sin coordenadas: no se pudo definir un orden óptimo para ellos (aparecen al final de la ruta).",
                )
            if res.get('error') and res.get('optimizados') == 0 and res.get('sin_coordenadas', 0) == 0:
                messages.warning(
                    self.request,
                    f"No se pudo optimizar la ruta con Google Maps: {res['error']}.",
                )
            elif res.get('error') and (res.get('optimizados', 0) > 0 or res.get('sin_coordenadas', 0) > 0):
                messages.warning(
                    self.request,
                    f"Optimización parcial. Aviso de Google Maps: {res['error']}.",
                )
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
        # GET: formulario con fecha (mañana) y fecha_origen (última fecha con rutas)
        manana = timezone.now().date() + timedelta(days=1)
        ultima_ruta = Ruta.objects.order_by('-fecha').values_list('fecha', flat=True).first()
        return render(request, 'delivery/generar_rutas_form.html', {
            'entregadores': Entregador.objects.filter(activo=True).order_by('nombre'),
            'fecha_default': manana.isoformat(),
            'fecha_origen_default': ultima_ruta.isoformat() if ultima_ruta else '',
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
    hoy = timezone.now().date()
    if fecha >= hoy:
        for ruta in rutas_fecha:
            optimizar_orden_entregas(ruta, request=request)
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

    hoy = timezone.now().date()
    if fecha >= hoy:
        for ruta in rutas_fecha:
            optimizar_orden_entregas(ruta, request=request)

    messages.success(
        request,
        f'Se asignaron {asignados} contrato(s) pendientes a las rutas del {fecha.strftime("%d/%m/%Y")}.',
    )
    return redirect(reverse('delivery:lista') + '?fecha=' + fecha_str)


@login_required
def distribuir_entregas(request):
    """
    Interfaz alternativa para distribuir puntos de entrega por entregador de forma visual.
    Muestra todos los contratos con entrega en la fecha seleccionada; el usuario asigna
    cada punto a un entregador (o deja sin asignar). No modifica el flujo existente
    (generar rutas / asignar pendientes); solo crea/actualiza Ruta y RutaCliente.
    """
    entregadores = list(Entregador.objects.filter(activo=True).order_by('nombre'))
    fecha_param = request.GET.get('fecha') or request.POST.get('fecha')
    fecha = timezone.now().date()
    if fecha_param:
        try:
            fecha = date.fromisoformat(fecha_param)
        except ValueError:
            pass

    # GET sin fecha: redirigir con ?fecha=hoy para que el botón "Ver puntos" tenga efecto visible
    if request.method == 'GET' and not request.GET.get('fecha'):
        return redirect(reverse('delivery:distribuir_entregas') + f'?fecha={fecha.isoformat()}')

    # Contratos con entrega en la fecha (vigentes ese día)
    contratos = list(
        contratos_con_entrega_en_fecha(fecha)
        .select_related('cliente', 'plan')
        .order_by('cliente__nombre')
    )
    # Asignación actual: contrato_id -> entregador_id (o None)
    asignacion_actual = {}
    if contratos:
        ids_contratos = [c.id for c in contratos]
        for rc in RutaCliente.objects.filter(
            ruta__fecha=fecha,
            contrato_id__in=ids_contratos,
        ).select_related('ruta'):
            asignacion_actual[rc.contrato_id] = rc.ruta.entregador_id

    if request.method == 'POST':
        # Guardar distribución: entregador_<contrato_id> para cada contrato
        actualizados = 0
        for c in contratos:
            key = f'entregador_{c.id}'
            entregador_id_raw = request.POST.get(key, '').strip()
            entregador_id = int(entregador_id_raw) if entregador_id_raw and entregador_id_raw.isdigit() else None
            actual = asignacion_actual.get(c.id)

            if actual == entregador_id:
                continue

            # Quitar de la ruta actual si estaba asignado
            RutaCliente.objects.filter(ruta__fecha=fecha, contrato_id=c.id).delete()

            if entregador_id:
                ruta = _get_or_create_ruta(fecha, Entregador.objects.get(pk=entregador_id))
                max_orden = ruta.ruta_clientes.aggregate(m=Max('orden_entrega'))['m'] or 0
                RutaCliente.objects.create(
                    ruta=ruta,
                    contrato_id=c.id,
                    orden_entrega=max_orden + 1,
                )
                actualizados += 1
            else:
                actualizados += 1

        if actualizados > 0:
            messages.success(
                request,
                f'Distribución guardada para el {fecha.strftime("%d/%m/%Y")}. '
                'Puedes ver las rutas en la lista de entregas.',
            )
        return redirect(reverse('delivery:distribuir_entregas') + f'?fecha={fecha.isoformat()}')

    fecha_str = fecha.isoformat()
    # Puntos con coordenadas para el mapa (lat/lng obligatorios)
    puntos_mapa = []
    for c in contratos:
        if c.latitud is not None and c.longitud is not None:
            puntos_mapa.append({
                'id': c.id,
                'lat': float(c.latitud),
                'lng': float(c.longitud),
                'cliente': c.cliente.nombre,
                'plan': c.plan.nombre,
                'direccion': (c.direccion_entrega or '')[:200],
                'entregador_actual_id': asignacion_actual.get(c.id),
            })
    entregadores_json = [{'id': e.id, 'nombre': e.nombre} for e in entregadores]
    contratos_json = [{'id': c.id, 'cliente': c.cliente.nombre, 'plan': c.plan.nombre} for c in contratos]
    return render(request, 'delivery/distribuir_entregas.html', {
        'fecha_seleccionada': fecha,
        'fecha_str': fecha_str,
        'contratos': contratos,
        'asignacion_actual': asignacion_actual,
        'entregadores': entregadores,
        'puntos_mapa': puntos_mapa,
        'entregadores_json': entregadores_json,
        'contratos_json': contratos_json,
    })


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
    hoy = timezone.now().date()
    if ruta.fecha >= hoy:
        optimizar_orden_entregas(ruta, request=request)
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
def punto_partida_config(request):
    """
    Configuración del punto de partida para optimización de rutas (cocina/depósito).
    Usa el primer registro activo o crea uno si no existe.
    """
    punto = PuntoPartidaEntrega.objects.filter(activo=True).order_by('-fecha_actualizacion').first()
    if punto is None:
        punto = PuntoPartidaEntrega.objects.order_by('-fecha_actualizacion').first()
    if request.method == 'POST':
        form = PuntoPartidaEntregaForm(request.POST, instance=punto)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                'Punto de partida guardado. El algoritmo de optimización de rutas lo usará como origen y destino.',
            )
            return redirect('delivery:lista')
    else:
        form = PuntoPartidaEntregaForm(instance=punto)
    return render(request, 'delivery/punto_partida_form.html', {
        'form': form,
        'punto': punto,
    })


def _formatear_tiempo_estimado(segundos):
    """Convierte segundos a texto: 'X min' o 'Xh Y min'."""
    if segundos is None or segundos < 0:
        return None
    if segundos < 3600:
        return f'{int(round(segundos / 60))} min'
    h = int(segundos // 3600)
    m = int(round((segundos % 3600) / 60))
    if m == 0:
        return f'{h}h'
    return f'{h}h {m} min'


def _datos_recorrido_ruta(ruta, ruta_clientes):
    """
    Construye los datos para mostrar el recorrido en un mapa: puntos en orden
    (punto de partida si existe, luego cada parada con coordenadas).
    Devuelve un dict con 'puntos' (lista de {lat, lng, label}) y 'tiene_punto_partida'.
    """
    from .models import PuntoPartidaEntrega
    puntos = []
    punto_partida = PuntoPartidaEntrega.objects.filter(activo=True).order_by('-fecha_actualizacion').first()
    if punto_partida and punto_partida.latitud is not None and punto_partida.longitud is not None:
        puntos.append({
            'lat': float(punto_partida.latitud),
            'lng': float(punto_partida.longitud),
            'label': punto_partida.nombre or 'Salida',
        })
    for rc in ruta_clientes:
        c = rc.contrato
        if c.latitud is not None and c.longitud is not None:
            puntos.append({
                'lat': float(c.latitud),
                'lng': float(c.longitud),
                'label': f"#{rc.orden_entrega} {rc.codigo_entrega}",
            })
    mapa = {
        'puntos': puntos,
        'tiene_punto_partida': bool(punto_partida and punto_partida.latitud is not None and punto_partida.longitud is not None),
    }
    if len(puntos) >= 2:
        polylines_calles = get_geometria_ruta_calles(puntos)
        if polylines_calles:
            mapa['polylines_calles'] = polylines_calles
    return mapa


def _tiempos_estimados_ruta(ruta, ruta_clientes):
    """
    Calcula tiempo estimado de llegada por punto (1 min espera por punto)
    y total estimado. Devuelve (clientes_con_tiempo, total_str).
    clientes_con_tiempo: lista de (ruta_cliente, tiempo_llegada_str o None)
    """
    legs = getattr(ruta, 'duracion_legs_segundos', None) or []
    n = len(ruta_clientes)
    clientes_con_tiempo = []
    total_estimado_seg = None
    if legs and n > 0:
        # legs[0] = hasta 1er punto, legs[1] = hasta 2do, ... Tiempo llegada punto i = sum(legs[0:i+1]) + i*60
        for i, rc in enumerate(ruta_clientes):
            if i < len(legs):
                acum = sum(legs[: i + 1]) + i * 60  # i min espera en los i puntos anteriores
                clientes_con_tiempo.append((rc, _formatear_tiempo_estimado(acum)))
            else:
                clientes_con_tiempo.append((rc, None))
        total_estimado_seg = sum(legs) + n * 60
    else:
        clientes_con_tiempo = [(rc, None) for rc in ruta_clientes]
    total_str = _formatear_tiempo_estimado(total_estimado_seg) if total_estimado_seg is not None else None
    return clientes_con_tiempo, total_str


@login_required
@require_POST
def ruta_cliente_marcar_entregada(request, pk):
    """
    Marca un RutaCliente como entregado (AJAX). Requiere confirmación en el cliente.
    """
    rc = get_object_or_404(RutaCliente, pk=pk)
    rc.entregada = True
    rc.fecha_entrega = timezone.now()
    rc.marcadopor_entregada = request.user
    rc.no_entregada = False
    rc.motivo_no_entrega = ''
    rc.fecha_no_entrega = None
    rc.marcadopor_no_entrega = None
    rc.save(update_fields=[
        'entregada', 'fecha_entrega', 'marcadopor_entregada',
        'no_entregada', 'motivo_no_entrega', 'fecha_no_entrega', 'marcadopor_no_entrega',
    ])
    nombre_usuario = (request.user.get_full_name().strip() or request.user.username) if request.user else ''
    return JsonResponse({
        'ok': True,
        'fecha_entrega': rc.fecha_entrega.isoformat() if rc.fecha_entrega else None,
        'marcado_por': nombre_usuario,
    })


@login_required
@require_POST
def ruta_cliente_reportar_no_entrega(request, pk):
    """
    Reporta que no se pudo realizar la entrega (AJAX). Requiere motivo en el body (JSON).
    """
    import json
    rc = get_object_or_404(RutaCliente, pk=pk)
    try:
        body = json.loads(request.body.decode('utf-8')) if request.body else {}
    except (ValueError, TypeError):
        body = {}
    motivo = (body.get('motivo') or '').strip()
    if not motivo:
        return JsonResponse({'ok': False, 'error': 'El motivo es obligatorio.'}, status=400)
    rc.no_entregada = True
    rc.motivo_no_entrega = motivo[:2000]
    rc.fecha_no_entrega = timezone.now()
    rc.marcadopor_no_entrega = request.user
    rc.entregada = False
    rc.fecha_entrega = None
    rc.marcadopor_entregada = None
    rc.save(update_fields=[
        'no_entregada', 'motivo_no_entrega', 'fecha_no_entrega', 'marcadopor_no_entrega',
        'entregada', 'fecha_entrega', 'marcadopor_entregada',
    ])
    nombre_usuario = (request.user.get_full_name().strip() or request.user.username) if request.user else ''
    return JsonResponse({
        'ok': True,
        'marcado_por': nombre_usuario,
        'fecha_no_entrega': rc.fecha_no_entrega.isoformat() if rc.fecha_no_entrega else None,
    })


@login_required
@require_POST
def ruta_recalcular_recorrido(request, ruta_id):
    """
    Recalcula el orden de entregas de la ruta (optimización con punto de partida)
    y devuelve los nuevos datos del recorrido para actualizar el mapa en el modal.
    """
    ruta = get_object_or_404(
        Ruta.objects.prefetch_related('ruta_clientes__contrato'),
        id=ruta_id,
    )
    result = optimizar_orden_entregas(ruta, request=request)
    if result.get('error'):
        return JsonResponse({
            'ok': False,
            'error': result['error'],
        }, status=400)
    ruta_clientes = list(ruta.ruta_clientes.select_related('contrato__cliente').order_by('orden_entrega'))
    mapa_recorrido = _datos_recorrido_ruta(ruta, ruta_clientes)
    return JsonResponse({
        'ok': True,
        'mapa_recorrido': mapa_recorrido,
        'optimizados': result.get('optimizados', 0),
        'sin_coordenadas': result.get('sin_coordenadas', 0),
    })


@login_required
def ruta_imprimible(request, ruta_id):
    """
    Vista para mostrar una ruta de entrega en formato imprimible
    """
    ruta = get_object_or_404(
        Ruta.objects.prefetch_related(
            'ruta_clientes__contrato__cliente',
            'ruta_clientes__marcadopor_entregada',
            'ruta_clientes__marcadopor_no_entrega',
        ),
        id=ruta_id,
    )
    ruta_clientes = ruta.ruta_clientes.all().order_by('orden_entrega')
    clientes_con_tiempo, total_estimado_str = _tiempos_estimados_ruta(ruta, list(ruta_clientes))
    mapa_recorrido = _datos_recorrido_ruta(ruta, list(ruta_clientes))
    context = {
        'ruta': ruta,
        'ruta_clientes': ruta_clientes,
        'clientes_con_tiempo': clientes_con_tiempo,
        'total_estimado_str': total_estimado_str,
        'mapa_recorrido': mapa_recorrido,
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
    ruta_clientes = ruta.ruta_clientes.select_related(
        'marcadopor_entregada', 'marcadopor_no_entrega', 'contrato__cliente'
    ).order_by('orden_entrega')
    clientes_con_tiempo, total_estimado_str = _tiempos_estimados_ruta(ruta, list(ruta_clientes))
    mapa_recorrido = _datos_recorrido_ruta(ruta, list(ruta_clientes))

    from base.models import es_feriado, get_feriado
    context = {
        'ruta': ruta,
        'entregador': entregador,
        'fecha': fecha,
        'ruta_clientes': ruta_clientes,
        'clientes_con_tiempo': clientes_con_tiempo,
        'total_estimado_str': total_estimado_str,
        'mapa_recorrido': mapa_recorrido,
        'es_feriado': es_feriado(fecha),
        'feriado': get_feriado(fecha),
    }
    return render(request, 'delivery/ruta_imprimible.html', context)

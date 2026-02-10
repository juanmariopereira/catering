from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, TemplateView
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
from base.models import es_feriado
from base.auth_utils import get_user_home_url, is_entregador, user_can_access_entregador
from routes.models import (
    Ruta, RutaCliente, Entregador,
    PlantillaRuta, PlantillaRutaCliente, EntregaDia,
)
from contracts.models import Contrato, q_filtro_estado, contratos_activos_en_fecha
from .forms import PlantillaRutaForm, PlantillaRutaClienteForm
from .models import PuntoPartidaEntrega
from .utils import (
    contratos_con_entrega_en_fecha,
    contratos_sin_ruta_en_fecha,
    get_paradas_ruta_fecha,
    RutaClienteDia,
)
from .services.google_maps_ruta import optimizar_orden_entregas_plantilla, get_geometria_ruta_calles


BasePlantillaRutaClienteFormSet = inlineformset_factory(
    PlantillaRuta,
    PlantillaRutaCliente,
    form=PlantillaRutaClienteForm,
    extra=0,
    can_delete=True,
)


class PlantillaRutaClienteFormSet(BasePlantillaRutaClienteFormSet):
    """Formset para clientes de la plantilla; contrato puede ser cualquier contrato (no duplicado en otras plantillas)."""
    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance')
        if instance and instance.pk:
            # Contratos ya en esta plantilla
            ids_en_plantilla = set(
                instance.clientes.values_list('contrato_id', flat=True)
            )
            # Todos los contratos (o al menos los activos recientes) para elegir
            disponibles = Contrato.objects.select_related('cliente', 'plan').order_by('cliente__nombre')
            ids_sin_ruta = set(
                contratos_sin_ruta_en_fecha(timezone.now().date()).values_list('pk', flat=True)
            )
            disponibles = disponibles.annotate(
                sin_ruta=Case(
                    When(pk__in=ids_sin_ruta, then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            ).order_by('-sin_ruta', 'cliente__nombre')
            self.form.base_fields['contrato'].queryset = disponibles
        super().__init__(*args, **kwargs)


class RutaListView(LoginRequiredMixin, TemplateView):
    """Lista de rutas del día por entregador (paradas calculadas desde plantilla + fecha)."""
    template_name = 'delivery/ruta_lista.html'

    def dispatch(self, request, *args, **kwargs):
        if is_entregador(request.user):
            return redirect(get_user_home_url(request.user))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        fecha_param = self.request.GET.get('fecha')
        fecha = timezone.now().date()
        if fecha_param:
            try:
                fecha = date.fromisoformat(fecha_param)
            except ValueError:
                pass
        entregadores = list(Entregador.objects.filter(activo=True).order_by('nombre'))
        entregador_id = self.request.GET.get('entregador')
        if entregador_id:
            entregadores = [e for e in entregadores if e.pk == int(entregador_id)]
        rutas = []
        for e in entregadores:
            paradas = get_paradas_ruta_fecha(e, fecha)
            rutas.append({
                'entregador': e,
                'paradas': paradas,
                'cantidad': len(paradas),
                'fecha': fecha,
            })
        sin_ruta = list(contratos_sin_ruta_en_fecha(fecha))
        con_entrega = contratos_con_entrega_en_fecha(fecha).count()
        context['rutas'] = rutas
        context['entregadores'] = Entregador.objects.filter(activo=True).order_by('nombre')
        context['fecha_seleccionada'] = fecha
        context['contratos_sin_ruta'] = sin_ruta
        context['total_con_entrega'] = con_entrega
        context['cantidad_sin_ruta'] = len(sin_ruta)
        context['cantidad_con_ruta'] = con_entrega - len(sin_ruta)
        return context


def _get_or_create_plantilla(entregador):
    """Obtiene o crea la plantilla de ruta para un entregador."""
    plantilla, _ = PlantillaRuta.objects.get_or_create(
        entregador=entregador,
        defaults={'activa': True},
    )
    return plantilla


class PlantillaRutaUpdateView(LoginRequiredMixin, UpdateView):
    """Editar plantilla de ruta de un entregador (contratos y orden)."""
    model = PlantillaRuta
    form_class = PlantillaRutaForm
    template_name = 'delivery/plantilla_ruta_form.html'
    context_object_name = 'plantilla'

    def dispatch(self, request, *args, **kwargs):
        if is_entregador(request.user):
            return redirect(get_user_home_url(request.user))
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        entregador = get_object_or_404(Entregador, pk=self.kwargs['entregador_id'])
        return _get_or_create_plantilla(entregador)

    def get_success_url(self):
        return reverse('delivery:lista')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['formset'] = PlantillaRutaClienteFormSet(
                self.request.POST, instance=self.object
            )
        else:
            context['formset'] = PlantillaRutaClienteFormSet(instance=self.object)
        contract_ids = set(
            self.object.clientes.values_list('contrato_id', flat=True)
        )
        context['contratos_sin_coordenadas'] = set(
            Contrato.objects.filter(pk__in=contract_ids).filter(
                Q(latitud__isnull=True) | Q(longitud__isnull=True)
            ).values_list('pk', flat=True)
        ) if contract_ids else set()
        context['fecha_seleccionada'] = timezone.now().date()
        return context

    def form_valid(self, form):
        self.object = form.save()
        formset = PlantillaRutaClienteFormSet(self.request.POST, instance=self.object)
        if formset.is_valid():
            formset.save()
            messages.success(self.request, 'Plantilla de ruta guardada correctamente.')
            return redirect(self.get_success_url())
        return self.render_to_response(
            self.get_context_data(form=form, formset=formset)
        )


def _asignar_contratos_a_plantillas(contratos_ids, plantillas):
    """
    Asigna los contratos (por id) a las plantillas existentes, repartiendo en round-robin.
    Modifica la BD; devuelve cuántos se asignaron.
    """
    if not plantillas or not contratos_ids:
        return 0
    ya_asignados = set(
        PlantillaRutaCliente.objects.values_list('contrato_id', flat=True)
    )
    pendientes = [cid for cid in contratos_ids if cid not in ya_asignados]
    if not pendientes:
        return 0
    counts = {p.id: p.clientes.count() for p in plantillas}
    orden_plantillas = sorted(plantillas, key=lambda p: (counts[p.id], p.entregador.nombre))
    asignados = 0
    for i, contrato_id in enumerate(pendientes):
        plantilla = orden_plantillas[i % len(orden_plantillas)]
        max_orden = plantilla.clientes.aggregate(m=Max('orden_entrega'))['m'] or 0
        PlantillaRutaCliente.objects.get_or_create(
            plantilla_ruta=plantilla,
            contrato_id=contrato_id,
            defaults={'orden_entrega': max_orden + 1},
        )
        asignados += 1
    return asignados


@login_required
def asignar_pendientes(request):
    """
    Asigna a plantillas los contratos que tienen entrega pero no están en ninguna plantilla.
    Reparte en round-robin entre las plantillas existentes.
    """
    if is_entregador(request.user):
        return redirect(get_user_home_url(request.user))
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
        messages.info(request, 'No hay contratos pendientes de asignar.')
        return redirect(reverse('delivery:lista') + '?fecha=' + fecha_str)

    plantillas = []
    for e in Entregador.objects.filter(activo=True).order_by('nombre'):
        plantillas.append(_get_or_create_plantilla(e))
    if not plantillas:
        messages.warning(request, 'No hay entregadores activos.')
        return redirect(reverse('delivery:lista') + '?fecha=' + fecha_str)

    ids_sin_ruta = [c.id for c in sin_ruta]
    asignados = _asignar_contratos_a_plantillas(ids_sin_ruta, plantillas)

    messages.success(
        request,
        f'Se asignaron {asignados} contrato(s) pendientes a las plantillas.',
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
    if is_entregador(request.user):
        return redirect(get_user_home_url(request.user))
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
    # Asignación actual: contrato_id -> entregador_id (desde plantillas)
    asignacion_actual = {}
    if contratos:
        ids_contratos = [c.id for c in contratos]
        for prc in PlantillaRutaCliente.objects.filter(
            contrato_id__in=ids_contratos,
        ).select_related('plantilla_ruta'):
            asignacion_actual[prc.contrato_id] = prc.plantilla_ruta.entregador_id

    # GET con copiar_ultima=1: copiar desde Ruta(fecha anterior) legacy si existe
    if request.method == 'GET' and request.GET.get('copiar_ultima'):
        fechas_anteriores = (
            Ruta.objects.filter(fecha__lt=fecha)
            .order_by('-fecha')
            .values_list('fecha', flat=True)
            .distinct()
        )
        ultima_fecha = None
        for f in fechas_anteriores:
            if f.weekday() < 5 and not es_feriado(f):
                ultima_fecha = f
                break
        if not ultima_fecha:
            messages.info(
                request,
                'No hay ninguna distribución anterior (Ruta por fecha) para copiar.',
            )
            return redirect(reverse('delivery:distribuir_entregas') + f'?fecha={fecha.isoformat()}')
        asignacion_origen = {
            rc.contrato_id: rc.ruta.entregador_id
            for rc in RutaCliente.objects.filter(ruta__fecha=ultima_fecha).select_related('ruta')
        }
        copiados = 0
        for c in contratos:
            entregador_id = asignacion_origen.get(c.id)
            if entregador_id is None:
                continue
            actual = asignacion_actual.get(c.id)
            if actual == entregador_id:
                continue
            PlantillaRutaCliente.objects.filter(contrato_id=c.id).delete()
            plantilla = _get_or_create_plantilla(Entregador.objects.get(pk=entregador_id))
            max_orden = plantilla.clientes.aggregate(m=Max('orden_entrega'))['m'] or 0
            PlantillaRutaCliente.objects.get_or_create(
                plantilla_ruta=plantilla,
                contrato_id=c.id,
                defaults={'orden_entrega': max_orden + 1},
            )
            asignacion_actual[c.id] = entregador_id
            copiados += 1
        if copiados > 0:
            messages.success(
                request,
                f'Se copió la distribución del {ultima_fecha.strftime("%d/%m/%Y")} ({copiados} punto(s)).',
            )
        else:
            messages.info(request, 'No hubo cambios (ya coincidía).')
        return redirect(reverse('delivery:distribuir_entregas') + f'?fecha={fecha.isoformat()}')

    if request.method == 'POST':
        actualizados = 0
        for c in contratos:
            key = f'entregador_{c.id}'
            entregador_id_raw = request.POST.get(key, '').strip()
            entregador_id = int(entregador_id_raw) if entregador_id_raw and entregador_id_raw.isdigit() else None
            actual = asignacion_actual.get(c.id)

            if actual == entregador_id:
                continue

            PlantillaRutaCliente.objects.filter(contrato_id=c.id).delete()

            if entregador_id:
                plantilla = _get_or_create_plantilla(Entregador.objects.get(pk=entregador_id))
                max_orden = plantilla.clientes.aggregate(m=Max('orden_entrega'))['m'] or 0
                PlantillaRutaCliente.objects.get_or_create(
                    plantilla_ruta=plantilla,
                    contrato_id=c.id,
                    defaults={'orden_entrega': max_orden + 1},
                )
                actualizados += 1
            else:
                actualizados += 1

        if actualizados > 0:
            messages.success(
                request,
                'Distribución guardada. Puedes ver las rutas en la lista de entregas.',
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
            nombre_cliente = (c.cliente.nombre if c.cliente_id else '').strip() or '—'
            direccion = (c.direccion_entrega or '').strip() or '—'
            # Hora de entrega pactada en el contrato
            hora_entrega = (c.horario_entrega.strftime('%H:%M') if c.horario_entrega and hasattr(c.horario_entrega, 'strftime') else None)
            puntos.append({
                'lat': float(c.latitud),
                'lng': float(c.longitud),
                'label': f"{rc.orden_entrega} {nombre_cliente}",
                'orden': rc.orden_entrega,
                'cliente': nombre_cliente,
                'codigo_entrega': (rc.codigo_entrega or '').strip() or '—',
                'direccion': direccion,
                'hora_entrega': hora_entrega,
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
def entregadia_marcar_entregada(request, entregador_id, contrato_id, fecha_str):
    """
    Marca la entrega del día como entregada (entregador, contrato, fecha). Crea/actualiza EntregaDia.
    """
    if not user_can_access_entregador(request.user, entregador_id):
        return JsonResponse({'ok': False, 'error': 'No autorizado.'}, status=403)
    entregador = get_object_or_404(Entregador, pk=entregador_id)
    contrato = get_object_or_404(Contrato, pk=contrato_id)
    try:
        fecha = date.fromisoformat(fecha_str)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Fecha inválida.'}, status=400)
    estado, _ = EntregaDia.objects.get_or_create(
        entregador=entregador,
        contrato=contrato,
        fecha=fecha,
        defaults={},
    )
    estado.entregada = True
    estado.fecha_entrega = timezone.now()
    estado.marcadopor_entregada = request.user
    estado.no_entregada = False
    estado.motivo_no_entrega = ''
    estado.fecha_no_entrega = None
    estado.marcadopor_no_entrega = None
    estado.save(update_fields=[
        'entregada', 'fecha_entrega', 'marcadopor_entregada',
        'no_entregada', 'motivo_no_entrega', 'fecha_no_entrega', 'marcadopor_no_entrega',
    ])
    nombre_usuario = (request.user.get_full_name().strip() or request.user.username) if request.user else ''
    return JsonResponse({
        'ok': True,
        'fecha_entrega': estado.fecha_entrega.isoformat() if estado.fecha_entrega else None,
        'marcado_por': nombre_usuario,
    })


@login_required
@require_POST
def entregadia_reportar_no_entrega(request, entregador_id, contrato_id, fecha_str):
    """
    Reporta que no se pudo realizar la entrega (entregador, contrato, fecha). Requiere motivo en body (JSON).
    """
    import json
    if not user_can_access_entregador(request.user, entregador_id):
        return JsonResponse({'ok': False, 'error': 'No autorizado.'}, status=403)
    entregador = get_object_or_404(Entregador, pk=entregador_id)
    contrato = get_object_or_404(Contrato, pk=contrato_id)
    try:
        fecha = date.fromisoformat(fecha_str)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Fecha inválida.'}, status=400)
    try:
        body = json.loads(request.body.decode('utf-8')) if request.body else {}
    except (ValueError, TypeError):
        body = {}
    motivo = (body.get('motivo') or '').strip()
    if not motivo:
        return JsonResponse({'ok': False, 'error': 'El motivo es obligatorio.'}, status=400)
    estado, _ = EntregaDia.objects.get_or_create(
        entregador=entregador,
        contrato=contrato,
        fecha=fecha,
        defaults={},
    )
    estado.no_entregada = True
    estado.motivo_no_entrega = motivo[:2000]
    estado.fecha_no_entrega = timezone.now()
    estado.marcadopor_no_entrega = request.user
    estado.entregada = False
    estado.fecha_entrega = None
    estado.marcadopor_entregada = None
    estado.save(update_fields=[
        'no_entregada', 'motivo_no_entrega', 'fecha_no_entrega', 'marcadopor_no_entrega',
        'entregada', 'fecha_entrega', 'marcadopor_entregada',
    ])
    nombre_usuario = (request.user.get_full_name().strip() or request.user.username) if request.user else ''
    return JsonResponse({
        'ok': True,
        'marcado_por': nombre_usuario,
        'fecha_no_entrega': estado.fecha_no_entrega.isoformat() if estado.fecha_no_entrega else None,
    })


@login_required
@require_POST
def ruta_calcular_orden(request, entregador_id):
    """
    Calcula el orden óptimo de entregas de la plantilla para la fecha indicada (Google Maps).
    POST: entregador_id en URL; opcional fecha (default hoy). Redirige a edición de plantilla.
    """
    if not user_can_access_entregador(request.user, entregador_id):
        return redirect(get_user_home_url(request.user))
    entregador = get_object_or_404(Entregador, pk=entregador_id)
    fecha_str = request.POST.get('fecha') or timezone.now().date().isoformat()
    try:
        fecha = date.fromisoformat(fecha_str)
    except ValueError:
        fecha = timezone.now().date()
    res = optimizar_orden_entregas_plantilla(entregador, fecha, request=request)
    if res.get('optimizados', 0) > 0:
        messages.success(
            request,
            f"Se optimizó el orden de {res['optimizados']} entrega(s) según Google Maps.",
        )
    if res.get('sin_coordenadas', 0) > 0:
        messages.warning(
            request,
            f"{res['sin_coordenadas']} cliente(s) sin coordenadas (aparecen al final).",
        )
    if res.get('error') and res.get('optimizados', 0) == 0 and res.get('sin_coordenadas', 0) == 0:
        messages.warning(request, f"No se pudo optimizar: {res['error']}.")
    elif res.get('error') and (res.get('optimizados', 0) > 0 or res.get('sin_coordenadas', 0) > 0):
        messages.warning(request, f"Optimización parcial: {res['error']}.")
    if not res.get('error') and res.get('optimizados', 0) == 0 and res.get('sin_coordenadas', 0) == 0:
        messages.info(request, "No había paradas que optimizar o la ruta del día está vacía.")
    return redirect('delivery:ruta_editar_plantilla', entregador_id=entregador_id)


@login_required
@require_POST
def ruta_recalcular_recorrido(request, fecha_str, entregador_id):
    """
    Recalcula el orden de entregas de la ruta del día (entregador + fecha) y devuelve
    los datos del recorrido para actualizar el mapa en el modal (JSON).
    """
    if not user_can_access_entregador(request.user, entregador_id):
        return redirect(get_user_home_url(request.user))
    entregador = get_object_or_404(Entregador, pk=entregador_id)
    try:
        fecha = date.fromisoformat(fecha_str)
    except ValueError:
        fecha = timezone.now().date()
    result = optimizar_orden_entregas_plantilla(entregador, fecha, request=request)
    if result.get('error'):
        return JsonResponse({'ok': False, 'error': result['error']}, status=400)
    paradas = get_paradas_ruta_fecha(entregador, fecha)
    ruta_clientes = [RutaClienteDia(prc, estado) for prc, estado in paradas]
    plantilla = getattr(entregador, 'plantilla_ruta', None)
    class RutaVirtual:
        pass
    ruta = RutaVirtual()
    ruta.duracion_legs_segundos = getattr(plantilla, 'duracion_legs_segundos', None) or []
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
    Redirige a ruta del día por (fecha, entregador) para compatibilidad con enlaces antiguos.
    """
    ruta = get_object_or_404(Ruta, id=ruta_id)
    if not user_can_access_entregador(request.user, ruta.entregador_id):
        return redirect(get_user_home_url(request.user))
    return redirect(
        'delivery:ruta_fecha_entregador',
        fecha_str=ruta.fecha.isoformat(),
        entregador_id=ruta.entregador_id,
    )


@login_required
def ruta_por_fecha_entregador(request, fecha_str, entregador_id):
    """
    Vista para mostrar ruta del día por fecha y entregador (paradas desde plantilla + estado en EntregaDia).
    """
    if not user_can_access_entregador(request.user, entregador_id):
        return redirect(get_user_home_url(request.user))
    try:
        fecha = date.fromisoformat(fecha_str)
    except ValueError:
        fecha = timezone.now().date()
    entregador = get_object_or_404(Entregador, id=entregador_id)
    paradas = get_paradas_ruta_fecha(entregador, fecha)
    ruta_clientes = [RutaClienteDia(prc, estado) for prc, estado in paradas]
    plantilla = getattr(entregador, 'plantilla_ruta', None)
    # Objeto "ruta" virtual para compatibilidad con template (duracion_legs, etc.)
    class RutaVirtual:
        pass
    ruta = RutaVirtual()
    ruta.fecha = fecha
    ruta.entregador = entregador
    ruta.duracion_legs_segundos = getattr(plantilla, 'duracion_legs_segundos', None) or []
    clientes_con_tiempo, total_estimado_str = _tiempos_estimados_ruta(ruta, ruta_clientes)
    mapa_recorrido = _datos_recorrido_ruta(ruta, ruta_clientes)
    from base.models import es_feriado, get_feriado
    context = {
        'ruta': ruta,
        'entregador': entregador,
        'fecha': fecha,
        'fecha_str': fecha_str,
        'ruta_clientes': ruta_clientes,
        'clientes_con_tiempo': clientes_con_tiempo,
        'total_estimado_str': total_estimado_str,
        'mapa_recorrido': mapa_recorrido,
        'es_feriado': es_feriado(fecha),
        'feriado': get_feriado(fecha),
    }
    return render(request, 'delivery/ruta_imprimible.html', context)

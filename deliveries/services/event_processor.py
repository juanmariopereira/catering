"""
Event processing: validate event, apply state transitions, record event, emit outbox.
Idempotent by request_id; invalid transitions return 409 with explanation.
"""
from django.utils import timezone
from django.db import transaction

from deliveries.models import (
    DeliveryActionEvent,
    DeliveryStop,
    DeliveryEventOutbox,
    StopState,
    ActionType,
)
from deliveries.services.proximity import is_near_stop
from deliveries.services.active_stop import get_active_stop, get_allowed_actions
from deliveries.services.courier_config import resolver_config


class EventProcessingError(Exception):
    """Raised when event is invalid (e.g. invalid transition)."""
    def __init__(self, message, status_code=409):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _config_for_route(delivery_route):
    """Resolved courier config for the route's entregador (system + per-delivery)."""
    ent = getattr(delivery_route, 'courier_entregador', None) if delivery_route else None
    return resolver_config(ent)


def _auto_checkin(delivery_route, courier_user, lat, lon, radio_km):
    """
    GPS-based automatic check-in: if the active stop is EN_ROUTE and the courier is
    within the approach radius, transition it to ARRIVED. Delivery/fail stay manual.
    """
    import uuid as _uuid
    active, _next, _status = get_active_stop(delivery_route)
    if not active or active.state != StopState.EN_ROUTE:
        return
    near, _dist = is_near_stop(lat, lon, active, threshold_km=radio_km)
    if not near or not active.can_transition_to(StopState.ARRIVED):
        return
    with transaction.atomic():
        active.state = StopState.ARRIVED
        active.save(update_fields=['state', 'updated_at'])
        DeliveryActionEvent.objects.create(
            request_id=_uuid.uuid4(),
            courier=courier_user,
            stop=active,
            action_type=ActionType.ATTEMPT_ARRIVE,
            payload={'auto': True, 'latitude': lat, 'longitude': lon},
        )


def _emit_outbox(event_type, stop, payload=None):
    DeliveryEventOutbox.objects.create(
        event_type=event_type,
        stop=stop,
        payload=payload or {},
    )


def _sync_ruta_cliente_delivered(stop, when=None):
    """Sync RutaCliente.entregada when stop is DELIVERED."""
    when = when or timezone.now()
    rc = stop.ruta_cliente
    rc.entregada = True
    rc.fecha_entrega = when
    rc.save(update_fields=['entregada', 'fecha_entrega', 'updated_at'])


def _sync_ruta_cliente_failed(stop, reason='', when=None):
    """Sync RutaCliente.no_entregada when stop is FAILED."""
    when = when or timezone.now()
    rc = stop.ruta_cliente
    rc.no_entregada = True
    rc.motivo_no_entrega = reason or 'Reported via app'
    rc.fecha_no_entrega = when
    rc.save(update_fields=['no_entregada', 'motivo_no_entrega', 'fecha_no_entrega', 'updated_at'])


def process_event(courier_user, request_id, action_type, stop_id=None, payload=None):
    """
    Process a single event: validate, dedupe by request_id, apply transition, record, outbox.
    Returns (delivery_route, updated_context_dict) on success.
    Raises EventProcessingError on invalid event (409) or other validation error.
    """
    from deliveries.services.route_sync import get_or_create_today_route_for_courier
    from deliveries.services.active_stop import get_active_stop, get_allowed_actions

    payload = payload or {}
    courier_lat = payload.get('latitude')
    courier_lon = payload.get('longitude')

    # Idempotency: if we already have this request_id, return current context (no-op)
    if DeliveryActionEvent.objects.filter(request_id=request_id).exists():
        delivery_route, err = get_or_create_today_route_for_courier(courier_user)
        if err:
            raise EventProcessingError(err, status_code=403)
        rkm = _config_for_route(delivery_route)['radio_metros'] / 1000.0
        active, next_stop, status = get_active_stop(
            delivery_route, courier_lat=courier_lat, courier_lon=courier_lon
        )
        return (delivery_route, _build_context(delivery_route, active, next_stop, status, courier_lat, courier_lon, radio_km=rkm))

    delivery_route, err = get_or_create_today_route_for_courier(courier_user)
    if err:
        raise EventProcessingError(err, status_code=403)

    cfg = _config_for_route(delivery_route)
    rkm = cfg['radio_metros'] / 1000.0

    if action_type == ActionType.LOCATION_PING:
        from deliveries.models import CourierLocationPing
        with transaction.atomic():
            DeliveryActionEvent.objects.create(
                request_id=request_id,
                courier=courier_user,
                stop=None,
                action_type=action_type,
                payload=payload,
            )
            if courier_lat is not None and courier_lon is not None:
                CourierLocationPing.objects.create(
                    courier=courier_user,
                    delivery_route=delivery_route,
                    latitude=courier_lat,
                    longitude=courier_lon,
                )
        ensure_first_stop_en_route(delivery_route)
        # Check-in automático por GPS (si está habilitado para este entregador)
        if cfg['auto_checkin'] and courier_lat is not None and courier_lon is not None:
            _auto_checkin(delivery_route, courier_user, courier_lat, courier_lon, rkm)
        active, next_stop, status = get_active_stop(
            delivery_route, courier_lat=courier_lat, courier_lon=courier_lon
        )
        return (delivery_route, _build_context(delivery_route, active, next_stop, status, courier_lat, courier_lon, radio_km=rkm))

    # Stop actions require stop_id
    if not stop_id:
        raise EventProcessingError('stop_id is required for this action.', status_code=400)
    try:
        stop = delivery_route.stops.get(pk=stop_id)
    except DeliveryStop.DoesNotExist:
        raise EventProcessingError('Stop not found on your route.', status_code=404)

    if action_type == ActionType.ATTEMPT_ARRIVE:
        if not stop.can_transition_to(StopState.ARRIVED):
            raise EventProcessingError(
                f'Cannot mark arrived: stop is in state {stop.state}. Valid transitions: {StopState.VALID_TRANSITIONS.get(stop.state, [])}',
                status_code=409,
            )
        allowed = get_allowed_actions(stop, courier_lat, courier_lon, radio_km=rkm)
        if not allowed['can_mark_arrived']:
            raise EventProcessingError(
                allowed['reason_if_blocked'] or 'Cannot mark arrived.',
                status_code=409,
            )
        with transaction.atomic():
            stop.state = StopState.ARRIVED
            stop.save(update_fields=['state', 'updated_at'])
            DeliveryActionEvent.objects.create(
                request_id=request_id,
                courier=courier_user,
                stop=stop,
                action_type=action_type,
                payload=payload,
            )
            # Outbox for "arrived" can be added if needed; EN_ROUTE was emitted when stop entered EN_ROUTE
        active, next_stop, status = get_active_stop(delivery_route, courier_lat, courier_lon)
        return (delivery_route, _build_context(delivery_route, active, next_stop, status, courier_lat, courier_lon, radio_km=rkm))

    if action_type == ActionType.ATTEMPT_DELIVER:
        if not stop.can_transition_to(StopState.DELIVERED):
            raise EventProcessingError(
                f'Cannot mark delivered: stop is in state {stop.state}.',
                status_code=409,
            )
        allowed = get_allowed_actions(stop, courier_lat, courier_lon, radio_km=rkm)
        if not allowed['can_mark_delivered']:
            raise EventProcessingError(
                allowed['reason_if_blocked'] or 'Cannot mark delivered.',
                status_code=409,
            )
        when = timezone.now()
        with transaction.atomic():
            stop.state = StopState.DELIVERED
            stop.save(update_fields=['state', 'updated_at'])
            _sync_ruta_cliente_delivered(stop, when)
            DeliveryActionEvent.objects.create(
                request_id=request_id,
                courier=courier_user,
                stop=stop,
                action_type=action_type,
                payload=payload,
            )
            _emit_outbox(DeliveryEventOutbox.EVENT_DELIVERED, stop, payload)
        active, next_stop, status = get_active_stop(delivery_route, courier_lat, courier_lon)
        return (delivery_route, _build_context(delivery_route, active, next_stop, status, courier_lat, courier_lon, radio_km=rkm))

    if action_type == ActionType.ATTEMPT_FAIL:
        if not stop.can_transition_to(StopState.FAILED):
            raise EventProcessingError(
                f'Cannot mark failed: stop is in state {stop.state}.',
                status_code=409,
            )
        reason = payload.get('reason', '') or payload.get('motivo_no_entrega', '')
        when = timezone.now()
        with transaction.atomic():
            stop.state = StopState.FAILED
            stop.save(update_fields=['state', 'updated_at'])
            _sync_ruta_cliente_failed(stop, reason, when)
            DeliveryActionEvent.objects.create(
                request_id=request_id,
                courier=courier_user,
                stop=stop,
                action_type=action_type,
                payload=payload,
            )
            _emit_outbox(DeliveryEventOutbox.EVENT_FAILED, stop, payload)
        active, next_stop, status = get_active_stop(delivery_route, courier_lat, courier_lon)
        return (delivery_route, _build_context(delivery_route, active, next_stop, status, courier_lat, courier_lon, radio_km=rkm))

    raise EventProcessingError(f'Unknown action type: {action_type}.', status_code=400)


def _distance_m(stop, courier_lat, courier_lon):
    """Distance in meters from the courier to a stop, or None if unknown."""
    if stop is None or courier_lat is None or courier_lon is None:
        return None
    from deliveries.services.proximity import get_stop_coordinates, haversine_km
    slat, slon = get_stop_coordinates(stop)
    if slat is None or slon is None:
        return None
    return round(haversine_km(courier_lat, courier_lon, slat, slon) * 1000)


def _build_context(delivery_route, active_stop, next_stop, status_message, courier_lat, courier_lon, radio_km=None):
    """Build context dict for API response: route, stops, allowed_actions, config, distance to active stop."""
    stops = list(delivery_route.stops.all().order_by('sequence'))
    stop_list = []
    for s in stops:
        allowed = get_allowed_actions(s, courier_lat, courier_lon, radio_km=radio_km)
        stop_list.append({
            'id': s.pk,
            'sequence': s.sequence,
            'state': s.state,
            'ruta_cliente_id': s.ruta_cliente_id,
            'codigo_entrega': s.ruta_cliente.codigo_entrega,
            'address': _stop_address(s),
            'can_mark_arrived': allowed['can_mark_arrived'],
            'can_mark_delivered': allowed['can_mark_delivered'],
            'can_mark_failed': allowed['can_mark_failed'],
            'reason_if_blocked': allowed['reason_if_blocked'],
        })
    active_summary = _stop_summary(active_stop) if active_stop else None
    if active_summary is not None:
        active_summary['distance_m'] = _distance_m(active_stop, courier_lat, courier_lon)
    next_summary = _stop_summary(next_stop) if next_stop else None
    if next_summary is not None:
        next_summary['distance_m'] = _distance_m(next_stop, courier_lat, courier_lon)
    return {
        'route': {
            'id': delivery_route.pk,
            'date': str(delivery_route.date),
        },
        'stops': stop_list,
        'current_active_stop_id': active_stop.pk if active_stop else None,
        'next_stop_id': next_stop.pk if next_stop else None,
        'status': status_message,
        'current_active_stop': active_summary,
        'next_stop': next_summary,
        'config': _config_for_route(delivery_route),
    }


def _stop_address(stop):
    if not stop:
        return None
    try:
        return stop.ruta_cliente.contrato.direccion_entrega or ''
    except Exception:
        return ''


def _stop_summary(stop):
    if not stop:
        return None
    return {
        'id': stop.pk,
        'sequence': stop.sequence,
        'state': stop.state,
        'codigo_entrega': stop.ruta_cliente.codigo_entrega,
        'address': _stop_address(stop),
    }


def mark_first_stop_en_route(delivery_route):
    """
    When courier starts the route, first PENDING stop can be marked EN_ROUTE.
    Called optionally when we want to auto-advance; or the app sends ATTEMPT_ARRIVE
    which we map to EN_ROUTE -> ARRIVED. Per spec, EN_ROUTE is a state; we transition
    PENDING -> EN_ROUTE when appropriate (e.g. when they ping location and we consider
    them "on the way"). For simplicity we do PENDING -> EN_ROUTE when they first
    interact, or we require an explicit "start route" event. Spec says transitions
    ATTEMPT_ARRIVE -> ARRIVED. So EN_ROUTE is set when? Either:
    - When they send first LOCATION_PING and we consider first stop "en route", or
    - We add a "start_route" action that does PENDING -> EN_ROUTE.
    Spec: "stop enters EN_ROUTE" triggers outbox. So we need to transition to EN_ROUTE
    at some point. I'll do: when they ATTEMPT_ARRIVE, we go EN_ROUTE -> ARRIVED.
    So the first stop must be EN_ROUTE before they can ATTEMPT_ARRIVE. So we need
    to set first PENDING stop to EN_ROUTE when route is "started". For MVP we can
    set the first stop to EN_ROUTE when they fetch context (so "active" stop is
    already EN_ROUTE), or when they send first LOCATION_PING. Let me add: when
    returning context, if the active stop is PENDING, we don't allow ATTEMPT_ARRIVE
    (we allow "start" which transitions PENDING -> EN_ROUTE). So we need either
    - Allow ATTEMPT_ARRIVE from PENDING to mean "I'm on my way" -> EN_ROUTE, or
    - Have a separate "start_route" that sets first stop to EN_ROUTE.
    Spec says: "ATTEMPT_ARRIVE" and "ATTEMPT_DELIVER", "ATTEMPT_FAIL". So ATTEMPT_ARRIVE
    likely means "I've arrived at the stop" -> ARRIVED. So PENDING -> EN_ROUTE must
    happen elsewhere. I'll set it when they first get context (so first stop is
    shown as EN_ROUTE) or on first LOCATION_PING. Implementing: when we return
    context, if active stop is PENDING, we could auto-transition to EN_ROUTE and
    emit outbox. That might be too implicit. Better: add logic in event processor
    - For ATTEMPT_ARRIVE we currently require state EN_ROUTE. So the app must
    first "start" the stop. Add action START_STOP or interpret first LOCATION_PING
    for the route as "start route" and set first PENDING to EN_ROUTE. I'll add
    a simple rule: when get_or_create_today_route returns the route, we don't
    auto-change. When they send LOCATION_PING and the current active stop is
    PENDING, we could transition it to EN_ROUTE (so "en route to first stop").
    Let me do that in process_event for LOCATION_PING: after recording ping,
    if active stop is PENDING, transition to EN_ROUTE and emit outbox.
    """
    first = delivery_route.stops.filter(state=StopState.PENDING).order_by('sequence').first()
    if first:
        first.state = StopState.EN_ROUTE
        first.save(update_fields=['state', 'updated_at'])
        _emit_outbox(DeliveryEventOutbox.EVENT_EN_ROUTE, first)


def ensure_first_stop_en_route(delivery_route):
    """If active stop is PENDING, transition to EN_ROUTE and emit (e.g. on first ping)."""
    active, _, _ = get_active_stop(delivery_route)
    if active and active.state == StopState.PENDING:
        mark_first_stop_en_route(delivery_route)

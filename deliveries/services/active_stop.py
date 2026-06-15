"""
Active stop calculation: backend determines which stop is active based on
route sequence, previous completed stops, and optionally courier location.
"""
from .proximity import is_near_stop, get_stop_coordinates


def get_active_stop(delivery_route, courier_lat=None, courier_lon=None):
    """
    Determine current active stop for the route.
    Returns (active_stop, next_stop, status_message).
    - active_stop: DeliveryStop or None
    - next_stop: DeliveryStop or None
    - status_message: human-readable string for UI
    """
    stops = list(delivery_route.stops.all().order_by('sequence'))
    if not stops:
        return (None, None, 'No stops on this route.')

    # First non-terminal stop (not DELIVERED, not FAILED) in sequence is active
    active = None
    next_stop = None
    for s in stops:
        if s.state not in ('DELIVERED', 'FAILED'):
            active = s
            idx = stops.index(s)
            if idx + 1 < len(stops):
                next_stop = stops[idx + 1]
            break

    if active is None:
        return (None, None, 'All stops completed.')

    # Optional: if courier location provided and they're near a later stop,
    # we could consider that stop active (e.g. out-of-order). For MVP we stick
    # to sequence-only: first incomplete stop is active.
    if courier_lat is not None and courier_lon is not None:
        # Could refine: if courier is near a later stop, use that as active.
        # For now we keep sequence-based only.
        pass

    if active.state == 'PENDING':
        status = 'Next stop in route.'
    elif active.state == 'EN_ROUTE':
        status = 'En route to this stop.'
    elif active.state == 'ARRIVED':
        status = 'At stop; you can mark delivered or fail.'
    else:
        status = f'Stop status: {active.state}.'

    return (active, next_stop, status)


def get_allowed_actions(stop, courier_lat=None, courier_lon=None, radio_km=None):
    """
    Server-driven allowed actions for a stop.
    radio_km: approach radius (km) from courier config; falls back to default if None.
    Returns dict: can_mark_arrived, can_mark_delivered, can_mark_failed, reason_if_blocked.
    """
    result = {
        'can_mark_arrived': False,
        'can_mark_delivered': False,
        'can_mark_failed': False,
        'reason_if_blocked': None,
    }
    if stop.state == 'EN_ROUTE':
        near, _ = is_near_stop(courier_lat or 0, courier_lon or 0, stop, threshold_km=radio_km)
        if courier_lat is not None and courier_lon is not None:
            result['can_mark_arrived'] = near
            if not near:
                result['reason_if_blocked'] = 'You must be closer to the stop to mark arrived.'
        else:
            result['can_mark_arrived'] = True  # Allow if no location yet
    if stop.state == 'ARRIVED':
        near = True
        if courier_lat is not None and courier_lon is not None:
            near, _ = is_near_stop(courier_lat, courier_lon, stop, threshold_km=radio_km)
        result['can_mark_delivered'] = near
        result['can_mark_failed'] = True
        if not near:
            result['reason_if_blocked'] = 'You must be at the stop to mark delivered.'
    if stop.state == 'EN_ROUTE':
        result['can_mark_failed'] = True
    return result

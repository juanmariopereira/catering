"""
Sync DeliveryRoute and DeliveryStops from routes.Ruta and RutaCliente.
Ensures today's route exists for the courier with correct stops and state.
"""
from django.utils import timezone

from deliveries.models import (
    CourierProfile,
    DeliveryRoute,
    DeliveryStop,
    StopState,
)
from routes.models import Ruta, RutaCliente


def get_or_create_today_route_for_courier(user):
    """
    Get or create DeliveryRoute for the courier's today route.
    Requires user to have CourierProfile linked to an Entregador.
    Creates DeliveryRoute from Ruta and DeliveryStops from RutaCliente if missing.
    Returns (DeliveryRoute or None, error_message).
    """
    try:
        profile = CourierProfile.objects.select_related('entregador').get(user=user)
    except CourierProfile.DoesNotExist:
        return (None, 'User is not a courier.')

    today = timezone.localdate()
    try:
        ruta = Ruta.objects.select_related('entregador').prefetch_related(
            'ruta_clientes__contrato',
        ).get(fecha=today, entregador=profile.entregador, activa=True)
    except Ruta.DoesNotExist:
        return (None, 'No route assigned for today.')

    delivery_route, _ = DeliveryRoute.objects.get_or_create(
        ruta=ruta,
        defaults={},
    )

    # Sync stops: create DeliveryStop for each RutaCliente if not present
    for rc in ruta.ruta_clientes.all().order_by('orden_entrega'):
        DeliveryStop.objects.get_or_create(
            delivery_route=delivery_route,
            ruta_cliente=rc,
            defaults={'sequence': rc.orden_entrega, 'state': StopState.PENDING},
        )

    # Ensure sequence is up to date
    for stop in delivery_route.stops.all():
        if stop.sequence != stop.ruta_cliente.orden_entrega:
            stop.sequence = stop.ruta_cliente.orden_entrega
            stop.save(update_fields=['sequence', 'updated_at'])

    return (delivery_route, None)

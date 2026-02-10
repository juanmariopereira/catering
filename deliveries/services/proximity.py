"""
Proximity logic: Haversine distance and "near stop" decision.
All distance calculations are server-side; mobile only sends raw GPS.
"""
import math
from decimal import Decimal

# Default threshold in km. Courier must be within this to mark arrived/delivered.
DEFAULT_PROXIMITY_KM = 0.15


def haversine_km(lat1, lon1, lat2, lon2):
    """
    Haversine distance in km between two points.
    Accepts Decimal or float.
    """
    lat1 = float(lat1)
    lon1 = float(lon1)
    lat2 = float(lat2)
    lon2 = float(lon2)
    R = 6371  # Earth radius in km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def get_stop_coordinates(stop):
    """
    Get (lat, lon) for a DeliveryStop from linked RutaCliente/Contrato.
    Returns (None, None) if no coordinates.
    """
    try:
        contrato = stop.ruta_cliente.contrato
        lat = contrato.latitud
        lon = contrato.longitud
        if lat is not None and lon is not None:
            return (lat, lon)
    except Exception:
        pass
    return (None, None)


def is_near_stop(courier_lat, courier_lon, stop, threshold_km=None):
    """
    Backend decides if courier is near a stop.
    Returns (is_near: bool, distance_km: float or None).
    """
    if threshold_km is None:
        threshold_km = DEFAULT_PROXIMITY_KM
    stop_lat, stop_lon = get_stop_coordinates(stop)
    if stop_lat is None or stop_lon is None:
        return (False, None)
    distance_km = haversine_km(
        float(courier_lat), float(courier_lon),
        float(stop_lat), float(stop_lon),
    )
    return (distance_km <= threshold_km, distance_km)

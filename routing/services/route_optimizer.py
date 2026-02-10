"""
Business logic and validation for route optimization.
Uses Google Routes API (Routes Preferred) with up to 98 stops (lat/lng only).
"""
import logging
from typing import Any, Dict, List, Optional

from django.conf import settings

from .google_routes import compute_routes

logger = logging.getLogger(__name__)

# Routes Preferred: max 98 intermediate waypoints when using lat/lng (no Place IDs)
MAX_STOPS = 98

# Valid lat/lng ranges
LAT_MIN, LAT_MAX = -90.0, 90.0
LNG_MIN, LNG_MAX = -180.0, 180.0


class RouteOptimizerError(Exception):
    """Raised on validation or API errors."""
    def __init__(self, message: str, code: str = "error"):
        self.message = message
        self.code = code
        super().__init__(message)


def _validate_lat_lng(lat: float, lng: float, name: str) -> None:
    """Validate latitude and longitude; raise RouteOptimizerError if invalid."""
    if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
        raise RouteOptimizerError(f"{name}: lat and lng must be numbers", "invalid_coords")
    if not (LAT_MIN <= lat <= LAT_MAX):
        raise RouteOptimizerError(f"{name}: latitude must be between {LAT_MIN} and {LAT_MAX}", "invalid_coords")
    if not (LNG_MIN <= lng <= LNG_MAX):
        raise RouteOptimizerError(f"{name}: longitude must be between {LNG_MIN} and {LNG_MAX}", "invalid_coords")


def _parse_duration(dur: Any) -> Optional[int]:
    """Parse duration from API (string '3600s' or object with seconds). Return seconds or None."""
    if dur is None:
        return None
    if isinstance(dur, str):
        if dur.endswith("s"):
            try:
                return int(dur[:-1])
            except ValueError:
                return None
        return None
    if isinstance(dur, dict) and "seconds" in dur:
        try:
            return int(dur["seconds"])
        except (TypeError, ValueError):
            return None
    return None


def optimize_route(
    start: Dict[str, float],
    stops: List[Dict[str, Any]],
    end: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Compute optimized visiting order for stops using Google Routes API.

    Args:
        start: {"lat": float, "lng": float} - start point
        stops: list of {"id": any, "lat": float, "lng": float} - up to 98 stops
        end: optional {"lat": float, "lng": float}; if omitted, end = start (round trip)

    Returns:
        {
            "optimized_stop_ids": [id, ...],  # order to visit
            "legs": [{"distance_meters": int, "duration_seconds": int}, ...],
            "polyline": Optional[str],  # encoded polyline if available
            "summary": {"total_distance_meters": int, "total_duration_seconds": int},
        }

    Raises:
        RouteOptimizerError: on validation (e.g. >98 stops, invalid coords) or API error
    """
    api_key = (getattr(settings, "GOOGLE_MAPS_API_KEY", None) or "").strip()
    if not api_key:
        raise RouteOptimizerError("GOOGLE_MAPS_API_KEY is not configured", "config")

    # Validate start
    if not start or "lat" not in start or "lng" not in start:
        raise RouteOptimizerError("start must have lat and lng", "invalid_input")
    _validate_lat_lng(start["lat"], start["lng"], "start")

    # End: default to start if omitted
    if end is None:
        end = {"lat": start["lat"], "lng": start["lng"]}
    if "lat" not in end or "lng" not in end:
        raise RouteOptimizerError("end must have lat and lng when provided", "invalid_input")
    _validate_lat_lng(end["lat"], end["lng"], "end")

    # Validate stops
    if not isinstance(stops, list):
        raise RouteOptimizerError("stops must be a list", "invalid_input")
    if len(stops) > MAX_STOPS:
        raise RouteOptimizerError(
            f"stops must have at most {MAX_STOPS} items (got {len(stops)})",
            "too_many_stops",
        )
    stop_ids = []
    intermediates = []
    for i, s in enumerate(stops):
        if not isinstance(s, dict):
            raise RouteOptimizerError(f"stop at index {i} must be an object", "invalid_input")
        if "id" not in s:
            raise RouteOptimizerError(f"stop at index {i} must have id", "invalid_input")
        if "lat" not in s or "lng" not in s:
            raise RouteOptimizerError(f"stop at index {i} must have lat and lng", "invalid_input")
        _validate_lat_lng(s["lat"], s["lng"], f"stop[{i}]")
        stop_ids.append(s["id"])
        intermediates.append({"lat": float(s["lat"]), "lng": float(s["lng"])})

    # No intermediates: return trivial order and empty legs
    if len(intermediates) == 0:
        return {
            "optimized_stop_ids": [],
            "legs": [],
            "polyline": None,
            "summary": {"total_distance_meters": 0, "total_duration_seconds": 0},
        }

    # Call Routes API
    try:
        raw = compute_routes(
            api_key=api_key,
            origin_lat=float(start["lat"]),
            origin_lng=float(start["lng"]),
            destination_lat=float(end["lat"]),
            destination_lng=float(end["lng"]),
            intermediates=intermediates,
        )
    except Exception as e:
        logger.exception("Routes API error: %s", e)
        msg = str(e)
        if hasattr(e, "response") and e.response is not None:
            try:
                body = e.response.json()
                msg = body.get("error", {}).get("message", msg)
            except Exception:
                pass
        raise RouteOptimizerError(f"Routes API error: {msg}", "api_error")

    # Parse response
    routes = raw.get("routes") or []
    if not routes:
        raise RouteOptimizerError("Routes API returned no routes", "api_error")

    route = routes[0]

    # Optimized order: optimizedIntermediateWaypointIndex is array of indices into intermediates
    optimized_index = route.get("optimizedIntermediateWaypointIndex")
    if optimized_index is None:
        # API did not return optimized order (e.g. optimization not enabled or failed)
        optimized_index = list(range(len(stop_ids)))
    optimized_stop_ids = [stop_ids[i] for i in optimized_index]

    # Legs: distanceMeters, duration (string "3600s" or object)
    legs_data = []
    for leg in route.get("legs") or []:
        dm = leg.get("distanceMeters")
        if dm is not None:
            try:
                dm = int(dm)
            except (TypeError, ValueError):
                dm = 0
        else:
            dm = 0
        dur = _parse_duration(leg.get("duration"))
        legs_data.append({"distance_meters": dm, "duration_seconds": dur})

    # Summary: total distance and duration at route level
    total_m = route.get("distanceMeters")
    if total_m is not None:
        try:
            total_m = int(total_m)
        except (TypeError, ValueError):
            total_m = sum(l.get("distance_meters", 0) for l in legs_data)
    else:
        total_m = sum(l.get("distance_meters", 0) for l in legs_data)

    total_s = _parse_duration(route.get("duration"))
    if total_s is None:
        total_s = sum(l.get("duration_seconds") or 0 for l in legs_data)

    # Polyline
    polyline = None
    pl = route.get("polyline") or {}
    if isinstance(pl, dict) and pl.get("encodedPolyline"):
        polyline = pl["encodedPolyline"]

    return {
        "optimized_stop_ids": optimized_stop_ids,
        "legs": legs_data,
        "polyline": polyline,
        "summary": {
            "total_distance_meters": total_m,
            "total_duration_seconds": total_s,
        },
    }

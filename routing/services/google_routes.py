"""
Google Routes API (Routes Preferred) client wrapper.
POST https://routes.googleapis.com/directions/v2:computeRoutes
Uses raw lat/lng only (no Place IDs) to support up to 98 waypoints with optimization.
"""
import logging
import time
from typing import Any, Dict, List

import httpx

logger = logging.getLogger(__name__)

# Routes API (Directions v2) endpoint for computeRoutes
ROUTES_API_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"

# Minimal field mask to reduce cost/latency: optimized order, legs (distance/duration), polyline, summary
FIELD_MASK = (
    "routes.optimizedIntermediateWaypointIndex,"
    "routes.legs.distanceMeters,routes.legs.duration,"
    "routes.distanceMeters,routes.duration,"
    "routes.polyline.encodedPolyline"
)

CONNECT_TIMEOUT = 10.0
READ_TIMEOUT = 30.0  # Optimization with many waypoints can take longer
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 1.0  # seconds


def _build_waypoint(lat: float, lng: float) -> Dict[str, Any]:
    """Build a Waypoint object using latLng (no placeId)."""
    return {
        "location": {
            "latLng": {
                "latitude": lat,
                "longitude": lng,
            }
        }
    }


def _build_request_body(
    origin_lat: float,
    origin_lng: float,
    destination_lat: float,
    destination_lng: float,
    intermediates: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build ComputeRoutes request body.
    intermediates: list of {lat, lng} (no id here; order is preserved and mapped by index).
    """
    body = {
        "origin": _build_waypoint(origin_lat, origin_lng),
        "destination": _build_waypoint(destination_lat, destination_lng),
        "intermediates": [_build_waypoint(p["lat"], p["lng"]) for p in intermediates],
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
        "optimizeWaypointOrder": True,
        "languageCode": "es",
        "units": "METRIC",
    }
    return body


def compute_routes(
    api_key: str,
    origin_lat: float,
    origin_lng: float,
    destination_lat: float,
    destination_lng: float,
    intermediates: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Call Google Routes API computeRoutes with waypoint optimization.

    Args:
        api_key: GOOGLE_MAPS_API_KEY
        origin_lat, origin_lng: start point
        destination_lat, destination_lng: end point
        intermediates: list of {"lat": float, "lng": float} (up to 98 for Routes Preferred with lat/lng)

    Returns:
        Parsed JSON response from the API.

    Raises:
        httpx.HTTPStatusError: on 4xx/5xx (after retries for 429/5xx)
        httpx.TimeoutException: on timeout
        ValueError: on invalid response or missing required fields
    """
    if not api_key or not api_key.strip():
        raise ValueError("GOOGLE_MAPS_API_KEY is required")

    body = _build_request_body(
        origin_lat, origin_lng,
        destination_lat, destination_lng,
        intermediates,
    )

    headers = {
        "X-Goog-Api-Key": api_key.strip(),
        "X-Goog-FieldMask": FIELD_MASK,
        "Content-Type": "application/json",
    }

    last_exception = None
    for attempt in range(MAX_RETRIES):
        try:
            with httpx.Client(timeout=httpx.Timeout(CONNECT_TIMEOUT, read=READ_TIMEOUT)) as client:
                response = client.post(
                    ROUTES_API_URL,
                    json=body,
                    headers=headers,
                )
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            last_exception = e
            # Retry on 429 (quota) or 5xx (transient)
            if e.response.status_code == 429 or e.response.status_code >= 500:
                if attempt < MAX_RETRIES - 1:
                    backoff = RETRY_BACKOFF_BASE * (2 ** attempt)
                    logger.warning(
                        "Routes API attempt %s failed with %s, retrying in %.1fs",
                        attempt + 1, e.response.status_code, backoff,
                    )
                    time.sleep(backoff)
                    continue
            raise

        except (httpx.TimeoutException, httpx.ConnectError) as e:
            last_exception = e
            if attempt < MAX_RETRIES - 1:
                backoff = RETRY_BACKOFF_BASE * (2 ** attempt)
                logger.warning(
                    "Routes API attempt %s timeout/connect error, retrying in %.1fs: %s",
                    attempt + 1, backoff, e,
                )
                time.sleep(backoff)
                continue
            raise

    if last_exception is not None:
        raise last_exception
    raise ValueError("Unexpected error in compute_routes")

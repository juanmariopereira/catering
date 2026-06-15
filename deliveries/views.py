"""
REST API views for deliveries (courier app).
Backend-driven: all state and permissions come from server.
"""
import uuid
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .models import CourierProfile, MobileAppVersion
from .permissions import IsCourier
from .serializers import EventRequestSerializer
from .services.route_sync import get_or_create_today_route_for_courier
from .services.active_stop import get_active_stop, get_allowed_actions
from .services.event_processor import process_event, EventProcessingError
from .services.courier_config import resolver_config
from .services.proximity import get_stop_coordinates, haversine_km


def _distance_m(stop, lat, lon):
    """Distancia en metros del courier a la parada, o None."""
    if stop is None or lat is None or lon is None:
        return None
    slat, slon = get_stop_coordinates(stop)
    if slat is None or slon is None:
        return None
    return round(haversine_km(lat, lon, slat, slon) * 1000)


def _build_context_response(delivery_route, profile, courier_lat=None, courier_lon=None):
    """Build full context dict for courier (profile + route snapshot)."""
    if delivery_route is None:
        return {
            'profile': {
                'id': profile.pk,
                'entregador_id': profile.entregador_id,
                'entregador_name': profile.entregador.nombre,
            },
            'route': None,
            'stops': [],
            'current_active_stop_id': None,
            'next_stop_id': None,
            'status': profile and 'No route assigned for today.' or 'You are not a courier.',
            'current_active_stop': None,
            'next_stop': None,
            'config': resolver_config(profile.entregador if profile else None),
        }
    cfg = resolver_config(delivery_route.courier_entregador)
    radio_km = cfg['radio_metros'] / 1000.0
    active, next_stop, status_msg = get_active_stop(
        delivery_route, courier_lat=courier_lat, courier_lon=courier_lon
    )
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
    active_summary = _stop_summary(active) if active else None
    if active_summary is not None:
        active_summary['distance_m'] = _distance_m(active, courier_lat, courier_lon)
    next_summary = _stop_summary(next_stop) if next_stop else None
    if next_summary is not None:
        next_summary['distance_m'] = _distance_m(next_stop, courier_lat, courier_lon)
    return {
        'profile': {
            'id': profile.pk,
            'entregador_id': profile.entregador_id,
            'entregador_name': profile.entregador.nombre,
        },
        'route': {'id': delivery_route.pk, 'date': str(delivery_route.date)},
        'stops': stop_list,
        'current_active_stop_id': active.pk if active else None,
        'next_stop_id': next_stop.pk if next_stop else None,
        'status': status_msg,
        'current_active_stop': active_summary,
        'next_stop': next_summary,
        'config': cfg,
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


class CourierContextView(APIView):
    """
    GET /api/v1/courier/context/
    Returns courier profile, today route, stops, current_active_stop_id, allowed_actions per stop.
    """
    permission_classes = [IsAuthenticated, IsCourier]

    def get(self, request):
        try:
            profile = CourierProfile.objects.select_related('entregador').get(user=request.user)
        except CourierProfile.DoesNotExist:
            return Response(
                {'detail': 'You are not a courier.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        delivery_route, err = get_or_create_today_route_for_courier(request.user)
        if err and delivery_route is None:
            return Response(
                _build_context_response(None, profile),
                status=status.HTTP_200_OK,
            )
        data = _build_context_response(delivery_route, profile)
        return Response(data)


class CourierConfigView(APIView):
    """
    GET /api/v1/courier/config/
    Returns the effective tracking config for the logged-in courier
    (system defaults merged with per-entregador overrides).
    """
    permission_classes = [IsAuthenticated, IsCourier]

    def get(self, request):
        try:
            profile = CourierProfile.objects.select_related('entregador').get(user=request.user)
        except CourierProfile.DoesNotExist:
            return Response(
                {'detail': 'You are not a courier.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(resolver_config(profile.entregador))


class EventView(APIView):
    """
    POST /api/v1/events/
    Body: { request_id, type, stop_id?, payload? }
    Validates event, applies state transition, records DeliveryActionEvent, returns updated route snapshot.
    Idempotent: repeated request_id returns 200 with current context.
    Invalid transitions return 409 with explanation.
    """
    permission_classes = [IsAuthenticated, IsCourier]

    def post(self, request):
        serializer = EventRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        request_id = data['request_id']
        action_type = data['type']
        stop_id = data.get('stop_id')
        payload = data.get('payload') or {}
        if action_type != 'LOCATION_PING':
            if not stop_id:
                return Response(
                    {'detail': 'stop_id is required for this action.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        try:
            profile = CourierProfile.objects.select_related('entregador').get(user=request.user)
        except CourierProfile.DoesNotExist:
            return Response(
                {'detail': 'You are not a courier.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            delivery_route, context = process_event(
                request.user,
                request_id=request_id,
                action_type=action_type,
                stop_id=stop_id,
                payload=payload,
            )
        except EventProcessingError as e:
            return Response(
                {'detail': e.message},
                status=e.status_code,
            )
        full = _build_context_response(
            delivery_route,
            profile,
            courier_lat=payload.get('latitude'),
            courier_lon=payload.get('longitude'),
        )
        return Response(full, status=status.HTTP_200_OK)


class MobileVersionView(APIView):
    """
    GET /api/v1/mobile/version/?platform=ANDROID&current_version_code=123
    Returns latest version info and update_required, apk_url if update available.
    Public (no auth required for version check).
    """
    permission_classes = [AllowAny]

    def get(self, request):
        platform = request.query_params.get('platform', 'ANDROID').upper()
        try:
            current = request.query_params.get('current_version_code')
            current_code = int(current) if current is not None else None
        except (TypeError, ValueError):
            current_code = None
        latest = (
            MobileAppVersion.objects.filter(platform=platform)
            .order_by('-version_code')
            .first()
        )
        if not latest:
            return Response(
                {
                    'platform': platform,
                    'version_code': 0,
                    'min_version_code': 0,
                    'update_required': False,
                    'apk_url': '',
                    'release_notes': '',
                },
                status=status.HTTP_200_OK,
            )
        update_required = current_code is not None and current_code < latest.min_version_code
        return Response(
            {
                'platform': latest.platform,
                'version_code': latest.version_code,
                'min_version_code': latest.min_version_code,
                'update_required': update_required,
                'apk_url': latest.apk_url if update_required else '',
                'release_notes': latest.release_notes or '',
            },
            status=status.HTTP_200_OK,
        )

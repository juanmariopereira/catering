"""
Servicio para optimizar el orden de entregas de una ruta usando Google Directions API.
Requiere GOOGLE_MAPS_API_KEY en settings.
Registra cada solicitud a la API en base.models.ExternalApiRequestLog.
"""
import logging
import time
from urllib.parse import urlencode
from urllib.request import urlopen
import json

from django.conf import settings

logger = logging.getLogger(__name__)

DIRECTIONS_URL = 'https://maps.googleapis.com/maps/api/directions/json'

# Límite de la API de Google Directions (solo waypoints; origin y destination no cuentan)
MAX_WAYPOINTS_PER_REQUEST = 25


def _get_punto_partida_activo():
    """Devuelve el punto de partida activo para optimización de rutas, o None."""
    try:
        from delivery.models import PuntoPartidaEntrega
        return PuntoPartidaEntrega.objects.filter(activo=True).order_by('-fecha_actualizacion').first()
    except Exception:
        return None


def _ensure_json_serializable(obj):
    """Convierte a estructura solo con tipos que JSONField puede serializar."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {str(k): _ensure_json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_ensure_json_serializable(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)):
        return obj
    return str(obj)


def _log_directions_request(ruta, request_params_safe, request_extra, response_status, response_body, exito, mensaje_error, duracion_ms, request=None):
    """Crea un registro en ExternalApiRequestLog para la llamada a Directions API."""
    try:
        from base.models import ExternalApiRequestLog
        user = request.user if request and getattr(request, 'user', None) else None
        ExternalApiRequestLog.objects.create(
            api='google_directions',
            endpoint=DIRECTIONS_URL,
            request_params=_ensure_json_serializable(request_params_safe) or {},
            request_extra=str(request_extra or ''),
            response_status=str(response_status or '')[:64],
            response_body=_ensure_json_serializable(response_body) if response_body is not None else {},
            exito=bool(exito),
            mensaje_error=str(mensaje_error or ''),
            duracion_ms=duracion_ms,
            objeto_tipo='ruta',
            objeto_id=ruta.pk if ruta else None,
            usuario=user,
        )
    except Exception as e:
        logger.exception('No se pudo guardar ExternalApiRequestLog: %s', e)


def _log_directions_skipped(ruta, reason, request=None):
    """Registra que no se llamó a la API (omitido por falta de key, waypoints, etc.)."""
    try:
        from base.models import ExternalApiRequestLog
        user = request.user if request and getattr(request, 'user', None) else None
        ExternalApiRequestLog.objects.create(
            api='google_directions',
            endpoint=DIRECTIONS_URL,
            request_params={},
            request_extra=f'skipped;reason={reason}',
            response_status='SKIPPED',
            response_body={'reason': reason},
            exito=False,
            mensaje_error=reason,
            duracion_ms=None,
            objeto_tipo='ruta',
            objeto_id=ruta.pk if ruta else None,
            usuario=user,
        )
    except Exception as e:
        logger.exception('No se pudo guardar ExternalApiRequestLog (skipped): %s', e)


def optimizar_orden_entregas(ruta, request=None):
    """
    Dada una instancia de Ruta (con ruta_clientes ya cargados), envía las coordenadas
    de los contratos que las tienen a la API de Google Directions con optimize:true,
    obtiene el orden óptimo y actualiza orden_entrega en cada RutaCliente.

    - Los RutaCliente cuyo contrato tiene latitud y longitud se incluyen en la
      optimización; se actualiza su orden_entrega según la respuesta de la API.
    - Los que no tienen coordenadas mantienen su orden relativo y se colocan al
      final (orden_entrega mayor que los optimizados).

    Devuelve un dict:
      - 'optimizados': número de clientes reordenados por la API
      - 'sin_coordenadas': número de clientes que no tenían coordenadas (no se optimizan)
      - 'error': mensaje de error si la API falló (optimizados y sin_coordenadas siguen informados)
    """
    from routes.models import RutaCliente

    api_key = getattr(settings, 'GOOGLE_MAPS_API_KEY', None) or ''
    if not api_key.strip():
        logger.warning('GOOGLE_MAPS_API_KEY no configurada; se omite optimización de ruta.')
        _log_directions_skipped(ruta, 'API key no configurada', request=request)
        return {'optimizados': 0, 'sin_coordenadas': 0, 'error': 'API key no configurada'}

    ruta_clientes = list(
        ruta.ruta_clientes.select_related('contrato').order_by('orden_entrega')
    )
    if not ruta_clientes:
        _log_directions_skipped(ruta, 'Ruta sin clientes', request=request)
        return {'optimizados': 0, 'sin_coordenadas': 0}

    con_coords = []
    sin_coords = []
    for rc in ruta_clientes:
        c = rc.contrato
        if c.latitud is not None and c.longitud is not None:
            con_coords.append((rc, float(c.latitud), float(c.longitud)))
        else:
            sin_coords.append(rc)

    result = {'optimizados': 0, 'sin_coordenadas': len(sin_coords)}

    if len(con_coords) < 2:
        # Sin suficientes puntos la API no optimiza; mantener orden actual
        _log_directions_skipped(
            ruta,
            f'Waypoints insuficientes (con coordenadas: {len(con_coords)}, mínimo 2)',
            request=request,
        )
        return result

    # Origen/destino: punto de partida (cocina/depósito) o primer entrega
    punto_partida = _get_punto_partida_activo()
    if punto_partida is not None:
        origin_str = f'{float(punto_partida.latitud)},{float(punto_partida.longitud)}'
        depot_str = origin_str
    else:
        origin_str = f'{con_coords[0][1]},{con_coords[0][2]}'
        depot_str = origin_str

    n = len(con_coords)
    # Construir tramos de hasta MAX_WAYPOINTS_PER_REQUEST waypoints cada uno.
    # El "link" entre tramos es el destino de uno y el origen del siguiente; no se repite como waypoint.
    chunks = []
    i = 0
    current_origin = origin_str
    while i < n:
        if i + MAX_WAYPOINTS_PER_REQUEST < n:
            waypoints_chunk = con_coords[i:i + MAX_WAYPOINTS_PER_REQUEST]
            link_point = con_coords[i + MAX_WAYPOINTS_PER_REQUEST]
            dest_str = f'{link_point[1]},{link_point[2]}'
            chunks.append((current_origin, waypoints_chunk, dest_str, link_point[0]))
            current_origin = dest_str
            i += MAX_WAYPOINTS_PER_REQUEST + 1  # el link no va como waypoint en el siguiente tramo
        else:
            waypoints_chunk = con_coords[i:]
            chunks.append((current_origin, waypoints_chunk, depot_str, None))
            break

    all_legs_sec = []
    ordered_rcs = []
    total_duracion_ms = 0
    request_extra_base = f'waypoints_count={len(con_coords)};chunks={len(chunks)}'
    if punto_partida:
        request_extra_base += ';origin=punto_partida'

    for chunk_idx, (orig, waypoints_chunk, dest, link_rc) in enumerate(chunks):
        waypoints_str = 'optimize:true|' + '|'.join(
            f'{lat},{lng}' for _, lat, lng in waypoints_chunk
        )
        params = {
            'origin': orig,
            'destination': dest,
            'waypoints': waypoints_str,
            'key': api_key,
        }
        request_params_safe = {k: ('***' if k == 'key' else v) for k, v in params.items()}
        request_extra = f'{request_extra_base};chunk={chunk_idx + 1}/{len(chunks)}'
        url = f'{DIRECTIONS_URL}?{urlencode(params)}'

        t0 = time.perf_counter()
        try:
            with urlopen(url, timeout=30) as resp:
                data = json.loads(resp.read().decode())
        except Exception as e:
            total_duracion_ms += int((time.perf_counter() - t0) * 1000)
            logger.exception('Error llamando a Google Directions API (chunk %s)', chunk_idx + 1)
            result['error'] = str(e)
            _log_directions_request(
                ruta, request_params_safe, request_extra,
                response_status='ERROR', response_body={'exception': str(e)},
                exito=False, mensaje_error=str(e), duracion_ms=int((time.perf_counter() - t0) * 1000), request=request,
            )
            return result
        chunk_duracion_ms = int((time.perf_counter() - t0) * 1000)
        total_duracion_ms += chunk_duracion_ms

        response_status = data.get('status') or ''
        response_body_log = {
            'status': response_status,
            'waypoint_order': data.get('routes', [{}])[0].get('waypoint_order') if data.get('routes') else None,
            'routes_count': len(data.get('routes') or []),
            'geocoded_waypoints_count': len(data.get('geocoded_waypoints') or []),
        }
        if response_status != 'OK':
            error_msg = data.get('error_message') or response_status or 'Unknown error'
            result['error'] = error_msg
            _log_directions_request(
                ruta, request_params_safe, request_extra,
                response_status=response_status, response_body=response_body_log,
                exito=False, mensaje_error=error_msg, duracion_ms=chunk_duracion_ms, request=request,
            )
            return result

        routes = data.get('routes') or []
        if not routes:
            result['error'] = 'La API no devolvió rutas'
            _log_directions_request(
                ruta, request_params_safe, request_extra,
                response_status=response_status, response_body=response_body_log,
                exito=False, mensaje_error='La API no devolvió rutas', duracion_ms=chunk_duracion_ms, request=request,
            )
            return result

        waypoint_order = routes[0].get('waypoint_order')
        if waypoint_order is not None:
            for idx in waypoint_order:
                ordered_rcs.append(waypoints_chunk[idx][0])
        else:
            for wc in waypoints_chunk:
                ordered_rcs.append(wc[0])
        if link_rc is not None:
            ordered_rcs.append(link_rc)

        legs = routes[0].get('legs') or []
        for leg in legs:
            dur = leg.get('duration') if isinstance(leg, dict) else None
            if isinstance(dur, dict) and 'value' in dur:
                all_legs_sec.append(int(dur['value']))
            else:
                all_legs_sec.append(0)

    # Aplicar orden obtenido
    orden_nuevo = 1
    for rc in ordered_rcs:
        if rc is not None:
            rc.orden_entrega = orden_nuevo
            rc.save(update_fields=['orden_entrega'])
            orden_nuevo += 1

    max_orden = orden_nuevo - 1
    for rc in sin_coords:
        max_orden += 1
        rc.orden_entrega = max_orden
        rc.save(update_fields=['orden_entrega'])

    ruta.duracion_legs_segundos = all_legs_sec
    ruta.save(update_fields=['duracion_legs_segundos'])

    result['optimizados'] = len(con_coords)
    response_body_log = {
        'status': 'OK',
        'waypoint_order': f'{len(chunks)} chunks',
        'routes_count': len(chunks),
        'geocoded_waypoints_count': n,
    }
    _log_directions_request(
        ruta, {'waypoints_count': len(con_coords), 'chunks': len(chunks), 'key': '***'},
        request_extra_base,
        response_status='OK', response_body=response_body_log,
        exito=True, mensaje_error='', duracion_ms=total_duracion_ms, request=request,
    )
    return result


def get_geometria_ruta_calles(puntos):
    """
    Obtiene la geometría del recorrido por calles (no línea recta) para una lista
    ordenada de puntos. Hace requests a Directions API en chunks de hasta 25 waypoints.
    Devuelve una lista de polylines codificados (encoded) para dibujar en el mapa.
    Si hay error o no hay API key, devuelve lista vacía.
    """
    if not puntos or len(puntos) < 2:
        return []
    api_key = (getattr(settings, 'GOOGLE_MAPS_API_KEY', None) or '').strip()
    if not api_key:
        return []
    n = len(puntos)
    polylines = []
    i = 0
    while i < n - 1:
        # Segmento: origin=puntos[i], waypoints=puntos[i+1 : i+26] (máx 25), destination=puntos[i+26] o último
        if i + 26 < n:
            waypoints_list = puntos[i + 1 : i + 26]
            dest_idx = i + 26
        else:
            waypoints_list = puntos[i + 1 : n - 1]
            dest_idx = n - 1
        origin = f"{puntos[i]['lat']},{puntos[i]['lng']}"
        destination = f"{puntos[dest_idx]['lat']},{puntos[dest_idx]['lng']}"
        if waypoints_list:
            waypoints_str = '|'.join(f"{p['lat']},{p['lng']}" for p in waypoints_list)
            params = {'origin': origin, 'destination': destination, 'waypoints': waypoints_str, 'key': api_key}
        else:
            params = {'origin': origin, 'destination': destination, 'key': api_key}
        url = f"{DIRECTIONS_URL}?{urlencode(params)}"
        try:
            with urlopen(url, timeout=15) as resp:
                data = json.loads(resp.read().decode())
        except Exception as e:
            logger.warning('Error obteniendo geometría de ruta por calles: %s', e)
            return polylines
        if data.get('status') != 'OK':
            return polylines
        routes = data.get('routes') or []
        if not routes:
            return polylines
        overview = routes[0].get('overview_polyline') or {}
        encoded = overview.get('points')
        if encoded:
            polylines.append(encoded)
        i = dest_idx
    return polylines

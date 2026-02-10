import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:uuid/uuid.dart';
import '../services/api_service.dart';

/// Repository: fetches context from API, queues events when offline, sends events with request_id.
/// No business logic here - UI uses backend-provided state and allowed_actions.
class CourierRepository extends ChangeNotifier {
  final ApiService _api;
  final List<_QueuedEvent> _queue = [];
  Map<String, dynamic>? _lastContext;
  String? _error;

  CourierRepository(this._api);

  Map<String, dynamic>? get lastContext => _lastContext;
  String? get error => _error;

  /// Fetch courier context (route, stops, current_active_stop_id, allowed_actions).
  Future<void> fetchContext() async {
    _error = null;
    final res = await _api.getCourierContext();
    if (res.ok && res.data != null) {
      _lastContext = res.data;
    } else {
      _error = res.statusCode == 401 ? 'Sesión expirada' : 'No se pudo cargar la ruta';
    }
    notifyListeners();
  }

  /// Send a single event. Uses request_id for idempotency. Offline: queue and try later.
  Future<bool> sendEvent({
    required String type,
    int? stopId,
    Map<String, dynamic>? payload,
  }) async {
    final requestId = const Uuid().v4();
    final res = await _api.postEvent(
      requestId: requestId,
      type: type,
      stopId: stopId,
      payload: payload,
    );
    if (res.ok && res.context != null) {
      _lastContext = res.context;
      _error = null;
      notifyListeners();
      return true;
    }
    if (res.statusCode == 409) {
      _error = res.errorDetail ?? 'Acción no permitida';
      notifyListeners();
      return false;
    }
    if (res.statusCode == 401 || res.statusCode == 403) {
      _error = 'Sesión expirada';
      notifyListeners();
      return false;
    }
    _queue.add(_QueuedEvent(
      requestId: requestId,
      type: type,
      stopId: stopId,
      payload: payload ?? {},
    ));
    notifyListeners();
    return false;
  }

  /// Send location ping (LOCATION_PING) with lat/lon. Backend decides proximity.
  Future<void> sendLocationPing(double latitude, double longitude) async {
    await sendEvent(
      type: 'LOCATION_PING',
      payload: {'latitude': latitude, 'longitude': longitude},
    );
  }

  /// Attempt arrive/deliver/fail - only if backend allows (can_mark_* from context).
  Future<bool> attemptArrive(int stopId, {double? lat, double? lon}) async {
    return sendEvent(
      type: 'ATTEMPT_ARRIVE',
      stopId: stopId,
      payload: lat != null && lon != null ? {'latitude': lat, 'longitude': lon} : null,
    );
  }

  Future<bool> attemptDeliver(int stopId, {double? lat, double? lon}) async {
    return sendEvent(
      type: 'ATTEMPT_DELIVER',
      stopId: stopId,
      payload: lat != null && lon != null ? {'latitude': lat, 'longitude': lon} : null,
    );
  }

  Future<bool> attemptFail(int stopId, {String? reason}) async {
    return sendEvent(
      type: 'ATTEMPT_FAIL',
      stopId: stopId,
      payload: reason != null ? {'reason': reason} : null,
    );
  }

  /// Flush queued events when back online (call after fetchContext succeeds).
  Future<void> flushQueue() async {
    while (_queue.isNotEmpty) {
      final ev = _queue.first;
      final res = await _api.postEvent(
        requestId: ev.requestId,
        type: ev.type,
        stopId: ev.stopId,
        payload: ev.payload.isNotEmpty ? ev.payload : null,
      );
      if (res.ok && res.context != null) {
        _lastContext = res.context;
        _queue.removeAt(0);
      } else {
        break;
      }
    }
    notifyListeners();
  }

  void logout() {
    _api.clearTokens();
    _lastContext = null;
    _queue.clear();
    _error = null;
    notifyListeners();
  }
}

class _QueuedEvent {
  final String requestId;
  final String type;
  final int? stopId;
  final Map<String, dynamic> payload;
  _QueuedEvent({required this.requestId, required this.type, this.stopId, required this.payload});
}

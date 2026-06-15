import 'dart:async';
import 'package:geolocator/geolocator.dart';
import '../repositories/courier_repository.dart';

/// Envía la ubicación GPS del repartidor al backend periódicamente, incluso en
/// segundo plano, mediante un servicio en primer plano de Android (notificación
/// persistente). El backend interpreta cada ping contra la ruta (parada activa,
/// proximidad y check-in automático).
class LocationService {
  StreamSubscription<Position>? _sub;
  DateTime _lastSent = DateTime.fromMillisecondsSinceEpoch(0);
  int _intervalSeconds = 5;

  Position? lastPosition;
  String? statusMessage;

  bool get isRunning => _sub != null;

  Future<bool> _ensureReady() async {
    if (!await Geolocator.isLocationServiceEnabled()) {
      statusMessage = 'Activa el GPS del dispositivo';
      return false;
    }
    var perm = await Geolocator.checkPermission();
    if (perm == LocationPermission.denied) {
      perm = await Geolocator.requestPermission();
    }
    if (perm == LocationPermission.denied || perm == LocationPermission.deniedForever) {
      statusMessage = 'Permiso de ubicación denegado';
      return false;
    }
    return true;
  }

  /// Inicia el envío periódico. Idempotente: si ya está activo, solo actualiza el intervalo.
  Future<bool> start(CourierRepository repo, {int intervalSeconds = 5}) async {
    _intervalSeconds = intervalSeconds < 1 ? 1 : intervalSeconds;
    if (_sub != null) return true;
    if (!await _ensureReady()) return false;

    final settings = AndroidSettings(
      accuracy: LocationAccuracy.high,
      distanceFilter: 0,
      foregroundNotificationConfig: const ForegroundNotificationConfig(
        notificationTitle: 'Entregas en curso',
        notificationText: 'Compartiendo tu ubicación con la central',
        enableWakeLock: true,
      ),
    );
    statusMessage = 'Enviando ubicación';
    _sub = Geolocator.getPositionStream(locationSettings: settings).listen(
      (pos) {
        lastPosition = pos;
        final now = DateTime.now();
        if (now.difference(_lastSent).inSeconds >= _intervalSeconds) {
          _lastSent = now;
          repo.sendLocationPing(pos.latitude, pos.longitude);
        }
      },
      onError: (_) {
        statusMessage = 'Error de GPS';
      },
    );
    return true;
  }

  void updateInterval(int intervalSeconds) {
    _intervalSeconds = intervalSeconds < 1 ? 1 : intervalSeconds;
  }

  Future<void> stop() async {
    await _sub?.cancel();
    _sub = null;
    statusMessage = null;
  }
}

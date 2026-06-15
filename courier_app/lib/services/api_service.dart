import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

/// API client for delivery backend. All business rules live on server;
/// this service only sends requests and returns raw responses.
class ApiService {
  static const _baseUrlKey = 'api_base_url';
  static const _accessKey = 'jwt_access';
  static const _refreshKey = 'jwt_refresh';

  String _baseUrl = 'http://10.0.2.2:8000/api/v1'; // Android emulator -> localhost
  final _client = http.Client();

  ApiService() {
    _loadBaseUrl();
  }

  Future<void> _loadBaseUrl() async {
    final prefs = await SharedPreferences.getInstance();
    _baseUrl = prefs.getString(_baseUrlKey) ?? _baseUrl;
  }

  Future<void> setBaseUrl(String url) async {
    _baseUrl = url.replaceAll(RegExp(r'/$'), '');
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_baseUrlKey, _baseUrl);
  }

  Future<bool> hasStoredTokens() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_accessKey) != null;
  }

  Future<String?> _getAccessToken() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_accessKey);
  }

  Future<void> _saveTokens(String access, String? refresh) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_accessKey, access);
    if (refresh != null) await prefs.setString(_refreshKey, refresh);
  }

  Future<void> clearTokens() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_accessKey);
    await prefs.remove(_refreshKey);
  }

  /// Login: POST /auth/token/ with username & password -> JWT access + refresh
  Future<LoginResult> login(String username, String password) async {
    final uri = Uri.parse('$_baseUrl/auth/token/');
    final res = await _client.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'username': username, 'password': password}),
    );
    if (res.statusCode == 200) {
      final data = jsonDecode(res.body) as Map<String, dynamic>;
      await _saveTokens(
        data['access'] as String,
        data['refresh'] as String?,
      );
      return LoginResult.success;
    }
    return LoginResult.failure;
  }

  Future<Map<String, String>> _authHeaders() async {
    final token = await _getAccessToken();
    return {
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };
  }

  /// GET /courier/context/ -> profile, route, stops, current_active_stop_id, allowed_actions
  Future<CourierContextResponse> getCourierContext() async {
    final uri = Uri.parse('$_baseUrl/courier/context/');
    final res = await _client.get(uri, headers: await _authHeaders());
    if (res.statusCode == 401 || res.statusCode == 403) {
      final refreshed = await _refreshToken();
      if (refreshed) return getCourierContext();
      return CourierContextResponse.unauthorized();
    }
    final data = res.statusCode == 200 ? jsonDecode(res.body) as Map<String, dynamic> : null;
    return CourierContextResponse.fromJson(data, res.statusCode);
  }

  /// GET /courier/config/ -> {auto_checkin, radio_metros, ping_segundos}
  Future<Map<String, dynamic>?> getCourierConfig() async {
    final uri = Uri.parse('$_baseUrl/courier/config/');
    final res = await _client.get(uri, headers: await _authHeaders());
    if (res.statusCode == 401 || res.statusCode == 403) {
      final refreshed = await _refreshToken();
      if (refreshed) return getCourierConfig();
      return null;
    }
    if (res.statusCode == 200) {
      return jsonDecode(res.body) as Map<String, dynamic>;
    }
    return null;
  }

  Future<bool> _refreshToken() async {
    final prefs = await SharedPreferences.getInstance();
    final refresh = prefs.getString(_refreshKey);
    if (refresh == null) return false;
    final uri = Uri.parse('$_baseUrl/auth/refresh/');
    final res = await _client.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'refresh': refresh}),
    );
    if (res.statusCode != 200) return false;
    final data = jsonDecode(res.body) as Map<String, dynamic>;
    await _saveTokens(data['access'] as String, data['refresh'] as String?);
    return true;
  }

  /// POST /events/ with request_id, type, stop_id?, payload. Returns updated context.
  Future<EventResponse> postEvent({
    required String requestId,
    required String type,
    int? stopId,
    Map<String, dynamic>? payload,
  }) async {
    final uri = Uri.parse('$_baseUrl/events/');
    final body = <String, dynamic>{
      'request_id': requestId,
      'type': type,
      'payload': payload ?? {},
    };
    if (stopId != null) body['stop_id'] = stopId;
    final res = await _client.post(
      uri,
      headers: await _authHeaders(),
      body: jsonEncode(body),
    );
    if (res.statusCode == 401 || res.statusCode == 403) {
      final refreshed = await _refreshToken();
      if (refreshed) return postEvent(requestId: requestId, type: type, stopId: stopId, payload: payload);
      return EventResponse.error(res.statusCode, res.body);
    }
    final data = res.statusCode == 200 ? jsonDecode(res.body) as Map<String, dynamic> : null;
    return EventResponse.fromHttp(res.statusCode, data, res.body);
  }

  /// GET /mobile/version/?platform=ANDROID&current_version_code=123
  Future<VersionInfo> getVersionInfo({int? currentVersionCode}) async {
    var path = '$_baseUrl/mobile/version/?platform=ANDROID';
    if (currentVersionCode != null) path += '&current_version_code=$currentVersionCode';
    final uri = Uri.parse(path);
    final res = await _client.get(uri);
    if (res.statusCode != 200) return VersionInfo(updateRequired: false, apkUrl: '');
    final data = jsonDecode(res.body) as Map<String, dynamic>;
    return VersionInfo(
      updateRequired: data['update_required'] as bool? ?? false,
      apkUrl: data['apk_url'] as String? ?? '',
    );
  }
}

enum LoginResult { success, failure }

class CourierContextResponse {
  final bool ok;
  final Map<String, dynamic>? data;
  final int statusCode;

  CourierContextResponse({required this.ok, this.data, this.statusCode = 200});

  factory CourierContextResponse.fromJson(Map<String, dynamic>? json, int statusCode) {
    if (json == null || statusCode != 200) {
      return CourierContextResponse(ok: false, statusCode: statusCode);
    }
    return CourierContextResponse(ok: true, data: json, statusCode: statusCode);
  }

  static CourierContextResponse unauthorized() =>
      CourierContextResponse(ok: false, statusCode: 401);
}

class EventResponse {
  final bool ok;
  final Map<String, dynamic>? context;
  final int statusCode;
  final String? errorDetail;

  EventResponse({required this.ok, this.context, required this.statusCode, this.errorDetail});

  factory EventResponse.fromHttp(int code, Map<String, dynamic>? data, String body) {
    if (code == 200 && data != null) {
      return EventResponse(ok: true, context: data, statusCode: code);
    }
    String? detail;
    try {
      final j = jsonDecode(body);
      if (j is Map<String, dynamic>) detail = j['detail'] as String?;
    } catch (_) {}
    return EventResponse(ok: false, statusCode: code, errorDetail: detail ?? body);
  }

  static EventResponse error(int code, String body) =>
      EventResponse.fromHttp(code, null, body);
}

class VersionInfo {
  final bool updateRequired;
  final String apkUrl;
  VersionInfo({required this.updateRequired, required this.apkUrl});
}

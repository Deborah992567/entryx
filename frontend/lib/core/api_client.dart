/// REST API client with automatic access-token refresh.
///
/// On a 401 it attempts one refresh with the stored refresh token, then retries
/// the original request. If refresh fails, listeners are notified of logout.
library;

import 'dart:convert';

import 'package:http/http.dart' as http;

import 'config.dart';
import 'models.dart';
import 'api_exception.dart';
import 'token_store.dart';

class ApiClient {
  ApiClient({TokenStore? store, http.Client? httpClient})
      : _store = store ?? TokenStore(),
        _http = httpClient ?? http.Client();

  final TokenStore _store;
  final http.Client _http;

  void Function()? onAuthExpired;

  Future<http.Response> _request(
    String method,
    String path, {
    Object? body,
    bool auth = true,
    Map<String, String>? headers,
  }) async {
    final uri = Uri.parse(AppConfig.apiPath(path));
    final request = http.Request(method, uri);

    if (auth) {
      final tokens = await _store.read();
      if (tokens != null) {
        request.headers['Authorization'] = 'Bearer ${tokens.accessToken}';
      }
    }
    if (headers != null) request.headers.addAll(headers);
    if (body != null) {
      request.headers['Content-Type'] = 'application/json';
      request.body = jsonEncode(body);
    }

    final streamed = await _http.send(request);
    var response = await http.Response.fromStream(streamed);

    if (auth && response.statusCode == 401) {
      final refreshed = await _tryRefresh();
      if (refreshed) {
        final tokens = await _store.read();
        request.headers['Authorization'] = 'Bearer ${tokens?.accessToken}';
        final retried = await _http.send(request);
        response = await http.Response.fromStream(retried);
      }
    }
    return response;
  }

  Future<bool> _tryRefresh() async {
    try {
      final tokens = await _store.read();
      if (tokens == null) return false;
      final resp = await _http.post(
        Uri.parse(AppConfig.apiPath('/auth/refresh')),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'refresh_token': tokens.refreshToken}),
      );
      if (resp.statusCode == 200) {
        await _store.storeSession(jsonDecode(resp.body));
        return true;
      }
      await _store.clear();
      onAuthExpired?.call();
      return false;
    } catch (_) {
      return false;
    }
  }

  static Never _throw(http.Response response) {
    String message = response.body;
    String code = 'ERR_HTTP_${response.statusCode}';
    try {
      final detail = jsonDecode(response.body);
      final d = detail is Map ? detail['detail'] : null;
      if (d is Map) {
        code = d['code'] as String? ?? code;
        message = d['message'] as String? ?? message;
      }
    } catch (_) {
      // non-JSON error body
    }
    throw ApiException(statusCode: response.statusCode, code: code, message: message);
  }

  Future<dynamic> get(String path, {bool auth = true}) async {
    final resp = await _request('GET', path, auth: auth);
    if (resp.statusCode != 200) _throw(resp);
    return resp.body.isEmpty ? null : jsonDecode(resp.body);
  }

  Future<dynamic> post(String path, {Object? body, bool auth = true}) async {
    final resp = await _request('POST', path, body: body, auth: auth);
    if (resp.statusCode < 200 || resp.statusCode >= 300) _throw(resp);
    return resp.body.isEmpty ? null : jsonDecode(resp.body);
  }

  Future<dynamic> put(String path, {Object? body, bool auth = true}) async {
    final resp = await _request('PUT', path, body: body, auth: auth);
    if (resp.statusCode < 200 || resp.statusCode >= 300) _throw(resp);
    return resp.body.isEmpty ? null : jsonDecode(resp.body);
  }

  Future<void> delete(String path, {bool auth = true}) async {
    final resp = await _request('DELETE', path, auth: auth);
    if (resp.statusCode >= 300) _throw(resp);
  }

  Future<Health> health() async {
    final data = await get('/health', auth: false);
    return Health.fromJson(data as Map<String, dynamic>);
  }
}

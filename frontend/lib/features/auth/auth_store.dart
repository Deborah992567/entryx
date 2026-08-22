/// Authentication store: session restore, login, register, logout.
library;

import 'package:flutter/foundation.dart';

import '../../core/api_client.dart';
import '../../core/api_exception.dart';
import '../../core/models.dart';
import '../../core/token_store.dart';
import '../../core/ws_client.dart';

enum AuthStatus { unknown, authenticated, unauthenticated }

class AuthStore extends ChangeNotifier {
  AuthStore({required ApiClient api, required TokenStore tokens, required WsClient ws})
      : _api = api,
        _tokens = tokens,
        _ws = ws {
    _api.onAuthExpired = logoutSilently;
  }

  final ApiClient _api;
  final TokenStore _tokens;
  final WsClient _ws;

  AuthStatus _status = AuthStatus.unknown;
  User? _user;
  String? _error;
  bool _busy = false;

  AuthStatus get status => _status;
  User? get user => _user;
  String? get error => _error;
  bool get busy => _busy;
  bool get isAuthenticated => _status == AuthStatus.authenticated;

  /// Restore a persisted session and fetch the profile.
  Future<void> restore() async {
    TokenPair? tokens;
    try {
      tokens = await _tokens.read();
    } catch (_) {
      tokens = null;
    }
    if (tokens == null) {
      _status = AuthStatus.unauthenticated;
      notifyListeners();
      return;
    }
    try {
      final me = await _api.get('/auth/me') as Map<String, dynamic>;
      _user = User.fromJson(me);
      _status = AuthStatus.authenticated;
      _ws.connect();
    } catch (_) {
      await _tokens.clear();
      _status = AuthStatus.unauthenticated;
    }
    notifyListeners();
  }

  Future<bool> login(String email, String password) async {
    _busy = true;
    _error = null;
    notifyListeners();
    try {
      final pair = await _api.post(
        '/auth/login',
        body: {'email': email, 'password': password},
        auth: false,
      );
      await _tokens.storeSession(pair as Map<String, dynamic>);
      final me = await _api.get('/auth/me') as Map<String, dynamic>;
      _user = User.fromJson(me);
      _status = AuthStatus.authenticated;
      _ws.connect();
      return true;
    } on ApiException catch (e) {
      _error = e.message;
      return false;
    } on Exception catch (e) {
      _error = e.toString();
      return false;
    } finally {
      _busy = false;
      notifyListeners();
    }
  }

  Future<bool> register(String email, String password, String name) async {
    _busy = true;
    _error = null;
    notifyListeners();
    try {
      await _api.post(
        '/auth/register',
        body: {'email': email, 'password': password, 'name': name},
        auth: false,
      );
      return await login(email, password);
    } on ApiException catch (e) {
      _error = e.message;
      return false;
    } on Exception catch (e) {
      _error = e.toString();
      return false;
    } finally {
      _busy = false;
      notifyListeners();
    }
  }

  Future<void> logout() async {
    final tokens = await _tokens.read();
    if (tokens != null) {
      try {
        await _api.post('/auth/logout', body: {'refresh_token': tokens.refreshToken});
      } catch (_) {
        // best effort
      }
    }
    await logoutSilently();
  }

  Future<void> logoutSilently() async {
    await _ws.dispose();
    await _tokens.clear();
    _user = null;
    _status = AuthStatus.unauthenticated;
    notifyListeners();
  }
}

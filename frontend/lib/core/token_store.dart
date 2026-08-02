/// Secure persistence of auth tokens (Keychain on macOS, DPAPI on Windows,
/// libsecret on Linux).
library;


import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'models.dart';

class TokenStore {
  TokenStore({FlutterSecureStorage? storage})
      : _storage = storage ?? const FlutterSecureStorage();

  static const _accessKey = 'entryx.access_token';
  static const _refreshKey = 'entryx.refresh_token';

  final FlutterSecureStorage _storage;

  Future<TokenPair?> read() async {
    final access = await _storage.read(key: _accessKey);
    final refresh = await _storage.read(key: _refreshKey);
    if (access == null || refresh == null) return null;
    return TokenPair(accessToken: access, refreshToken: refresh, expiresIn: 0);
  }

  Future<void> write(TokenPair pair) async {
    await _storage.write(key: _accessKey, value: pair.accessToken);
    await _storage.write(key: _refreshKey, value: pair.refreshToken);
  }

  Future<void> clear() async {
    await _storage.delete(key: _accessKey);
    await _storage.delete(key: _refreshKey);
  }

  Future<void> storeSession(dynamic json) async {
    await write(TokenPair.fromJson(json as Map<String, dynamic>));
  }
}

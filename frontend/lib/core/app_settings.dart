/// Application settings store: theme mode, locale, layout preferences.
///
/// Persists user preferences to secure storage so they survive restarts.
library;

import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

enum AppThemeMode { dark, light, system }

class AppSettings extends ChangeNotifier {
  AppSettings({FlutterSecureStorage? storage})
      : _storage = storage ?? const FlutterSecureStorage();

  static const _key = 'entryx.settings';
  final FlutterSecureStorage _storage;

  AppThemeMode _themeMode = AppThemeMode.dark;
  bool _showVolume = true;
  bool _showSpread = true;
  int _defaultCandleCount = 500;
  String _defaultTimeframe = 'H1';

  AppThemeMode get themeMode => _themeMode;
  bool get showVolume => _showVolume;
  bool get showSpread => _showSpread;
  int get defaultCandleCount => _defaultCandleCount;
  String get defaultTimeframe => _defaultTimeframe;

  Future<void> load() async {
    try {
      final raw = await _storage.read(key: _key);
      if (raw == null) return;
      final data = jsonDecode(raw) as Map<String, dynamic>;
      _themeMode = AppThemeMode.values.firstWhere(
        (e) => e.name == data['themeMode'],
        orElse: () => AppThemeMode.dark,
      );
      _showVolume = data['showVolume'] as bool? ?? true;
      _showSpread = data['showSpread'] as bool? ?? true;
      _defaultCandleCount = data['defaultCandleCount'] as int? ?? 500;
      _defaultTimeframe = data['defaultTimeframe'] as String? ?? 'H1';
      notifyListeners();
    } catch (_) {
      // ignore corrupt settings
    }
  }

  Future<void> _save() async {
    final data = {
      'themeMode': _themeMode.name,
      'showVolume': _showVolume,
      'showSpread': _showSpread,
      'defaultCandleCount': _defaultCandleCount,
      'defaultTimeframe': _defaultTimeframe,
    };
    await _storage.write(key: _key, value: jsonEncode(data));
  }

  Future<void> setThemeMode(AppThemeMode mode) async {
    _themeMode = mode;
    notifyListeners();
    await _save();
  }

  Future<void> setShowVolume(bool value) async {
    _showVolume = value;
    notifyListeners();
    await _save();
  }

  Future<void> setShowSpread(bool value) async {
    _showSpread = value;
    notifyListeners();
    await _save();
  }

  Future<void> setDefaultCandleCount(int count) async {
    _defaultCandleCount = count;
    notifyListeners();
    await _save();
  }

  Future<void> setDefaultTimeframe(String tf) async {
    _defaultTimeframe = tf;
    notifyListeners();
    await _save();
  }
}

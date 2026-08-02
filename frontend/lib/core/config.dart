/// Global application configuration.
///
/// The API base URL is configurable at build/run time via the
/// `ENTRYX_API_URL` environment variable (overrides the default).
library;

class AppConfig {
  AppConfig._();

  /// Backend REST + WebSocket base. Defaults to the local FastAPI dev server.
  static String get apiBaseUrl =>
      const String.fromEnvironment('ENTRYX_API_URL', defaultValue: 'http://localhost:8000');

  static String get wsUrl {
    final http = apiBaseUrl.replaceFirst('http://', 'ws://').replaceFirst('https://', 'wss://');
    return '$http/ws';
  }

  static const String appName = 'EntryX';
  static const String appVersion = '0.1.0';

  static String apiPath(String path) => '$apiBaseUrl/api/v1$path';
}

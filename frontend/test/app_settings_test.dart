/// Tests for AppSettings store.
library;

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:entryx/core/app_settings.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
      const MethodChannel('plugins.it_nomads.com/flutter_secure_storage'),
      (call) async => null,
    );
  });

  tearDown(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
      const MethodChannel('plugins.it_nomads.com/flutter_secure_storage'),
      null,
    );
  });

  test('defaults are correct', () {
    final settings = AppSettings();
    expect(settings.themeMode, AppThemeMode.dark);
    expect(settings.showVolume, true);
    expect(settings.showSpread, true);
    expect(settings.defaultCandleCount, 500);
    expect(settings.defaultTimeframe, 'H1');
  });

  test('setThemeMode updates and notifies', () async {
    final settings = AppSettings();
    bool notified = false;
    settings.addListener(() => notified = true);

    await settings.setThemeMode(AppThemeMode.light);
    expect(settings.themeMode, AppThemeMode.light);
    expect(notified, true);
  });

  test('setShowVolume updates value', () async {
    final settings = AppSettings();
    await settings.setShowVolume(false);
    expect(settings.showVolume, false);
  });

  test('setShowSpread updates value', () async {
    final settings = AppSettings();
    await settings.setShowSpread(false);
    expect(settings.showSpread, false);
  });

  test('setDefaultCandleCount updates value', () async {
    final settings = AppSettings();
    await settings.setDefaultCandleCount(1000);
    expect(settings.defaultCandleCount, 1000);
  });

  test('setDefaultTimeframe updates value', () async {
    final settings = AppSettings();
    await settings.setDefaultTimeframe('H4');
    expect(settings.defaultTimeframe, 'H4');
  });
}

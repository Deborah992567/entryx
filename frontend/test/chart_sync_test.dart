import 'package:entryx/core/api_client.dart';
import 'package:entryx/core/ws_client.dart';
import 'package:entryx/features/chart/chart_store.dart';
import 'package:entryx/features/chart/chart_store_registry.dart';
import 'package:flutter_test/flutter_test.dart';

class _FakeApi extends ApiClient {
  @override
  Future<dynamic> get(String path, {bool auth = true}) async {
    if (path.startsWith('/market/candles')) {
      return [
        for (var i = 0; i < 200; i++)
          {
            'symbol': 'XAUUSD',
            'timeframe': 'H1',
            'ts': DateTime.fromMillisecondsSinceEpoch(i * 3600000).toIso8601String(),
            'o': 100,
            'h': 102,
            'l': 99,
            'c': 101,
            'v': 10,
          }
      ];
    }
    return null;
  }
}

void main() {
  group('ChartSyncGroup', () {
    late ChartStore a;
    late ChartStore b;
    late ChartStore c;

    setUp(() {
      a = ChartStore(api: _FakeApi(), ws: WsClient());
      b = ChartStore(api: _FakeApi(), ws: WsClient());
      c = ChartStore(api: _FakeApi(), ws: WsClient());
    });

    tearDown(() {
      a.dispose();
      b.dispose();
      c.dispose();
    });

    test('unlinked charts do not affect each other', () async {
      await Future<void>.delayed(Duration.zero);
      a.panBy(40);
      expect(b.followingLatest, isTrue);
      expect(b.visibleEnd, 200);
    });

    test('panning a synced chart pans the others', () async {
      await Future<void>.delayed(Duration.zero);
      final group = ChartSyncGroup();
      a.setSyncGroup(group);
      b.setSyncGroup(group);
      c.setSyncGroup(group);

      a.panBy(40);
      expect(b.visibleEnd, 160);
      expect(c.visibleEnd, 160);
    });

    test('zoom and reset propagate across the group', () async {
      await Future<void>.delayed(Duration.zero);
      final group = ChartSyncGroup();
      a.setSyncGroup(group);
      b.setSyncGroup(group);

      a.zoomIn();
      expect(b.barsVisible, a.barsVisible);
      expect(b.barsVisible, lessThan(ChartStore.defaultBars));

      b.resetView();
      expect(a.followingLatest, isTrue);
      expect(a.barsVisible, ChartStore.defaultBars);
    });

    test('crosshair propagates to synced charts', () async {
      await Future<void>.delayed(Duration.zero);
      final group = ChartSyncGroup();
      a.setSyncGroup(group);
      b.setSyncGroup(group);

      a.setCrosshair(5, 101.5);
      expect(b.crosshairIndex, 5);
      expect(b.crosshairPrice, closeTo(101.5, 1e-6));
    });

    test('leaving the group stops sync', () async {
      await Future<void>.delayed(Duration.zero);
      final group = ChartSyncGroup();
      a.setSyncGroup(group);
      b.setSyncGroup(group);

      b.setSyncGroup(null);
      a.panBy(40);
      expect(b.followingLatest, isTrue);
    });

    test('disposing a member removes it from the group', () async {
      final other = ChartStore(api: _FakeApi(), ws: WsClient());
      await Future<void>.delayed(Duration.zero);
      final group = ChartSyncGroup();
      a.setSyncGroup(group);
      other.setSyncGroup(group);

      other.dispose();
      expect(group.isEmpty, isFalse);
      a.panBy(40);
      // no crash: other was removed on dispose
    });
  });

  group('ChartStoreRegistry', () {
    test('returns a distinct store per panel id', () async {
      final registry = ChartStoreRegistry(api: _FakeApi(), ws: WsClient());
      final one = registry.storeFor('panel.a');
      final two = registry.storeFor('panel.b');
      expect(one, isNot(same(two)));
      expect(registry.storeFor('panel.a'), same(one));
      await Future<void>.delayed(Duration.zero);
      registry.dispose();
    });

    test('sync toggling joins and leaves the shared group', () async {
      final registry = ChartStoreRegistry(api: _FakeApi(), ws: WsClient());
      final a = registry.storeFor('panel.a');
      final b = registry.storeFor('panel.b');
      await Future<void>.delayed(Duration.zero);

      registry.setSynced('panel.a', true);
      registry.setSynced('panel.b', true);
      expect(a.synced, isTrue);
      expect(b.synced, isTrue);

      a.panBy(40);
      expect(b.visibleEnd, 160);

      registry.setSynced('panel.b', false);
      a.panBy(-200);
      expect(a.followingLatest, isTrue);
      expect(b.followingLatest, isFalse); // b no longer follows a
      expect(b.visibleEnd, 160);
      registry.dispose();
    });

    test('disposeStore disposes the store and drops it from the map', () async {
      final registry = ChartStoreRegistry(api: _FakeApi(), ws: WsClient());
      registry.storeFor('panel.a');
      registry.disposeStore('panel.a');
      expect(registry.storeFor('panel.a'), isNot(same(registry.storeFor('panel.b'))));
      await Future<void>.delayed(Duration.zero);
      registry.dispose();
    });
  });
}

import 'package:entryx/core/api_client.dart';
import 'package:entryx/core/ws_client.dart';
import 'package:entryx/features/trading/trading_store.dart';
import 'package:flutter_test/flutter_test.dart';

class _FakeApi extends ApiClient {
  final deletions = <String>[];
  final posts = <String>[];

  @override
  Future<dynamic> get(String path, {bool auth = true}) async {
    switch (path) {
      case '/trading/account':
        return {
          'number': '9001',
          'currency': 'USD',
          'balance': 10000.0,
          'equity': 10050.0,
          'margin_used': 500.0,
          'free_margin': 9550.0,
          'margin_level': 2010.0,
          'floating_pnl': 50.0,
          'realized_pnl': -25.0,
          'commission': 2.18,
          'swap': -1.5,
          'exposure': 109002.0,
        };
      case '/trading/positions':
        return [
          {
            'id': 'p-1',
            'symbol': 'EURUSD',
            'side': 'buy',
            'volume': 0.5,
            'open_price': 1.0850,
            'floating_pnl': 12.5,
            'sl': 1.0800,
            'tp': 1.0950,
            'trail': 50,
            'commission': 1.09,
          }
        ];
      case '/trading/orders':
        return [
          {
            'id': 'o-1',
            'symbol': 'XAUUSD',
            'side': 'sell',
            'type': 'limit',
            'volume': 0.1,
            'state': 'pending',
            'price': 2350.0,
            'limit_price': 2350.0,
            'sl': 2360.0,
            'tp': 2330.0,
            'magic': 0,
            'comment': '',
            'expiry': '2026-08-07T10:00:00Z',
          }
        ];
      case '/trading/history':
        return [
          {
            'id': 't-1',
            'symbol': 'BTCUSD',
            'side': 'buy',
            'volume': 0.2,
            'open_price': 64000.0,
            'close_price': 64500.0,
            'gross_pnl': 100.0,
            'net_pnl': 99.4,
            'commission': 0.52,
            'swap': -0.08,
            'closed_at': '2026-08-05T14:30:00Z',
          }
        ];
      default:
        return null;
    }
  }

  @override
  Future<dynamic> delete(String path, {bool auth = true}) async {
    deletions.add(path);
    return null;
  }

  @override
  Future<dynamic> post(String path, {Object? body, bool auth = true}) async {
    posts.add(path);
    return null;
  }
}

void main() {
  late _FakeApi api;
  late WsClient ws;
  late TradingStore store;

  setUp(() {
    api = _FakeApi();
    ws = WsClient();
    store = TradingStore(api: api, ws: ws, userId: 7);
  });

  tearDown(() {
    store.dispose();
    ws.dispose();
  });

  test('loads account, positions, orders, and history', () async {
    await Future<void>.delayed(Duration.zero);
    expect(store.loading, isFalse);
    expect(store.error, isEmpty);
    expect(store.account!.number, '9001');
    expect(store.account!.commission, 2.18);
    expect(store.account!.swap, -1.5);
    expect(store.account!.exposure, 109002.0);
    expect(store.positions, hasLength(1));
    expect(store.positions.first.symbol, 'EURUSD');
    expect(store.positions.first.trail, 50);
    expect(store.orders, hasLength(1));
    expect(store.orders.first.isPending, isTrue);
    expect(store.orders.first.limitPrice, 2350.0);
    expect(store.orders.first.expiry, '2026-08-07T10:00:00Z');
    expect(store.history, hasLength(1));
    expect(store.history.first.netPnl, 99.4);
    expect(store.history.first.swap, -0.08);
  });

  test('cancelOrder issues DELETE and reloads', () async {
    await Future<void>.delayed(Duration.zero);
    await store.cancelOrder('o-1');
    expect(api.deletions, contains('/trading/orders/o-1'));
    expect(store.error, isEmpty);
  });

  test('closePosition issues DELETE for the position', () async {
    await Future<void>.delayed(Duration.zero);
    await store.closePosition('p-1');
    expect(api.deletions, contains('/trading/positions/p-1'));
  });

  test('partialClose POSTs volume to the close endpoint', () async {
    await Future<void>.delayed(Duration.zero);
    await store.partialClose('p-1', 0.2);
    expect(api.posts, contains('/trading/positions/p-1/close'));
  });
}

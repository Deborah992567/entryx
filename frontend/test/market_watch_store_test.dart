import 'package:entryx/core/api_client.dart';
import 'package:entryx/core/ws_client.dart';
import 'package:entryx/features/market/market_watch_store.dart';
import 'package:flutter_test/flutter_test.dart';

class _FakeApi extends ApiClient {
  @override
  Future<dynamic> get(String path, {bool auth = true}) async {
    if (path == '/market/symbols') {
      return [
        {'symbol': 'EURUSD', 'name': 'Euro / US Dollar', 'category': 'forex', 'digits': 5},
        {'symbol': 'GBPUSD', 'name': 'British Pound / US Dollar', 'category': 'forex', 'digits': 5},
        {'symbol': 'XAUUSD', 'name': 'Gold Spot', 'category': 'commodity', 'digits': 2},
        {'symbol': 'BTCUSD', 'name': 'Bitcoin', 'category': 'crypto', 'digits': 2},
      ];
    }
    return null;
  }
}

void main() {
  late MarketWatchStore store;

  setUp(() {
    store = MarketWatchStore(api: _FakeApi(), ws: WsClient());
  });

  tearDown(() => store.dispose());

  test('loads symbol catalog from the API', () async {
    await Future<void>.delayed(Duration.zero);
    expect(store.symbols, hasLength(4));
    expect(store.categories, containsAll(['all', 'forex', 'commodity', 'crypto']));
  });

  test('visibleSymbols filters by query', () async {
    await Future<void>.delayed(Duration.zero);
    store.setQuery('usd');
    final symbols = store.visibleSymbols.map((s) => s.symbol).toList();
    expect(symbols, containsAll(['EURUSD', 'GBPUSD', 'BTCUSD', 'XAUUSD']));
  });

  test('visibleSymbols filters by category', () async {
    await Future<void>.delayed(Duration.zero);
    store.setCategory('forex');
    final symbols = store.visibleSymbols.map((s) => s.symbol).toList();
    expect(symbols, containsAll(['EURUSD', 'GBPUSD']));
    expect(symbols, isNot(contains('XAUUSD')));
  });

  test('favorites toggle on and off', () async {
    await Future<void>.delayed(Duration.zero);
    expect(store.isFavorite('XAUUSD'), isFalse);
    store.toggleFavorite('XAUUSD');
    expect(store.isFavorite('XAUUSD'), isTrue);
    store.toggleFavorite('XAUUSD');
    expect(store.isFavorite('XAUUSD'), isFalse);
  });
}

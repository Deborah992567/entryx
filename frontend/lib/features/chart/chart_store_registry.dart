/// Per-panel chart stores.
///
/// Every chart panel owns its own `ChartStore` (symbol, timeframe, viewport,
/// drawings), keyed by the dock panel id. This lets the workspace host
/// multiple independent charts. Charts that opt into the same sync group
/// share viewport + crosshair.
library;

import 'package:flutter/foundation.dart';

import '../../core/api_client.dart';
import '../../core/ws_client.dart';
import 'chart_store.dart';

class ChartStoreRegistry extends ChangeNotifier {
  ChartStoreRegistry({required ApiClient api, required WsClient ws})
      : _api = api,
        _ws = ws;

  final ApiClient _api;
  final WsClient _ws;
  final Map<String, ChartStore> _stores = <String, ChartStore>{};

  /// The default sync group; all synced charts join this one.
  final ChartSyncGroup syncGroup = ChartSyncGroup();

  ChartStore storeFor(String panelId) {
    return _stores.putIfAbsent(panelId, () => ChartStore(api: _api, ws: _ws));
  }

  /// Whether the chart at [panelId] is linked to the shared sync group.
  bool isSynced(String panelId) => storeFor(panelId).synced;

  void setSynced(String panelId, bool synced) {
    storeFor(panelId).setSyncGroup(synced ? syncGroup : null);
  }

  void disposeStore(String panelId) {
    final store = _stores.remove(panelId);
    store?.dispose();
    notifyListeners();
  }

  @override
  void dispose() {
    for (final store in _stores.values) {
      store.dispose();
    }
    _stores.clear();
    super.dispose();
  }
}

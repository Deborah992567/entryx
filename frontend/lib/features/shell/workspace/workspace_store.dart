/// Workspace store: holds the current dock layout, persists it to the
/// backend (`chart_layouts`), and restores the user's default on login.
library;

import 'dart:async';

import 'package:flutter/foundation.dart';

import '../../../core/api_client.dart';
import 'dock_layout.dart';

class WorkspaceStore extends ChangeNotifier {
  WorkspaceStore({required ApiClient api}) : _api = api;

  final ApiClient _api;
  DockLayout _layout = DockLayout.defaultLayout();
  List<Map<String, dynamic>> _savedLayouts = const [];
  Timer? _persistTimer;
  bool _loaded = false;

  DockLayout get layout => _layout;
  List<Map<String, dynamic>> get savedLayouts => _savedLayouts;
  bool get loaded => _loaded;

  // ------------------------------------------------------------- mutations

  void resizeChild(String splitId, int childIndex, double deltaPixels, double totalPixels) {
    _apply(_layout.resizeChild(splitId, childIndex, deltaPixels, totalPixels));
  }

  void toggleCollapse(String panelId) {
    _apply(_layout.toggleCollapse(panelId));
  }

  void swapPanel(String splitId, int childIndex, PanelType type) {
    _apply(_layout.swapPanel(splitId, childIndex, type));
  }

  void _apply(DockLayout next) {
    if (next.toJson().toString() == _layout.toJson().toString()) return;
    _layout = next;
    notifyListeners();
    _schedulePersist();
  }

  void _schedulePersist() {
    _persistTimer?.cancel();
    _persistTimer = Timer(const Duration(milliseconds: 600), saveCurrent);
  }

  // -------------------------------------------------------------- backend

  Future<void> load() async {
    try {
      final data = await _api.get('/workspace/layouts') as List;
      _savedLayouts = data.cast<Map<String, dynamic>>();
      final defaultLayout = _savedLayouts
          .where((l) => l['is_default'] == true)
          .firstOrNull;
      if (defaultLayout != null) {
        _layout = DockLayout.fromJson(defaultLayout['layout_json'] as Map<String, dynamic>);
      }
      _loaded = true;
      notifyListeners();
    } catch (e) {
      debugPrint('WorkspaceStore.load failed: $e');
    }
  }

  Future<void> saveCurrent() async {
    try {
      final body = {
        'name': 'default',
        'layout_json': _layout.toJson(),
        'is_default': true,
      };
      await _api.post('/workspace/layouts', body: body);
    } catch (e) {
      debugPrint('WorkspaceStore.save failed: $e');
    }
  }
}

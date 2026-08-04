/// Pure, immutable dock-layout model for the EntryX workspace.
///
/// A layout is a binary-ish tree of `SplitNode`s (rows/columns with flex
/// weights) whose leaves are `PanelNode`s. All mutating operations return a
/// new `DockLayout` — no side effects — so the logic is fully unit-testable
/// without widgets.
library;

enum DockOrientation { horizontal, vertical }

enum PanelType { marketWatch, chart, aiCopilot, terminal, journal, alerts, positions, history }

extension PanelTypeInfo on PanelType {
  String get id => name;
  String get title => switch (this) {
        PanelType.marketWatch => 'Market Watch',
        PanelType.chart => 'Chart',
        PanelType.aiCopilot => 'AI Copilot',
        PanelType.terminal => 'Trading Terminal',
        PanelType.journal => 'Journal',
        PanelType.alerts => 'Alerts',
        PanelType.positions => 'Positions',
        PanelType.history => 'History',
      };
}

sealed class DockNode {
  const DockNode({required this.id});
  final String id;

  DockNode copy();
}

class PanelNode extends DockNode {
  const PanelNode({required super.id, required this.type, this.collapsed = false});

  final PanelType type;
  final bool collapsed;

  @override
  PanelNode copy() => PanelNode(id: id, type: type, collapsed: collapsed);

  PanelNode withCollapsed(bool value) => PanelNode(id: id, type: type, collapsed: value);
}

class DockChild {
  DockChild(this.node, this.flex);
  DockNode node;
  double flex;
}

class SplitNode extends DockNode {
  SplitNode({
    required super.id,
    required this.orientation,
    required List<DockChild> children,
  }) : children = List.of(children);

  final DockOrientation orientation;
  final List<DockChild> children;

  @override
  SplitNode copy() => SplitNode(
        id: id,
        orientation: orientation,
        children: children.map((c) => DockChild(c.node.copy(), c.flex)).toList(),
      );
}

class DockLayout {
  DockLayout(this.root);

  static const minFlex = 0.04;
  static int _idCounter = 0;

  final DockNode root;

  static String _freshId(String prefix) => '$prefix.${_idCounter++}';
  static String _freshPanelId(String sourceId) => 'panel.$sourceId.${_idCounter++}';

  PanelNode? panel(String id) => _findPanel(root, id);

  SplitNode? split(String id) => _findSplit(root, id);

  static PanelNode? _findPanel(DockNode node, String id) {
    if (node is PanelNode && node.id == id) return node;
    if (node is SplitNode) {
      for (final child in node.children) {
        final found = _findPanel(child.node, id);
        if (found != null) return found;
      }
    }
    return null;
  }

  static SplitNode? _findSplit(DockNode node, String id) {
    if (node is SplitNode) {
      if (node.id == id) return node;
      for (final child in node.children) {
        final found = _findSplit(child.node, id);
        if (found != null) return found;
      }
    }
    return null;
  }

  // --------------------------------------------------------------- factory

  /// The classic four-region terminal:
  ///   vertical: [ horizontal: [MarketWatch | Chart | AI Copilot] , Terminal ]
  factory DockLayout.defaultLayout() {
    const chart = PanelNode(id: 'panel.chart', type: PanelType.chart);
    const watch = PanelNode(id: 'panel.marketwatch', type: PanelType.marketWatch);
    const ai = PanelNode(id: 'panel.aicopilot', type: PanelType.aiCopilot);
    const terminal = PanelNode(id: 'panel.terminal', type: PanelType.terminal);

    final upper = SplitNode(
      id: 'split.upper',
      orientation: DockOrientation.horizontal,
      children: [
        DockChild(watch, 0.18),
        DockChild(chart, 0.62),
        DockChild(ai, 0.20),
      ],
    );
    final root = SplitNode(
      id: 'split.root',
      orientation: DockOrientation.vertical,
      children: [
        DockChild(upper, 0.72),
        DockChild(terminal, 0.28),
      ],
    );
    return DockLayout(root);
  }

  // ------------------------------------------------------------- serialize

  factory DockLayout.fromJson(Map<String, dynamic> json) {
    return DockLayout(_nodeFromJson(json['root'] as Map<String, dynamic>));
  }

  static DockNode _nodeFromJson(Map<String, dynamic> json) {
    final id = json['id'] as String;
    switch (json['kind'] as String) {
      case 'panel':
        return PanelNode(
          id: id,
          type: PanelType.values.firstWhere(
            (t) => t.id == json['type'],
            orElse: () => PanelType.chart,
          ),
          collapsed: json['collapsed'] as bool? ?? false,
        );
      case 'split':
        return SplitNode(
          id: id,
          orientation: json['orientation'] == 'vertical'
              ? DockOrientation.vertical
              : DockOrientation.horizontal,
          children: [
            for (final c in json['children'] as List)
              DockChild(
                _nodeFromJson(c['node'] as Map<String, dynamic>),
                (c['flex'] as num).toDouble(),
              ),
          ],
        );
      default:
        throw FormatException('unknown node kind: ${json['kind']}');
    }
  }

  Map<String, dynamic> toJson() => {'root': _nodeToJson(root)};

  static Map<String, dynamic> _nodeToJson(DockNode node) {
    if (node is PanelNode) {
      return {
        'id': node.id,
        'kind': 'panel',
        'type': node.type.id,
        'collapsed': node.collapsed,
      };
    }
    final split = node as SplitNode;
    return {
      'id': split.id,
      'kind': 'split',
      'orientation': split.orientation == DockOrientation.vertical ? 'vertical' : 'horizontal',
      'children': [
        for (final c in split.children)
          {'node': _nodeToJson(c.node), 'flex': c.flex},
      ],
    };
  }

  // -------------------------------------------------------------- queries

  DockNode? findById(String id) => _find(root, id);

  static DockNode? _find(DockNode node, String id) {
    if (node.id == id) return node;
    if (node is SplitNode) {
      for (final child in node.children) {
        final found = _find(child.node, id);
        if (found != null) return found;
      }
    }
    return null;
  }

  /// Path of split children leading to [panelId]; empty if not found.
  List<(DockChild, SplitNode)> pathToPanel(String panelId) {
    final path = <(DockChild, SplitNode)>[];
    void walk(DockNode node) {
      if (node is SplitNode) {
        for (final child in node.children) {
          if (child.node.id == panelId) {
            path.add((child, node));
            return;
          }
          if (child.node is SplitNode) walk(child.node);
        }
      }
    }

    walk(root);
    return path;
  }

  List<PanelNode> get panels {
    final out = <PanelNode>[];
    void walk(DockNode node) {
      if (node is PanelNode) {
        out.add(node);
      } else if (node is SplitNode) {
        for (final c in node.children) {
          walk(c.node);
        }
      }
    }

    walk(root);
    return out;
  }

  // -------------------------------------------------------------- mutators

  /// Resize a split child by [deltaPixels] across a [totalPixels] span.
  /// Returns a new layout with clamped flex weights.
  DockLayout resizeChild(String splitId, int childIndex, double deltaPixels, double totalPixels) {
    if (totalPixels <= 0) return this;
    final delta = deltaPixels / totalPixels;
    return DockLayout(_copyWith(root, (node) {
      if (node is! SplitNode || node.id != splitId || childIndex < 0 || childIndex >= node.children.length) {
        return node;
      }
      if (childIndex + 1 >= node.children.length) return node; // last child has no neighbor
      final children = node.children;
      var before = children[childIndex].flex;
      var after = children[childIndex + 1].flex;
      before += delta;
      after -= delta;
      if (before < minFlex) {
        after -= (minFlex - before);
        before = minFlex;
      }
      if (after < minFlex) {
        before -= (minFlex - after);
        after = minFlex;
      }
      if (before < minFlex || after < minFlex) return node;
      final newChildren = List<DockChild>.of(children);
      newChildren[childIndex] = DockChild(children[childIndex].node, before);
      newChildren[childIndex + 1] = DockChild(children[childIndex + 1].node, after);
      return SplitNode(id: node.id, orientation: node.orientation, children: newChildren);
    }));
  }

  DockLayout toggleCollapse(String panelId) {
    return DockLayout(_copyWith(root, (node) {
      if (node is PanelNode && node.id == panelId) {
        return node.withCollapsed(!node.collapsed);
      }
      return node;
    }));
  }

  /// Swap the panel type at a split child (e.g. turn a chart into a journal).
  DockLayout swapPanel(String splitId, int childIndex, PanelType type) {
    return DockLayout(_copyWith(root, (node) {
      if (node is! SplitNode || node.id != splitId || childIndex < 0 || childIndex >= node.children.length) {
        return node;
      }
      final child = node.children[childIndex];
      if (child.node is! PanelNode) return node;
      final newChildren = List<DockChild>.of(node.children);
      newChildren[childIndex] = DockChild(PanelNode(id: child.node.id, type: type), child.flex);
      return SplitNode(id: node.id, orientation: node.orientation, children: newChildren);
    }));
  }

  /// Split [panelId] into two panels stacked along [orientation]. The original
  /// panel keeps its id; a fresh panel of [type] is added next to it.
  DockLayout splitPanel(String panelId, {required DockOrientation orientation, required PanelType type}) {
    if (root is PanelNode && root.id == panelId) {
      final split = SplitNode(
        id: _freshId('split.$panelId'),
        orientation: orientation,
        children: [
          DockChild(root, 0.5),
          DockChild(PanelNode(id: _freshPanelId(panelId), type: type), 0.5),
        ],
      );
      return DockLayout(split);
    }
    final path = pathToPanel(panelId);
    if (path.isEmpty) return this;
    final (child, parent) = path.first;
    final index = parent.children.indexOf(child);
    if (index < 0) return this;
    final inner = SplitNode(
      id: _freshId('split.$panelId'),
      orientation: orientation,
      children: [
        DockChild(child.node, 0.5),
        DockChild(PanelNode(id: _freshPanelId(panelId), type: type), 0.5),
      ],
    );
    return DockLayout(_copyWith(root, (node) {
      if (node is! SplitNode || node.id != parent.id) return node;
      final newChildren = List<DockChild>.of(node.children);
      newChildren[index] = DockChild(inner, child.flex);
      return SplitNode(id: node.id, orientation: node.orientation, children: newChildren);
    }));
  }

  DockNode _copyWith(DockNode node, DockNode Function(DockNode) transform) {
    final updated = transform(node);
    if (updated is SplitNode) {
      List<DockChild>? newChildren;
      for (var i = 0; i < updated.children.length; i++) {
        final child = updated.children[i];
        final newChildNode = _copyWith(child.node, transform);
        if (!identical(newChildNode, child.node)) {
          newChildren ??= List<DockChild>.of(updated.children);
          newChildren[i] = DockChild(newChildNode, child.flex);
        }
      }
      if (newChildren != null) {
        return SplitNode(
          id: updated.id,
          orientation: updated.orientation,
          children: newChildren,
        );
      }
    }
    return updated;
  }
}

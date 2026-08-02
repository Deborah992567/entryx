/// Recursive workspace renderer.
///
/// Renders a `DockLayout` as nested Rows/Columns with draggable dividers
/// (resize), collapsible panels, and the panel body from the registry.
library;

import 'package:flutter/material.dart';

import '../../../app/theme.dart';
import '../../panels/panels.dart';
import 'dock_layout.dart';
import 'workspace_store.dart';

class WorkspaceView extends StatelessWidget {
  const WorkspaceView({super.key, required this.store});

  final WorkspaceStore store;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: store,
      builder: (context, _) => _renderNode(context, store.layout.root),
    );
  }

  Widget _renderNode(BuildContext context, DockNode node) {
    if (node is PanelNode) {
      return PanelFrame(
        panel: node,
        layout: store.layout,
        onCollapse: () => store.toggleCollapse(node.id),
        onSwap: (type) => _swapTo(node.id, type),
      );
    }
    final split = node as SplitNode;
    final orientation =
        split.orientation == DockOrientation.horizontal ? Axis.horizontal : Axis.vertical;

    final children = <Widget>[];
    for (var i = 0; i < split.children.length; i++) {
      if (i > 0) {
        children.add(_DividerHandle(
          axis: orientation,
          onDrag: (delta, total) =>
              store.resizeChild(split.id, i - 1, delta, total),
        ));
      }
      children.add(Expanded(
        flex: (split.children[i].flex * 1000).round(),
        child: _renderNode(context, split.children[i].node),
      ));
    }

    return orientation == Axis.horizontal
        ? Row(children: children)
        : Column(children: children);
  }

  void _swapTo(String panelId, PanelType type) {
    final layout = store.layout;
    final path = layout.pathToPanel(panelId);
    if (path.isEmpty) return;
    final (child, split) = path.first;
    final index = split.children.indexOf(child);
    store.swapPanel(split.id, index, type);
  }
}

class _DividerHandle extends StatefulWidget {
  const _DividerHandle({required this.axis, required this.onDrag});

  final Axis axis;
  final void Function(double delta, double total) onDrag;

  @override
  State<_DividerHandle> createState() => _DividerHandleState();
}

class _DividerHandleState extends State<_DividerHandle> {
  double _start = 0;
  double _accum = 0;

  void _begin(double pos) {
    _start = pos;
    _accum = 0;
  }

  void _update(double pos, double total) {
    _accum = pos - _start;
    widget.onDrag(_accum, total);
  }

  @override
  Widget build(BuildContext context) {
    final horizontal = widget.axis == Axis.horizontal;
    return LayoutBuilder(
      builder: (context, constraints) {
        final total = horizontal ? constraints.maxWidth : constraints.maxHeight;
        return GestureDetector(
          behavior: HitTestBehavior.opaque,
          onHorizontalDragStart: horizontal ? (d) => _begin(d.localPosition.dx) : null,
          onHorizontalDragUpdate: horizontal ? (d) => _update(d.localPosition.dx, total) : null,
          onVerticalDragStart: horizontal ? null : (d) => _begin(d.localPosition.dy),
          onVerticalDragUpdate: horizontal ? null : (d) => _update(d.localPosition.dy, total),
          child: MouseRegion(
            cursor: horizontal
                ? SystemMouseCursors.resizeLeftRight
                : SystemMouseCursors.resizeUpDown,
            child: Container(
              width: horizontal ? 5 : double.infinity,
              height: horizontal ? double.infinity : 5,
              color: Colors.transparent,
              child: Center(
                child: Container(
                  width: horizontal ? 1 : double.infinity,
                  height: horizontal ? double.infinity : 1,
                  color: Theme.of(context).dividerColor.withValues(alpha: 0.7),
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}

/// Panel chrome: title bar with collapse + panel-swap menu.
class PanelFrame extends StatelessWidget {
  const PanelFrame({
    super.key,
    required this.panel,
    required this.layout,
    required this.onCollapse,
    required this.onSwap,
  });

  final PanelNode panel;
  final DockLayout layout;
  final VoidCallback onCollapse;
  final void Function(PanelType) onSwap;

  @override
  Widget build(BuildContext context) {
    if (panel.collapsed) {
      return InkWell(
        onTap: onCollapse,
        child: Container(
          width: double.infinity,
          height: double.infinity,
          alignment: Alignment.center,
          decoration: const BoxDecoration(
            color: EntryXColors.bgRaised,
            border: Border(right: BorderSide(color: EntryXColors.border)),
          ),
          child: const RotatedBox(
            quarterTurns: 3,
            child: Text('▸', style: TextStyle(color: EntryXColors.textDim, fontSize: 11)),
          ),
        ),
      );
    }

    return Container(
      decoration: const BoxDecoration(
        color: EntryXColors.bg,
        border: Border(top: BorderSide(color: EntryXColors.border)),
      ),
      child: Column(
        children: [
          Container(
            height: 28,
            color: EntryXColors.bgRaised,
            padding: const EdgeInsets.only(left: 8),
            child: Row(
              children: [
                Text(
                  panel.type.title,
                  style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600),
                ),
                const Spacer(),
                _IconAction(
                  icon: Icons.unfold_more,
                  tooltip: 'Collapse',
                  onTap: onCollapse,
                ),
                PopupMenuButton<PanelType>(
                  tooltip: 'Change panel',
                  icon: const Icon(Icons.more_vert, size: 14, color: EntryXColors.textDim),
                  padding: EdgeInsets.zero,
                  itemBuilder: (_) => [
                    for (final type in PanelType.values)
                      if (type != panel.type)
                        PopupMenuItem(value: type, child: Text(type.title)),
                  ],
                  onSelected: onSwap,
                ),
              ],
            ),
          ),
          const Divider(height: 1),
          Expanded(child: buildPanel(panel.type)),
        ],
      ),
    );
  }
}

class _IconAction extends StatelessWidget {
  const _IconAction({required this.icon, required this.tooltip, required this.onTap});

  final IconData icon;
  final String tooltip;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: tooltip,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 6),
          child: Icon(icon, size: 14, color: EntryXColors.textDim),
        ),
      ),
    );
  }
}

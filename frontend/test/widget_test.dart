import 'package:entryx/app/entryx_app.dart';
import 'package:entryx/features/auth/auth_screen.dart';
import 'package:entryx/features/shell/workspace/dock_layout.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('default dock layout produces the four classic panels', () {
    final layout = DockLayout.defaultLayout();
    final ids = <String>{};
    void walk(DockNode node) {
      if (node is PanelNode) {
        ids.add(node.id);
      } else if (node is SplitNode) {
        for (final child in node.children) {
          walk(child.node);
        }
      }
    }

    walk(layout.root);
    expect(ids, contains('panel.chart'));
    expect(ids, contains('panel.marketwatch'));
    expect(ids, contains('panel.aicopilot'));
    expect(ids, contains('panel.terminal'));
  });

  test('toggleCollapse flips a panel and leaves the rest untouched', () {
    final layout = DockLayout.defaultLayout();
    final collapsed = layout.toggleCollapse('panel.chart');
    expect(collapsed.panel('panel.chart')!.collapsed, isTrue);
    expect(collapsed.panel('panel.marketwatch')!.collapsed, isFalse);
    expect(layout.panel('panel.chart')!.collapsed, isFalse);
  });

  test('resizeChild clamps flex weights to the minimum', () {
    final layout = DockLayout.defaultLayout();
    final resized = layout.resizeChild('split.upper', 0, 1000, 1000);
    final watch = resized.panel('panel.marketwatch')!;
    final chart = resized.panel('panel.chart')!;
    final upper = resized.split('split.upper')!;
    final sum = upper.children.fold<double>(0, (acc, c) => acc + c.flex);
    expect(watch.collapsed, isFalse);
    expect(chart.collapsed, isFalse);
    expect(sum, closeTo(1.0, 1e-9));
  });

  testWidgets('app boots to the auth screen when no session exists', (tester) async {
    await tester.pumpWidget(const EntryXApp());
    expect(find.byType(AuthScreen), findsNothing);
    await tester.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 300)));
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.byType(AuthScreen), findsOneWidget);
  });
}

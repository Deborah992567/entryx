import 'package:entryx/features/chart/chart_template.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('all templates have unique ids and a label', () {
    final ids = ChartTemplate.all.map((t) => t.id).toSet();
    expect(ids.length, ChartTemplate.all.length);
    for (final t in ChartTemplate.all) {
      expect(t.label, isNotEmpty);
      expect(t.id, isNotEmpty);
    }
  });

  test('dark is the default template', () {
    expect(ChartTemplate.byId(null), ChartTemplate.dark);
    expect(ChartTemplate.byId('unknown'), ChartTemplate.dark);
  });

  test('byId resolves known templates', () {
    expect(ChartTemplate.byId('ocean'), ChartTemplate.ocean);
    expect(ChartTemplate.byId('light'), ChartTemplate.light);
    expect(ChartTemplate.byId('amber'), ChartTemplate.amber);
    expect(ChartTemplate.byId('mono'), ChartTemplate.mono);
    expect(ChartTemplate.byId('dark'), ChartTemplate.dark);
  });
}

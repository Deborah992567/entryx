/// Chart color templates (themes).
///
/// A template is a named palette for the candle chart: up/down candle and
/// volume colors, the grid, axis text, crosshair, and the accent used for
/// tags/handles/overlay fallback. Templates are pure data, so they can be
/// persisted per panel inside the workspace layout JSON and round-trip.
library;

import 'package:flutter/material.dart';

class ChartTemplate {
  const ChartTemplate({
    required this.id,
    required this.label,
    required this.up,
    required this.down,
    required this.grid,
    required this.axisText,
    required this.crosshair,
    required this.accent,
  });

  final String id;
  final String label;
  final Color up;
  final Color down;
  final Color grid;
  final Color axisText;
  final Color crosshair;
  final Color accent;

  static const dark = ChartTemplate(
    id: 'dark',
    label: 'Dark',
    up: Color(0xFF2ECC71),
    down: Color(0xFFE74C3C),
    grid: Color(0xFF242B36),
    axisText: Color(0xFF8B95A5),
    crosshair: Color(0xFF8B95A5),
    accent: Color(0xFF3B9EFF),
  );

  static const light = ChartTemplate(
    id: 'light',
    label: 'Light',
    up: Color(0xFF1E8E3E),
    down: Color(0xFFC62828),
    grid: Color(0xFFD6DAE1),
    axisText: Color(0xFF5A6472),
    crosshair: Color(0xFF5A6472),
    accent: Color(0xFF1A73E8),
  );

  static const ocean = ChartTemplate(
    id: 'ocean',
    label: 'Ocean',
    up: Color(0xFF00BFA5),
    down: Color(0xFFFF5252),
    grid: Color(0xFF1B2A3A),
    axisText: Color(0xFF90A4AE),
    crosshair: Color(0xFF90A4AE),
    accent: Color(0xFF40C4FF),
  );

  static const amber = ChartTemplate(
    id: 'amber',
    label: 'Amber',
    up: Color(0xFFF1C40F),
    down: Color(0xFFE67E22),
    grid: Color(0xFF2A2620),
    axisText: Color(0xFF9E9484),
    crosshair: Color(0xFF9E9484),
    accent: Color(0xFFF39C12),
  );

  static const mono = ChartTemplate(
    id: 'mono',
    label: 'Mono',
    up: Color(0xFFE0E0E0),
    down: Color(0xFF909090),
    grid: Color(0xFF333333),
    axisText: Color(0xFF9E9E9E),
    crosshair: Color(0xFF9E9E9E),
    accent: Color(0xFFBDBDBD),
  );

  /// All built-in templates, in menu order.
  static const List<ChartTemplate> all = [dark, light, ocean, amber, mono];

  /// Looks up a template by id, falling back to [dark].
  static ChartTemplate byId(String? id) {
    for (final t in all) {
      if (t.id == id) return t;
    }
    return dark;
  }
}

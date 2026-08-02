/// Terminal-style theming: dense, professional dark + light themes.
library;

import 'package:flutter/material.dart';

class EntryXColors {
  EntryXColors._();

  // Dark palette
  static const bg = Color(0xFF0E1116);
  static const bgRaised = Color(0xFF161B22);
  static const bgSunken = Color(0xFF0A0D12);
  static const border = Color(0xFF242B36);
  static const text = Color(0xFFDDE3EA);
  static const textDim = Color(0xFF8B95A5);
  static const accent = Color(0xFF3B9EFF);
  static const accentBright = Color(0xFF6FC0FF);
  static const up = Color(0xFF2ECC71);
  static const down = Color(0xFFE74C3C);
  static const warn = Color(0xFFF1C40F);
  static const gold = Color(0xFFE8C15A);
}

class EntryXTheme {
  EntryXTheme._();

  static ThemeData dark() {
    final base = ThemeData(brightness: Brightness.dark);
    return base.copyWith(
      scaffoldBackgroundColor: EntryXColors.bg,
      colorScheme: const ColorScheme.dark(
        primary: EntryXColors.accent,
        secondary: EntryXColors.accentBright,
        surface: EntryXColors.bgRaised,
        error: EntryXColors.down,
        onSurface: EntryXColors.text,
      ),
      dividerColor: EntryXColors.border,
      textTheme: base.textTheme
          .apply(bodyColor: EntryXColors.text, displayColor: EntryXColors.text)
          .copyWith(
            bodySmall: const TextStyle(fontSize: 11, color: EntryXColors.textDim),
            labelSmall: const TextStyle(fontSize: 10, color: EntryXColors.textDim),
          ),
      appBarTheme: const AppBarTheme(
        backgroundColor: EntryXColors.bgRaised,
        elevation: 0,
        titleTextStyle: TextStyle(color: EntryXColors.text, fontSize: 13, fontWeight: FontWeight.w600),
      ),
      inputDecorationTheme: InputDecorationTheme(
        isDense: true,
        filled: true,
        fillColor: EntryXColors.bgSunken,
        hintStyle: const TextStyle(color: EntryXColors.textDim, fontSize: 12),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(4),
          borderSide: const BorderSide(color: EntryXColors.border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(4),
          borderSide: const BorderSide(color: EntryXColors.border),
        ),
      ),
      dividerTheme: const DividerThemeData(color: EntryXColors.border, thickness: 1),
      tooltipTheme: TooltipThemeData(
        decoration: BoxDecoration(
          color: EntryXColors.bgRaised,
          border: Border.all(color: EntryXColors.border),
        ),
        textStyle: const TextStyle(color: EntryXColors.text, fontSize: 11),
      ),
    );
  }

  static ThemeData light() {
    final base = ThemeData(brightness: Brightness.light);
    const bg = Color(0xFFF4F5F7);
    const bgRaised = Color(0xFFFFFFFF);
    const text = Color(0xFF1B222A);
    const textDim = Color(0xFF5A6472);
    const border = Color(0xFFD6DAE1);
    return base.copyWith(
      scaffoldBackgroundColor: bg,
      colorScheme: const ColorScheme.light(
        primary: EntryXColors.accent,
        secondary: EntryXColors.accentBright,
        surface: bgRaised,
        error: EntryXColors.down,
        onSurface: text,
      ),
      dividerColor: border,
      textTheme: base.textTheme
          .apply(bodyColor: text, displayColor: text)
          .copyWith(
            bodySmall: const TextStyle(fontSize: 11, color: textDim),
            labelSmall: const TextStyle(fontSize: 10, color: textDim),
          ),
      appBarTheme: const AppBarTheme(backgroundColor: bgRaised, elevation: 0),
    );
  }
}

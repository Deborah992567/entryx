/// Chart panel — custom canvas engine surface.
///
/// The Canvas-based chart engine (candles, timeframes, crosshair, drawings)
/// ships in Phase 3. This panel renders the real axis/grid scaffolding and an
/// honest "engine not built" notice instead of fake candles.
library;

import 'package:flutter/material.dart';

import '../../app/theme.dart';

class ChartPanel extends StatelessWidget {
  const ChartPanel({super.key});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        _Toolbar(),
        const Divider(height: 1),
        Expanded(
          child: Stack(
            children: [
              const CustomPaint(
                painter: _GridPainter(),
                size: Size.infinite,
              ),
              const Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.show_chart, color: EntryXColors.textDim, size: 34),
                    SizedBox(height: 8),
                    Text(
                      'Chart engine — Phase 3',
                      style: TextStyle(color: EntryXColors.textDim, fontSize: 13),
                    ),
                    Text(
                      'Candlesticks · timeframes · indicators · drawings',
                      style: TextStyle(color: EntryXColors.textDim, fontSize: 10),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        const Divider(height: 1),
        _PriceScaleLegend(),
      ],
    );
  }
}

class _Toolbar extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return const SizedBox(
      height: 30,
      child: Row(
        children: [
          SizedBox(width: 8),
          Text('XAUUSD', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
          SizedBox(width: 6),
          Text('H1', style: TextStyle(fontSize: 11, color: EntryXColors.textDim)),
          Spacer(),
          Icon(Icons.refresh, size: 14, color: EntryXColors.textDim),
          SizedBox(width: 12),
        ],
      ),
    );
  }
}

class _PriceScaleLegend extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      height: 22,
      padding: const EdgeInsets.symmetric(horizontal: 8),
      child: const Row(
        children: [
          Icon(Icons.candlestick_chart, size: 13, color: EntryXColors.textDim),
          SizedBox(width: 6),
          Text('No data loaded', style: TextStyle(fontSize: 10, color: EntryXColors.textDim)),
        ],
      ),
    );
  }
}

/// Light grid + axes so the chart region reads as a real charting surface.
class _GridPainter extends CustomPainter {
  const _GridPainter();

  @override
  void paint(Canvas canvas, Size size) {
    final grid = Paint()
      ..color = EntryXColors.border.withValues(alpha: 0.5)
      ..strokeWidth = 0.5;

    const hLines = 8;
    const vLines = 16;
    for (var i = 1; i < hLines; i++) {
      final dy = size.height * i / hLines;
      canvas.drawLine(Offset(0, dy), Offset(size.width, dy), grid);
    }
    for (var i = 1; i < vLines; i++) {
      final dx = size.width * i / vLines;
      canvas.drawLine(Offset(dx, 0), Offset(dx, size.height), grid);
    }
  }

  @override
  bool shouldRepaint(covariant _GridPainter oldDelegate) => false;
}

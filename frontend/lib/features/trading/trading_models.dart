/// Trading domain models parsed from the backend API.
///
/// These mirror the JSON produced by `trading_service` (`to_order_out`,
/// `to_position_out`, `to_trade_out`, `account_summary`). Timestamps come
/// through as ISO strings.
library;

class TradingAccount {
  const TradingAccount({
    required this.number,
    required this.currency,
    required this.balance,
    required this.equity,
    required this.marginUsed,
    required this.freeMargin,
    required this.marginLevel,
    required this.floatingPnl,
    required this.realizedPnl,
    this.commission = 0,
    this.swap = 0,
    this.exposure = 0,
  });

  final String number;
  final String currency;
  final double balance;
  final double equity;
  final double marginUsed;
  final double freeMargin;
  final double marginLevel;
  final double floatingPnl;
  final double realizedPnl;
  final double commission;
  final double swap;
  final double exposure;

  factory TradingAccount.fromJson(Map<String, dynamic> json) => TradingAccount(
        number: json['number'] as String? ?? '',
        currency: json['currency'] as String? ?? 'USD',
        balance: _num(json['balance']),
        equity: _num(json['equity']),
        marginUsed: _num(json['margin_used']),
        freeMargin: _num(json['free_margin']),
        marginLevel: _num(json['margin_level']),
        floatingPnl: _num(json['floating_pnl']),
        realizedPnl: _num(json['realized_pnl']),
        commission: _num(json['commission']),
        swap: _num(json['swap']),
        exposure: _num(json['exposure']),
      );
}

class TradingOrder {
  const TradingOrder({
    required this.id,
    required this.symbol,
    required this.side,
    required this.type,
    required this.volume,
    required this.state,
    this.price,
    this.limitPrice,
    this.filledPrice,
    this.sl,
    this.tp,
    this.magic = 0,
    this.comment = '',
    this.expiry,
  });

  final String id;
  final String symbol;
  final String side;
  final String type;
  final double volume;
  final String state;
  final double? price;
  final double? limitPrice;
  final double? filledPrice;
  final double? sl;
  final double? tp;
  final int magic;
  final String comment;
  final String? expiry;

  bool get isPending => state == 'pending';

  factory TradingOrder.fromJson(Map<String, dynamic> json) => TradingOrder(
        id: json['id'] as String,
        symbol: json['symbol'] as String? ?? '',
        side: json['side'] as String? ?? '',
        type: json['type'] as String? ?? '',
        volume: _num(json['volume']),
        state: json['state'] as String? ?? '',
        price: _optNum(json['price']),
        limitPrice: _optNum(json['limit_price']),
        filledPrice: _optNum(json['filled_price']),
        sl: _optNum(json['sl']),
        tp: _optNum(json['tp']),
        magic: (json['magic'] as num?)?.toInt() ?? 0,
        comment: json['comment'] as String? ?? '',
        expiry: json['expiry'] as String?,
      );
}

class TradingPosition {
  const TradingPosition({
    required this.id,
    required this.symbol,
    required this.side,
    required this.volume,
    required this.openPrice,
    required this.floatingPnl,
    this.sl,
    this.tp,
    this.trail,
    this.commission = 0,
  });

  final String id;
  final String symbol;
  final String side;
  final double volume;
  final double openPrice;
  final double floatingPnl;
  final double? sl;
  final double? tp;
  final double? trail;
  final double commission;

  factory TradingPosition.fromJson(Map<String, dynamic> json) => TradingPosition(
        id: json['id'] as String,
        symbol: json['symbol'] as String? ?? '',
        side: json['side'] as String? ?? '',
        volume: _num(json['volume']),
        openPrice: _num(json['open_price']),
        floatingPnl: _num(json['floating_pnl']),
        sl: _optNum(json['sl']),
        tp: _optNum(json['tp']),
        trail: _optNum(json['trail']),
        commission: _num(json['commission']),
      );
}

class TradeRecord {
  const TradeRecord({
    required this.id,
    required this.symbol,
    required this.side,
    required this.volume,
    required this.openPrice,
    required this.closePrice,
    required this.grossPnl,
    required this.netPnl,
    required this.commission,
    required this.closedAt,
    this.swap = 0,
  });

  final String id;
  final String symbol;
  final String side;
  final double volume;
  final double openPrice;
  final double closePrice;
  final double grossPnl;
  final double netPnl;
  final double commission;
  final double swap;
  final String closedAt;

  factory TradeRecord.fromJson(Map<String, dynamic> json) => TradeRecord(
        id: json['id'] as String,
        symbol: json['symbol'] as String? ?? '',
        side: json['side'] as String? ?? '',
        volume: _num(json['volume']),
        openPrice: _num(json['open_price']),
        closePrice: _num(json['close_price']),
        grossPnl: _num(json['gross_pnl']),
        netPnl: _num(json['net_pnl']),
        commission: _num(json['commission']),
        swap: _num(json['swap']),
        closedAt: json['closed_at'] as String? ?? '',
      );
}

double _num(dynamic value) => (value as num?)?.toDouble() ?? 0;

double? _optNum(dynamic value) => value == null ? null : (value as num).toDouble();

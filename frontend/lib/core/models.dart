/// EntryX models shared across stores and panels.
library;

class User {
  const User({
    required this.id,
    required this.email,
    required this.name,
    required this.role,
    this.preferences = const {},
  });

  final int id;
  final String email;
  final String name;
  final String role;
  final Map<String, dynamic> preferences;

  factory User.fromJson(Map<String, dynamic> json) => User(
        id: json['id'] as int,
        email: json['email'] as String? ?? '',
        name: json['name'] as String? ?? '',
        role: json['role'] as String? ?? 'user',
        preferences: json['preferences'] as Map<String, dynamic>? ?? const {},
      );
}

class TokenPair {
  const TokenPair({
    required this.accessToken,
    required this.refreshToken,
    required this.expiresIn,
  });

  final String accessToken;
  final String refreshToken;
  final int expiresIn;

  factory TokenPair.fromJson(Map<String, dynamic> json) => TokenPair(
        accessToken: json['access_token'] as String,
        refreshToken: json['refresh_token'] as String,
        expiresIn: json['expires_in'] as int? ?? 900,
      );
}

class ComponentStatus {
  const ComponentStatus({required this.status, this.detail});

  final String status; // ok | degraded | down
  final Object? detail;

  bool get isOk => status == 'ok';

  factory ComponentStatus.fromJson(Map<String, dynamic> json) => ComponentStatus(
        status: json['status'] as String? ?? 'unknown',
        detail: json['detail'],
      );
}

class Health {
  const Health({required this.status, required this.components});

  final String status;
  final Map<String, ComponentStatus> components;

  factory Health.fromJson(Map<String, dynamic> json) => Health(
        status: json['status'] as String? ?? 'unknown',
        components: (json['components'] as Map<String, dynamic>? ?? {})
            .map((key, value) => MapEntry(
                  key,
                  ComponentStatus.fromJson(value as Map<String, dynamic>),
                )),
      );
}

class SymbolInfo {
  const SymbolInfo({
    required this.symbol,
    required this.name,
    required this.category,
    required this.digits,
    this.baseCurrency = '',
    this.quoteCurrency = '',
    this.tickSize = 0.00001,
  });

  final String symbol;
  final String name;
  final String category;
  final String baseCurrency;
  final String quoteCurrency;
  final int digits;
  final double tickSize;

  factory SymbolInfo.fromJson(Map<String, dynamic> json) => SymbolInfo(
        symbol: json['symbol'] as String,
        name: json['name'] as String? ?? '',
        category: json['category'] as String? ?? '',
        baseCurrency: json['base_currency'] as String? ?? '',
        quoteCurrency: json['quote_currency'] as String? ?? '',
        digits: json['digits'] as int? ?? 5,
        tickSize: (json['tick_size'] as num?)?.toDouble() ?? 0.00001,
      );
}

class Quote {
  const Quote({
    required this.symbol,
    required this.bid,
    required this.ask,
    this.spread = 0,
    this.changePct = 0,
    this.volume = 0,
  });

  final String symbol;
  final double bid;
  final double ask;
  final double spread;
  final double changePct;
  final double volume;

  factory Quote.fromJson(Map<String, dynamic> json) => Quote(
        symbol: json['symbol'] as String? ?? '',
        bid: (json['bid'] as num?)?.toDouble() ?? 0,
        ask: (json['ask'] as num?)?.toDouble() ?? 0,
        spread: (json['spread'] as num?)?.toDouble() ?? 0,
        changePct: (json['change_pct'] as num?)?.toDouble() ?? 0,
        volume: (json['volume'] as num?)?.toDouble() ?? 0,
      );
}

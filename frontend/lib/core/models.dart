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

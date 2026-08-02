# EntryX Database Schema

Managed with Alembic migrations. Production: MariaDB (10.11+/12.x). Development/tests: SQLite.
All tables carry `id` (bigint PK), `created_at`, `updated_at` (UTC). Soft deletes use
`is_active`. No uncontrolled tables — every change ships a migration.

Type mapping used below:

| concept | MariaDB | SQLite (dev) |
|---|---|---|
| bigint pk | `BIGINT AUTO_INCREMENT` | `INTEGER PRIMARY KEY` |
| decimal money/price | `DECIMAL(24,8)` | `NUMERIC(24,8)` |
| json | `JSON` | `TEXT` (JSON-encoded) |
| datetime | `DATETIME(6)` UTC | `DATETIME` |
| varchar | `VARCHAR(n)` | `VARCHAR(n)` |

## Entities

### users
| column | type | notes |
|---|---|---|
| id | bigint pk | |
| email | varchar(255) unique not null | case-insensitive |
| password_hash | varchar(255) not null | Argon2 |
| name | varchar(120) | |
| preferences | json | theme, defaults, risk prefs |
| role | varchar(20) default 'user' | user/admin |
| is_active | bool default true | |
| created_at / updated_at | datetime | |

### refresh_tokens
| column | type | notes |
|---|---|---|
| id | bigint pk | |
| user_id | fk → users | |
| token_hash | varchar(64) not null unique | sha256 of token |
| expires_at | datetime not null | |
| revoked_at | datetime null | |
| ip / user_agent | varchar | audit |

### accounts
| column | type | notes |
|---|---|---|
| id | bigint pk | |
| user_id | fk → users | |
| broker_id | fk → brokers | |
| number | varchar(64) | display id |
| environment | varchar(10) not null | `PAPER` or `LIVE` |
| currency | varchar(8) default 'USD' | |
| balance | decimal(24,8) | |
| leverage | decimal(10,2) default 100 | |
| is_active | bool | |
| settings | json | margin mode, etc. |

LIVE accounts are gated by flags (`is_live_enabled`) and require confirmation.

### brokers
| column | type | notes |
|---|---|---|
| id | bigint pk | |
| name | varchar(80) | e.g. "Paper", "OANDA" |
| adapter_key | varchar(40) unique | provider class key |
| credentials_encrypted | text null | Fernet-encrypted |
| is_active | bool | |

Credentials are never logged and never returned by the API.

### symbols
| column | type | notes |
|---|---|---|
| id | bigint pk | |
| symbol | varchar(32) unique | e.g. XAUUSD |
| name | varchar(160) | |
| category | varchar(32) | forex/indices/commodities/crypto/stocks/synthetic |
| base_currency / quote_currency | varchar(16) | |
| digits | int | price precision |
| contract_size | decimal(20,6) | |
| tick_size / tick_value | decimal(20,8) | |
| is_active | bool | |

### market_data_meta
| column | type | notes |
|---|---|---|
| id | bigint pk | |
| symbol_id | fk → symbols | |
| provider | varchar(40) | |
| timeframe | varchar(8) | |
| first_ts / last_ts | datetime | coverage window |
| candle_count | bigint | |

### candles
| column | type | notes |
|---|---|---|
| id | bigint pk | |
| symbol_id | fk → symbols | |
| timeframe | varchar(8) not null | |
| ts | datetime not null | open time |
| o/h/l/c | decimal(24,8) not null | |
| v | decimal(24,2) default 0 | |
| unique (symbol_id, timeframe, ts) | | upsert |

### ticks
| column | type | notes |
|---|---|---|
| id | bigint pk | |
| symbol_id | fk → symbols | |
| ts | datetime not null | |
| bid / ask | decimal(24,8) | |
| volume | decimal(24,2) default 0 | |
| index (symbol_id, ts) | | |

### orders
| column | type | notes |
|---|---|---|
| id | bigint pk | |
| account_id | fk → accounts | |
| symbol_id | fk → symbols | |
| external_id | varchar(64) | broker-side id |
| side | varchar(8) | buy/sell |
| type | varchar(24) | market/limit/stop/stop_limit |
| volume | decimal(24,8) | |
| entry_price / sl / tp | decimal(24,8) null | |
| price (limit/stop) | decimal(24,8) null | |
| state | varchar(20) | pending/filled/cancelled/expired/rejected |
| magic | int | |
| comment | varchar(255) | |
| expiration_ts | datetime null | |
| fill_price / filled_volume / created_at / updated_at | | |
| index (account_id, state) | | |

### positions
| column | type | notes |
|---|---|---|
| id | bigint pk | |
| account_id | fk → accounts | |
| symbol_id | fk → symbols | |
| external_id | varchar(64) | |
| side | varchar(8) | |
| volume | decimal(24,8) | |
| open_price / sl / tp | decimal(24,8) | |
| commission / swap | decimal(24,8) | |
| opened_at / updated_at | datetime | |
| state | varchar(20) | open/closed |
| index (account_id, state) | | |

### trades (closed positions / history)
| column | type | notes |
|---|---|---|
| id | bigint pk | |
| account_id | fk → accounts | |
| position_id | fk → positions | |
| symbol_id | fk → symbols | |
| side / volume | | |
| open_price / close_price / sl / tp | decimal(24,8) | |
| gross_pnl / net_pnl / commission / swap | decimal(24,8) | |
| opened_at / closed_at | datetime | |
| close_reason | varchar(32) | sl/tp/manual/trailing/expiry |
| magic | int | |
| strategy_id | fk → strategies null | |

### strategies
| column | type | notes |
|---|---|---|
| id | bigint pk | |
| user_id | fk → users | |
| name | varchar(120) | |
| description | text | |
| source_code | text | python or DSL |
| language | varchar(16) default 'python' | |
| params_json | json | defaults + ranges |
| rules_json | json | AI-generated structured rules |
| is_active | bool | |
| risk_profile_json | json | risk limits |

### backtests
| column | type | notes |
|---|---|---|
| id | bigint pk | |
| strategy_id | fk → strategies | |
| user_id | fk → users | |
| symbol / timeframe | | |
| range_json | json | from/to |
| config_json | json | commission/spread/slippage/leverage |
| params_json | json | |
| metrics_json | json | pf, max_dd, sharpe, expectancy, win rate… |
| equity_curve_json | json | |
| trades_json | json | per-trade records |
| status | varchar(20) | running/completed/failed |
| created_at | | |

### chart_layouts
| column | type | notes |
|---|---|---|
| id | bigint pk | |
| user_id | fk → users | |
| name | varchar(120) | |
| layout_json | json not null | dock nodes + panel config |
| is_default | bool default false | |
| created_at / updated_at | | |

### drawings
| column | type | notes |
|---|---|---|
| id | bigint pk | |
| user_id | fk → users | |
| layout_id | fk → chart_layouts null | |
| symbol / timeframe | varchar | |
| kind | varchar(32) | trendline, fib_retr, rectangle… |
| points_json | json | anchors |
| style_json | json | color/width/style |
| created_at / updated_at | | |

### alerts
| column | type | notes |
|---|---|---|
| id | bigint pk | |
| user_id | fk → users | |
| symbol | varchar(32) | |
| kind | varchar(24) | price/indicator/trendline/fvg/bos/liquidity/ai_setup |
| condition_json | json | |
| is_active | bool | |
| last_triggered_at | datetime | |
| created_at | | |

### ai_conversations
| column | type | notes |
|---|---|---|
| id | bigint pk | |
| user_id | fk → users | |
| title | varchar(160) | |
| context_json | json | symbol/tf/selection |
| created_at / updated_at | | |

### ai_messages
| column | type | notes |
|---|---|---|
| id | bigint pk | |
| conversation_id | fk → ai_conversations | |
| role | varchar(16) | user/assistant/system |
| content | text | |
| grounded_json | json null | references to real EntryX data used |
| model | varchar(80) | |
| created_at | | |

### ai_analyses
| column | type | notes |
|---|---|---|
| id | bigint pk | |
| user_id | fk → users | |
| symbol / timeframe | | |
| kind | varchar(40) | chart_explainer/scanner/journal_report |
| input_json | json | features/selection |
| output_json | json | structured findings |
| model | varchar(80) | |
| created_at | | |

### journal_entries
| column | type | notes |
|---|---|---|
| id | bigint pk | |
| user_id | fk → users | |
| trade_id | fk → trades null | |
| notes | text | |
| setup_type | varchar(64) | |
| strategy | varchar(120) | |
| reason_entry / reason_exit | text | |
| emotional_tag | varchar(32) | |
| screenshot_path | varchar(512) | |
| created_at | | |

### audit_logs
| column | type | notes |
|---|---|---|
| id | bigint pk | |
| user_id | fk → users null | |
| action | varchar(120) not null | e.g. auth.login, order.place |
| entity / entity_id | varchar(64) | |
| detail_json | json null | sanitized (never secrets) |
| ip | varchar(64) | |
| created_at | | |

## Conventions

- Money/price columns: `DECIMAL(24,8)`; computed values prefer `Decimal`.
- Every FK is indexed.
- JSON columns keep flexible strategy/layout/AI payloads stable across model iterations.
- Migrations are forward-only; destructive changes require explicit review.

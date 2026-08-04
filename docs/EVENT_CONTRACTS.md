# EntryX Event Contracts (WebSocket)

Transport: WebSocket at `/ws`. Auth: JWT passed as `?token=` query param on connect
(validated before the connection is accepted). One connection per authenticated session.

## Envelope

```json
{
  "type": "market.tick",
  "channel": "market.XAUUSD",
  "data": { ... },
  "ts": 1720000000.123,
  "seq": 42
}
```

- `type`: dotted event name (below).
- `channel`: subscription scope the event belongs to.
- `data`: event payload (schema per type).
- `ts`: server-side epoch seconds (float).
- `seq`: per-channel monotonic sequence for ordering/replay detection.

## Client → Server (subscribe/unsubscribe)

```json
{ "action": "subscribe",  "channels": ["market.XAUUSD", "candles.XAUUSD.H1"] }
{ "action": "unsubscribe", "channels": ["market.XAUUSD"] }
```

Server replies with `{ "type": "system.subscribed", "channel": "..." }` per channel
and `system.error` with `{"code": "...", "message": "..."}` on failure.

## Server → Client event types

### Market
| type | channel | data |
|---|---|---|
| `market.tick` | `market.<symbol>` | `{symbol, bid, ask, spread, last, volume, ts}` |
| `market.candle` | `candles.<symbol>.<tf>` | `{symbol, tf, ts, o, h, l, c, v, closed}` |
| `market.snapshot` | `market.watch` | list of quote summaries for the watch list |

### Trading / account
| type | channel | data |
|---|---|---|
| `account.updated` | `account.<id>` | `{balance, equity, margin, free_margin, margin_level, floating_pnl, realized_pnl}` |
| `order.created` / `order.updated` / `order.cancelled` / `order.expired` | `orders` | Order object (incl. `limit_price`, `expiry`) |
| `order.filled` | `orders` | Filled order object; a `position.opened` follows |
| `position.opened` / `position.updated` / `position.closed` | `positions` | Position object (incl. pnl) |
| `trade.closed` | `history` | Closed trade record |

### System
| type | channel | data |
|---|---|---|
| `system.status` | `system` | `{market_data, broker, ai, db, ws: {...}}` |
| `system.subscribed` / `system.unsubscribed` | `system` | `{channel}` |
| `system.error` | `system` | `{code, message}` |
| `system.ping` / `system.pong` | `system` | `{ts}` (keep-alive) |

### Alerts / AI
| type | channel | data |
|---|---|---|
| `alert.triggered` | `alerts` | Alert object with trigger context |
| `ai.setup` | `ai.scanner` | `{symbol, tf, setup_type, confidence, summary}` |
| `ai.scan.progress` | `ai.scanner` | `{done, total, symbol, tf}` |

## Channels available to subscribers

`market.<symbol>`, `candles.<symbol>.<tf>`, `market.watch`, `account.<id>`,
`orders`, `positions`, `history`, `alerts`, `ai.scanner`, `system`.

## Guarantees

- Events are best-effort but per-channel `seq` is monotonic; clients can detect gaps.
- All account/order/position events are authoritative and emitted post-transaction.
- The hub enforces channel authorization: a user only receives their own account/positions.

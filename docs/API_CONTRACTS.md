# EntryX API Contracts (v1)

All REST endpoints are JSON. Auth uses `Authorization: Bearer <access_token>`.
Errors use a uniform envelope: `{"detail": {"code": "ERR_CODE", "message": "...", "fields": {...}}}`.

Base path: `/api/v1`.

## Auth

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/register` | no | Create user. `{email, password, name}` |
| POST | `/auth/login` | no | `{email, password}` → `{access_token, refresh_token, token_type, expires_in}` |
| POST | `/auth/refresh` | no | `{refresh_token}` → new token pair |
| GET | `/auth/me` | yes | Current user profile + active account(s) |
| POST | `/auth/logout` | yes | Revoke refresh token |

Rate limit: login/register 10/min/IP. Audit log entries written for all auth events.

## Users & workspace

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/users/me` | yes | Profile (alias of `/auth/me`) |
| PUT | `/users/me` | yes | Update name/preferences |
| GET | `/workspace/layouts` | yes | List saved layouts for user |
| POST | `/workspace/layouts` | yes | Create/save layout `{name, layout_json, is_default}` |
| PUT | `/workspace/layouts/{id}` | yes | Update layout |
| DELETE | `/workspace/layouts/{id}` | yes | Delete layout |

## Health & system

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | no | Liveness + component statuses (db, market_data, broker, ai) |
| GET | `/system/status` | yes | Detailed status incl. WS fan-out stats |

## Market data (Phase 2)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/market/symbols` | yes | Symbol list w/ categories |
| GET | `/market/candles?symbol=XAUUSD&tf=H1&limit=1000` | yes | Historical candles |
| GET | `/market/ticks?symbol=XAUUSD&since=...` | yes | Historical ticks |
| GET | `/market/quote?symbol=XAUUSD` | yes | Latest bid/ask/spread |

Real-time: WS `market.<symbol>` channel.

## Trading (Phase 2/4)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/trading/account` | yes | Current paper account summary |
| GET | `/trading/positions` | yes | Open positions |
| GET | `/trading/orders` | yes | Working orders |
| GET | `/trading/history` | yes | Closed trades (paginated) |
| POST | `/trading/orders` | yes | `OrderRequest` (market/pending, SL/TP, magic, comment) |
| PUT | `/trading/orders/{id}` | yes | Modify (SL/TP/price/volume/expiry) |
| DELETE | `/trading/orders/{id}` | yes | Cancel |
| DELETE | `/trading/positions/{id}` | yes | Close position (`{volume?}` for partial) |
| PUT | `/trading/positions/{id}/sl-tp` | yes | Modify SL/TP |

Every order mutation passes through RiskEngine (configurable limits).

## Strategy / Backtest (Phase 5)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET/POST/PUT/DELETE | `/strategies` | yes | Strategy CRUD (source + params) |
| POST | `/backtests` | yes | Run backtest → `{id, metrics, equity_curve, trades}` |
| GET | `/backtests/{id}` | yes | Fetch result |
| POST | `/backtests/{id}/optimize` | yes | Parameter sweep |

## AI (Phase 7/8)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/ai/status` | yes | Provider health + available local models |
| POST | `/ai/chat` | yes | Copilot chat (grounded context) |
| POST | `/ai/analyze/chart` | yes | "Explain this chart" (selection + features) |
| POST | `/ai/scanner/scan` | yes | Multi-symbol scan |
| POST | `/ai/strategy/from-description` | yes | NL → structured strategy rules (compile only) |
| GET | `/ai/journal/report` | yes | Trading-journal analysis report |

## Notifications / Alerts (Phase 4+)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET/POST/PUT/DELETE | `/alerts` | yes | Alert CRUD |

---

## Notable request/response shapes

### Token pair
```json
{ "access_token": "…", "refresh_token": "…", "token_type": "bearer", "expires_in": 900 }
```

### OrderRequest (trading)
```json
{
  "symbol": "XAUUSD",
  "side": "buy",
  "type": "market",
  "volume": 0.1,
  "sl": 2310.0,
  "tp": 2340.0,
  "comment": "FVG retest",
  "magic": 42,
  "expiration_ts": null
}
```

### Layout (workspace)
```json
{
  "name": "default",
  "layout_json": { "nodes": [ { "id": "chart1", "type": "chart", "x":0, "y":0, "w":3, "h":2 } ] },
  "is_default": true
}
```

All trading schemas use decimal-based float-compatible values; positions/orders carry
`entry_price`, `sl`, `tp`, `volume`, `pnl` and lifecycle `status`/`reason` fields.

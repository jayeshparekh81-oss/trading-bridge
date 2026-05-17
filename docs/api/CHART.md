# Chart — API reference

Source: `backend/app/api/chart.py`

Chart module's REST + WebSocket endpoints.

---

### `GET /api/chart/history`

**Summary:** Fetch historical candles for charting.

**Query params:**
- `symbol` — e.g. `NIFTY` / `BANKNIFTY` / `RELIANCE`
- `timeframe` — `1m` / `5m` / `15m` / `1h` / `1d`
- `from` (optional, ISO timestamp) — window start
- `to` (optional, ISO timestamp) — window end

**Response:** `ChartHistoryResponse`
```json
{
  "symbol": "NIFTY",
  "timeframe": "5m",
  "candles": [
    { "timestamp": "...", "open": ..., "high": ..., "low": ..., "close": ..., "volume": ... }
  ]
}
```

**Responses:**
- `200` — Success
- `400` — Invalid symbol or timeframe
- `502` — Upstream Dhan fetch failure (rare)

---

### `GET /api/chart/ws-token`

**Summary:** Mint a short-lived WS token for the chart WebSocket.

**Auth:** Required (JWT). Token has ~15 min TTL.

**Response:** `WsTokenResponse { token, expires_at }`

---

### `WebSocket /ws/chart/{symbol}/{timeframe}`

**Summary:** Live tick stream + partial candle updates.

**Auth:** Pass `?token=<ws-token>` from /api/chart/ws-token.

**Message types** (server → client):
- `tick` — single trade tick
- `candle_partial` — current bar's running close
- `candle_closed` — finalised bar emitted at boundary
- `error` — structured error event

5-min reconnect threshold triggers `BROKER_DISCONNECTED` event per
`docs/architecture.md`.

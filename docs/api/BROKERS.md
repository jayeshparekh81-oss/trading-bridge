# Brokers — API reference

Source: `backend/app/api/brokers.py`

Multi-broker integration (Fyers + Dhan live; Zerodha + Upstox in flight).

---

### `GET /api/brokers/fyers/connect`

**Summary:** Initiate Fyers OAuth flow.

**Auth:** Required.

**Response:** redirect to Fyers OAuth consent.

---

### `GET /api/brokers/fyers/callback`

**Summary:** Fyers OAuth callback. NOT called by customer directly —
Fyers redirects here with `code` + `state`.

**Query params:** `code`, `state`

**Response:** Stores encrypted credentials, redirects to settings page.

---

### `POST /api/brokers/dhan/connect`

**Summary:** Connect Dhan account via static client_id / access_token.

**Auth:** Required.

**Request body:**
```json
{ "client_id": "...", "access_token": "..." }
```

**Responses:**
- `200` — Credentials stored encrypted (Fernet)
- `400` — Invalid credentials (token verification with Dhan failed)

---

### `GET /api/brokers/dhan/status`

**Summary:** Current Dhan connection state.

**Auth:** Required.

**Response:** `DhanStatusResponse`
```json
{
  "connected": true,
  "client_id_masked": "10****567",
  "last_verified_at": "...",
  "token_expires_at": "..."
}
```

---

### Cross-references

- Encrypted credential storage:
  `backend/app/db/models/broker_credential.py`
- Fyers SDK wrapper: `backend/app/brokers/fyers.py`
- Dhan SDK wrapper: `backend/app/brokers/dhan.py`
- Broker auto-disconnect events: per `docs/architecture.md`

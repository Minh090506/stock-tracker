# API Reference

Base URL: `http://localhost:8000` (direct) or `http://localhost` (via Nginx)

## REST Endpoints

### System

#### `GET /health`

Health check with database status.

```json
{
  "status": "healthy",
  "database": "connected",
  "uptime_seconds": 3600
}
```

Returns `503` if database is unavailable (app still serves real-time data).

#### `GET /api/vn30-components`

List VN30 component stock symbols.

```json
["ACB", "BCM", "BID", "BVH", "CTG", "FPT", "GAS", "GVR", "HDB", "HPG",
 "MBB", "MSN", "MWG", "PLX", "POW", "SAB", "SHB", "SSB", "SSI", "STB",
 "TCB", "TPB", "VCB", "VHM", "VIB", "VIC", "VJC", "VNM", "VPB", "VRE"]
```

#### `GET /metrics`

Prometheus metrics endpoint. Exposes counters, histograms, and gauges for:
- `ssi_messages_total` — SSI messages processed by type
- `ws_connections_active` — Active WebSocket connections by channel
- `ws_messages_sent_total` — Messages sent per channel
- `trade_classification_seconds` — Trade classification latency histogram
- `db_batch_write_seconds` — Database batch write latency

---

### Market Data

#### `GET /api/market/snapshot`

Full market data snapshot (quotes + indices + foreign summary + derivatives).

**Response** (truncated):
```json
{
  "quotes": {
    "FPT": {
      "symbol": "FPT",
      "price": 135500,
      "change": 2500,
      "change_pct": 1.88,
      "volume": 5234100,
      "bid": [135400, 135300, 135200],
      "ask": [135500, 135600, 135700],
      "bid_vol": [1200, 800, 500],
      "ask_vol": [900, 1100, 600],
      "ceiling": 142100,
      "floor": 123500,
      "ref": 133000
    }
  },
  "indices": {
    "VN30": {"value": 1285.5, "change": 12.3, "change_pct": 0.97, "volume": 234567890},
    "VNINDEX": {"value": 1312.8, "change": 8.7, "change_pct": 0.67, "volume": 567890123}
  },
  "foreign": {
    "aggregate": {"total_buy_vol": 12345678, "total_sell_vol": 9876543, "net_vol": 2469135},
    "top_buy": [{"symbol": "VNM", "buy_vol": 456789, "net_vol": 234567}],
    "top_sell": [{"symbol": "HPG", "sell_vol": 345678, "net_vol": -123456}]
  },
  "derivatives": {
    "contract": "VN30F2603",
    "price": 1287.0,
    "basis": 1.5,
    "open_interest": 45678
  }
}
```

#### `GET /api/market/foreign-detail`

Per-symbol foreign investor data for all VN30 stocks.

**Response**:
```json
{
  "FPT": {
    "symbol": "FPT",
    "buy_vol": 123456,
    "sell_vol": 98765,
    "net_vol": 24691,
    "speed": 1234.5,
    "acceleration": 56.7,
    "last_updated": "2026-02-11T10:30:00+07:00"
  }
}
```

#### `GET /api/market/volume-stats`

Per-symbol active buy/sell session stats.

**Response**:
```json
{
  "FPT": {
    "symbol": "FPT",
    "total_buy_vol": 2345678,
    "total_sell_vol": 1987654,
    "total_neutral_vol": 456789,
    "sessions": {
      "ATO": {"buy_vol": 234567, "sell_vol": 198765, "neutral_vol": 45678},
      "Continuous": {"buy_vol": 1890123, "sell_vol": 1567890, "neutral_vol": 345678},
      "ATC": {"buy_vol": 220988, "sell_vol": 220999, "neutral_vol": 65433}
    }
  }
}
```

#### `GET /api/market/basis-trend`

Historical basis points (futures - spot spread).

**Query params**:
| Param | Default | Description |
|-------|---------|-------------|
| `minutes` | `30` | Lookback window in minutes |

**Response**:
```json
[
  {"time": "2026-02-11T10:00:00+07:00", "basis": 1.2},
  {"time": "2026-02-11T10:00:30+07:00", "basis": 1.5},
  {"time": "2026-02-11T10:01:00+07:00", "basis": 0.8}
]
```

#### `GET /api/market/alerts`

Real-time alerts (filterable).

**Query params**:
| Param | Default | Description |
|-------|---------|-------------|
| `limit` | `50` | Max alerts returned |
| `type` | *(all)* | Filter: `VOLUME_SPIKE`, `PRICE_BREAKOUT`, `FOREIGN_ACCELERATION`, `BASIS_DIVERGENCE` |
| `severity` | *(all)* | Filter: `WARNING`, `CRITICAL` |

**Response**:
```json
[
  {
    "id": "alert-uuid-1",
    "type": "VOLUME_SPIKE",
    "severity": "CRITICAL",
    "symbol": "HPG",
    "message": "HPG volume 5.2x above 5-min average",
    "value": 5.2,
    "timestamp": "2026-02-11T10:15:30+07:00"
  }
]
```

---

### Historical Data

All history endpoints require TimescaleDB. Returns `503` if database unavailable.

#### `GET /api/history/{symbol}/candles`

1-minute OHLCV candles.

**Query params**:
| Param | Default | Description |
|-------|---------|-------------|
| `start` | *(required)* | Start date `YYYY-MM-DD` |
| `end` | *(required)* | End date `YYYY-MM-DD` |

**Response**:
```json
[
  {
    "time": "2026-02-11T09:15:00+07:00",
    "open": 135000, "high": 135500, "low": 134800, "close": 135200,
    "volume": 123456, "buy_volume": 67890, "sell_volume": 55566
  }
]
```

#### `GET /api/history/{symbol}/ticks`

Trade tick history.

**Query params**:
| Param | Default | Description |
|-------|---------|-------------|
| `start` | *(required)* | Start date |
| `end` | *(required)* | End date |
| `limit` | `10000` | Max rows |

#### `GET /api/history/{symbol}/foreign`

Foreign flow snapshots.

**Query params**: `start`, `end` (same as candles)

#### `GET /api/history/{symbol}/foreign/daily`

Daily aggregated foreign summary.

**Query params**:
| Param | Default | Description |
|-------|---------|-------------|
| `days` | `30` | Number of trading days |

#### `GET /api/history/index/{index_name}`

Index value history. `index_name`: `VN30` or `VNINDEX`.

**Query params**: `start`, `end`

#### `GET /api/history/derivatives/{contract}`

Futures contract history. `contract`: e.g. `VN30F2603`.

**Query params**: `start`, `end`

---

## WebSocket Endpoints

Connection: `ws://localhost:8000/ws/{channel}?token={auth_token}`

### Authentication

| Env Var | Behavior |
|---------|----------|
| `WS_AUTH_TOKEN` empty | No auth required (development) |
| `WS_AUTH_TOKEN` set | Token required as `?token=` query param |

### Rate Limiting

| Setting | Default | Description |
|---------|---------|-------------|
| `WS_MAX_CONNECTIONS_PER_IP` | `5` | Max connections per client IP |
| `WS_QUEUE_SIZE` | `50` | Per-client message buffer |
| `WS_THROTTLE_INTERVAL_MS` | `500` | Min interval between broadcasts |
| `WS_HEARTBEAT_INTERVAL` | `30.0` | Ping interval (seconds) |
| `WS_HEARTBEAT_TIMEOUT` | `10.0` | Pong timeout (seconds) |

### Channel: `/ws/market`

Full market snapshot (same structure as `GET /api/market/snapshot`). Broadcast every 500ms (trailing-edge throttle).

### Channel: `/ws/foreign`

Foreign investor summary only.

```json
{
  "aggregate": {"total_buy_vol": 12345678, "total_sell_vol": 9876543, "net_vol": 2469135},
  "top_buy": [...],
  "top_sell": [...]
}
```

### Channel: `/ws/index`

Index data only.

```json
{
  "VN30": {"value": 1285.5, "change": 12.3, "change_pct": 0.97},
  "VNINDEX": {"value": 1312.8, "change": 8.7, "change_pct": 0.67}
}
```

### Channel: `/ws/alerts`

Real-time analytics alerts. Pushed immediately on detection (no throttle).

```json
{
  "id": "alert-uuid",
  "type": "FOREIGN_ACCELERATION",
  "severity": "WARNING",
  "symbol": "VCB",
  "message": "VCB foreign buying acceleration detected",
  "value": 2.3,
  "timestamp": "2026-02-11T10:15:30+07:00"
}
```

### Client Example (JavaScript)

```javascript
const ws = new WebSocket('ws://localhost/ws/market?token=your-token');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Market update:', data);
};

ws.onclose = (event) => {
  console.log('Disconnected, reconnecting in 3s...');
  setTimeout(() => connect(), 3000);
};
```

### Reconnection Strategy

The frontend `useWebSocket` hook implements:
1. Auto-reconnect with exponential backoff (1s → 2s → 4s → ... → 30s max)
2. After 3 failed reconnects, falls back to REST polling (10s interval)
3. Resumes WebSocket on next successful connection

---

## Error Responses

All endpoints return standard error format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

| Status | Meaning |
|--------|---------|
| `400` | Bad request (invalid params) |
| `401` | Unauthorized (invalid WS token) |
| `429` | Too many connections (rate limited) |
| `503` | Database unavailable (history endpoints) |

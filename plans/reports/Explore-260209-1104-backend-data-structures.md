# Backend Data Structures Scout Report

**Date:** 2026-02-09  
**Scope:** Backend data models, REST endpoints, WebSocket channels, and service layer architecture

## Executive Summary

The stock-tracker backend uses a clean, layered architecture:
1. **SSI Models** (raw WebSocket) → **Pydantic domain models** → **API/WebSocket responses**
2. **MarketDataProcessor** orchestrates all data processing with per-service callbacks
3. **Data Publisher** bridges SSI stream events to WebSocket channels via event-driven throttled push
4. Three main WebSocket channels: `/ws/market`, `/ws/foreign`, `/ws/index`

---

## 1. MarketSnapshot Data Structure

**Source:** `/backend/app/models/domain.py:134-141`

The unified response from `/api/market/snapshot` and `/ws/market` channel:

```python
class MarketSnapshot(BaseModel):
    quotes: dict[str, "SessionStats"] = {}
    indices: dict[str, IndexData] = {}
    foreign: ForeignSummary | None = None
    derivatives: DerivativesData | None = None
```

**Field Breakdown:**
- **quotes**: Dictionary mapping symbol (str) → SessionStats object
- **indices**: Dictionary mapping index_id (str) → IndexData object
- **foreign**: Optional ForeignSummary (aggregate flow across all symbols)
- **derivatives**: Optional DerivativesData (VN30F futures snapshot)

---

## 2. QuoteCache Data Structure

**Source:** `/backend/app/services/quote_cache.py`

Stores **raw SSIQuoteMessage** per symbol (NOT domain SessionStats):

```python
class QuoteCache:
    def __init__(self):
        self._cache: dict[str, SSIQuoteMessage] = {}
    
    def get_bid_ask(self, symbol: str) -> tuple[float, float]:
        """Returns (bid_price_1, ask_price_1). (0, 0) if not yet cached."""
        q = self._cache.get(symbol)
        return (q.bid_price_1, q.ask_price_1) if q else (0.0, 0.0)
    
    def get_price_refs(self, symbol: str) -> tuple[float, float, float]:
        """Returns (ref_price, ceiling, floor) for VN market color coding."""
        q = self._cache.get(symbol)
        return (q.ref_price, q.ceiling, q.floor) if q else (0.0, 0.0, 0.0)
```

**SSIQuoteMessage Fields** (`/backend/app/models/ssi_messages.py:23-45`):
- `symbol` (str)
- `exchange` (str)
- `ceiling` (float) — price ceiling
- `floor` (float) — price floor
- `ref_price` (float) — reference price for market color
- `open` (float)
- `high` (float)
- `low` (float)
- `bid_price_1`, `bid_vol_1` (float, int)
- `ask_price_1`, `ask_vol_1` (float, int)
- `bid_price_2`, `bid_vol_2` (float, int)
- `ask_price_2`, `ask_vol_2` (float, int)
- `bid_price_3`, `bid_vol_3` (float, int)
- `ask_price_3`, `ask_vol_3` (float, int)

**Purpose:** Used by TradeClassifier to look up bid/ask prices for trade classification (mua_chu_dong/ban_chu_dong).

---

## 3. SessionStats Data Structure

**Source:** `/backend/app/models/domain.py:31-42`

Per-symbol active buy/sell classification aggregates:

```python
class SessionStats(BaseModel):
    symbol: str
    mua_chu_dong_volume: int = 0
    mua_chu_dong_value: float = 0.0
    ban_chu_dong_volume: int = 0
    ban_chu_dong_value: float = 0.0
    neutral_volume: int = 0
    total_volume: int = 0
    last_updated: datetime | None = None
```

**Field Breakdown:**
- **symbol** — stock symbol (e.g., "VNM")
- **mua_chu_dong_volume** — cumulative "active buy" volume for session
- **mua_chu_dong_value** — cumulative "active buy" value for session
- **ban_chu_dong_volume** — cumulative "active sell" volume for session
- **ban_chu_dong_value** — cumulative "active sell" value for session
- **neutral_volume** — cumulative neutral trades (no clear buy/sell signal)
- **total_volume** — sum of all three types
- **last_updated** — timestamp of last trade update

**Source:** SessionAggregator accumulates ClassifiedTrade objects into SessionStats

---

## 4. REST Endpoint `/api/market/snapshot`

**Source:** `/backend/app/routers/market_router.py:11-16`

```python
@router.get("/snapshot")
async def get_snapshot():
    """Full market snapshot: quotes + indices + foreign + derivatives."""
    from app.main import processor
    return processor.get_market_snapshot()
```

**Response Format:** JSON serialization of MarketSnapshot:

```json
{
  "quotes": {
    "VNM": {
      "symbol": "VNM",
      "mua_chu_dong_volume": 12345,
      "mua_chu_dong_value": 123456789.5,
      "ban_chu_dong_volume": 11000,
      "ban_chu_dong_value": 110000000.0,
      "neutral_volume": 5000,
      "total_volume": 28345,
      "last_updated": "2026-02-09T10:30:45.123Z"
    },
    "HPG": { ... },
    ...
  },
  "indices": {
    "VN30": {
      "index_id": "VN30",
      "value": 1234.56,
      "prior_value": 1233.10,
      "change": 1.46,
      "ratio_change": 0.12,
      "total_volume": 123456789,
      "advances": 20,
      "declines": 10,
      "no_changes": 0,
      "intraday": [...],
      "last_updated": "2026-02-09T10:30:45.123Z",
      "advance_ratio": 0.667
    },
    "VNINDEX": { ... }
  },
  "foreign": {
    "total_buy_value": 987654321.5,
    "total_sell_value": 876543210.0,
    "total_net_value": 111111111.5,
    "total_buy_volume": 1234567,
    "total_sell_volume": 1100000,
    "total_net_volume": 134567,
    "top_buy": [...],
    "top_sell": [...]
  },
  "derivatives": {
    "symbol": "VN30F2602",
    "last_price": 1235.0,
    "change": 1.5,
    "change_pct": 0.12,
    "volume": 123456,
    "bid_price": 1234.5,
    "ask_price": 1235.5,
    "basis": 0.44,
    "basis_pct": 0.036,
    "is_premium": true,
    "last_updated": "2026-02-09T10:30:45.123Z"
  }
}
```

---

## 5. WebSocket `/ws/market` Channel

**Source:** `/backend/app/websocket/router.py:119-123`  
**Data Publisher:** `/backend/app/websocket/data_publisher.py:122-124`

**Sends:** Same JSON as `/api/market/snapshot` (full MarketSnapshot)

**Throttle:** 100ms (configurable via `ws_throttle_interval_ms` setting)

**Delivery Method:** Event-driven reactive push (trailing-edge throttle)
- When processor updates trigger changes, DataPublisher notifies via `notify("market")`
- If broadcast happens within throttle window, a deferred broadcast schedules for latest data
- Always sends the most recent complete state

**Connection Lifecycle:**
1. Client connects with optional `?token=xxx` query param
2. Auth validation (if token configured)
3. Rate limiting per IP (default 10 connections per IP)
4. Heartbeat: `ping` bytes every 30s (configurable)
5. Server broadcasts MarketSnapshot whenever data changes (throttled)
6. Client maintains keep-alive read loop

---

## 6. WebSocket `/ws/foreign` Channel

**Source:** `/backend/app/websocket/router.py:126-130`  
**Data Publisher:** `/backend/app/websocket/data_publisher.py:125-126`

**Sends:** ForeignSummary only (aggregate + top movers)

```python
class ForeignSummary(BaseModel):
    total_buy_value: float = 0.0
    total_sell_value: float = 0.0
    total_net_value: float = 0.0
    total_buy_volume: int = 0
    total_sell_volume: int = 0
    total_net_volume: int = 0
    top_buy: list[ForeignInvestorData] = []
    top_sell: list[ForeignInvestorData] = []
```

**top_buy/top_sell:** 5 symbols with highest/lowest net value

---

## 7. WebSocket `/ws/index` Channel

**Source:** `/backend/app/websocket/router.py:133-137`  
**Data Publisher:** `/backend/app/websocket/data_publisher.py:127-132`

**Sends:** Dictionary of indices (VN30, VNINDEX, HNX)

```python
{
  "VN30": { IndexData },
  "VNINDEX": { IndexData },
  "HNX": { IndexData }
}
```

---

## 8. REST Endpoint `/api/vn30-components`

**Source:** `/backend/app/main.py:124-127`

```python
@app.get("/api/vn30-components")
async def get_vn30():
    """Return cached VN30 component stock symbols."""
    return {"symbols": vn30_symbols}
```

**Response Format:**

```json
{
  "symbols": ["VNM", "HPG", "VCB", "ACB", "MWG", "TCB", "BID", "FPT", ...]
}
```

**Notes:**
- Cached at app startup via `SSIMarketService.fetch_vn30_components()`
- Uses SSI IndexComponents API
- Returns ~30 stock symbols in VN30 index
- Empty list [] if fetch fails at startup

---

## 9. Quote Dict Fields Available in MarketDataProcessor

**Context:** After Quote message received, `quote_cache` stores SSIQuoteMessage

**Accessible via:**
```python
quote_cache.get_bid_ask(symbol)  # → (bid_price_1, ask_price_1)
quote_cache.get_price_refs(symbol)  # → (ref_price, ceiling, floor)
quote_cache.get_quote(symbol)  # → full SSIQuoteMessage
```

**Full SSIQuoteMessage fields:**
- `symbol`, `exchange`
- `ceiling`, `floor`, `ref_price`, `open`, `high`, `low`
- `bid_price_1`, `bid_vol_1`, `ask_price_1`, `ask_vol_1`
- `bid_price_2`, `bid_vol_2`, `ask_price_2`, `ask_vol_2`
- `bid_price_3`, `bid_vol_3`, `ask_price_3`, `ask_vol_3`

---

## 10. MarketDataProcessor Unified API

**Source:** `/backend/app/services/market_data_processor.py`

Public methods that return complete snapshots:

```python
def get_market_snapshot(self) -> MarketSnapshot:
    """All quotes + indices + foreign + derivatives."""
    return MarketSnapshot(
        quotes=self.aggregator.get_all_stats(),
        indices=self.index_tracker.get_all(),
        foreign=self.foreign_tracker.get_summary(),
        derivatives=self.derivatives_tracker.get_data(),
    )

def get_foreign_summary(self) -> ForeignSummary:
    """Aggregate foreign flow across all tracked symbols."""

def get_trade_analysis(self, symbol: str) -> SessionStats:
    """Active buy/sell breakdown for a single symbol."""

def get_derivatives_data(self) -> DerivativesData | None:
    """Current derivatives snapshot."""
```

---

## 11. Key Domain Models Summary

### IndexData
- `index_id` (str): e.g., "VN30"
- `value`, `prior_value`, `change`, `ratio_change` (float)
- `total_volume` (int)
- `advances`, `declines`, `no_changes` (int)
- `intraday` (list[IntradayPoint]) — sparkline for charting
- `advance_ratio` (computed property)

### ForeignInvestorData (per symbol)
- `symbol`, `buy_volume`, `sell_volume`, `net_volume`
- `buy_value`, `sell_value`, `net_value`
- `total_room`, `current_room`
- `buy_speed_per_min`, `sell_speed_per_min` (vol/min over 5-min window)
- `buy_acceleration`, `sell_acceleration` (speed change rate)
- `last_updated`

### DerivativesData (for VN30F)
- `symbol` (e.g., "VN30F2602")
- `last_price`, `change`, `change_pct`
- `volume` (cumulative session)
- `bid_price`, `ask_price`
- `basis` (futures_price - VN30_spot)
- `basis_pct` (basis / VN30_spot * 100)
- `is_premium` (basis > 0)
- `last_updated`

---

## 12. Data Flow Architecture

```
SSI WebSocket Stream
    ↓
Stream demux (X-TRADE, X-QUOTE, R, MI, VN30F) 
    ↓
MarketDataProcessor handlers:
    handle_quote(SSIQuoteMessage)      → QuoteCache
    handle_trade(SSITradeMessage)      → TradeClassifier → SessionAggregator
    handle_foreign(SSIForeignMessage)  → ForeignInvestorTracker
    handle_index(SSIIndexMessage)      → IndexTracker
    (VN30F trades)                     → DerivativesTracker
    ↓
processor.subscribe(publisher.notify)  [event-driven push]
    ↓
DataPublisher._get_channel_data()
    ↓
ConnectionManager.broadcast() → WebSocket clients
```

---

## 13. Serialization Notes

**Format:** All responses use Pydantic `model_dump_json()` for ISO 8601 datetime serialization

**Special handling:**
- Index channel uses `model_dump()` then `json.dumps(..., default=str)` for datetime objects
- Status messages sent as raw JSON strings: `{"type": "status", "connected": true/false}`

---

## Implementation Checklist

- [x] MarketSnapshot structure (quotes, indices, foreign, derivatives)
- [x] QuoteCache data structure (SSIQuoteMessage storage)
- [x] SessionStats fields and lifecycle
- [x] REST /api/market/snapshot serialization
- [x] WebSocket /ws/market channel format
- [x] WebSocket /ws/foreign channel format
- [x] WebSocket /ws/index channel format
- [x] REST /api/vn30-components response
- [x] Quote dict available fields
- [x] MarketDataProcessor unified API
- [x] Domain models (IndexData, ForeignInvestorData, DerivativesData)
- [x] Data flow architecture
- [x] Event-driven throttled publishing mechanism

---

## Notes for Frontend Integration

1. **Polling vs WebSocket:** Frontend should prefer WebSocket over polling to avoid hammering REST
2. **Data is always fresh:** DataPublisher throttles at 100ms but always sends latest complete state
3. **Status messages:** Watch for `{"type": "status", "connected": false}` to detect SSI disconnects
4. **Heartbeat:** Server sends `ping` bytes; client should log but doesn't need to respond
5. **SessionStats is cumulative:** `total_volume` resets at 15:00 VN time daily
6. **Futures basis:** Requires both SSI trades AND index updates to compute (both > 0)
7. **Foreign speed:** Computed over 5-min rolling window; updates every message


# Backend Scout Report: Router Files, Tests & Architecture

**Date:** 2026-02-09  
**Scope:** Backend router files, test patterns, dependencies, service layer, data models  
**Status:** Complete survey of all router endpoints, test infrastructure, and related services

---

## Part 1: Router Files Overview

### Backend Router Structure
- **Location:** `backend/app/routers/`
- **Files:** 3 routers total
  - `market_router.py` (REST API for real-time market data)
  - `history_router.py` (REST API for historical queries)
  - `__init__.py` (empty)

**Note:** WebSocket routing is in `backend/app/websocket/router.py` (separate from REST routers)

---

## Part 2: REST API Endpoints

### Market Router (`/api/market`)
**File:** `/Users/minh/Projects/stock-tracker/backend/app/routers/market_router.py`

| Endpoint | Method | Path | Query Params | Response Model |
|----------|--------|------|--------------|-----------------|
| Full Market Snapshot | GET | `/api/market/snapshot` | None | `MarketSnapshot` |
| Foreign Investor Detail | GET | `/api/market/foreign-detail` | None | `{summary: ForeignSummary, stocks: list[ForeignInvestorData]}` |
| Volume Session Stats | GET | `/api/market/volume-stats` | None | `{stats: list[SessionStats]}` |
| Futures Basis Trend | GET | `/api/market/basis-trend` | `minutes: int` (1-120, default 30) | `list[BasisPoint]` |

**Key implementation pattern:**
- All endpoints import processor instance from `app.main` at runtime
- Call specific tracker methods: `processor.get_market_snapshot()`, `processor.derivatives_tracker.get_basis_trend()`
- Return dict or model_dump() JSON

---

### History Router (`/api/history`)
**File:** `/Users/minh/Projects/stock-tracker/backend/app/routers/history_router.py`

| Endpoint | Method | Path | Query Params | Response |
|----------|--------|------|--------------|----------|
| Candles/OHLCV | GET | `/{symbol}/candles` | `start` (date), `end` (date) | `list[dict]` |
| Tick Data | GET | `/{symbol}/ticks` | `start`, `end`, `limit` (max 50000) | `list[dict]` |
| Foreign Flow | GET | `/{symbol}/foreign` | `start`, `end` | `list[dict]` |
| Foreign Daily Summary | GET | `/{symbol}/foreign/daily` | `days` (max 365, default 30) | `list[dict]` |
| Index History | GET | `/index/{index_name}` | `start`, `end` | `list[dict]` |
| Derivatives History | GET | `/derivatives/{contract}` | `start`, `end` | `list[dict]` |

**Key implementation pattern:**
- Lazy initializes `HistoryService` once from DB pool
- All queries use `asyncio` + `asyncpg` pool
- Symbols uppercased at endpoint level
- All endpoints `async def`

---

## Part 3: WebSocket Endpoints

### Streaming Channels (`app/websocket/router.py`)

| Endpoint | Path | Data Type | Auth | Rate Limit |
|----------|------|-----------|------|-----------|
| Market Data | `/ws/market` | `MarketSnapshot` (full) | Optional token | Per-IP limit |
| Foreign Flow | `/ws/foreign` | `ForeignSummary` (agg only) | Optional token | Per-IP limit |
| Index Data | `/ws/index` | `dict[str, IndexData]` | Optional token | Per-IP limit |

**Connection lifecycle:**
1. Token auth (if enabled)
2. Rate limit check per IP
3. Accept connection → create async queue + sender task
4. Heartbeat loop (ping bytes every N seconds)
5. Read loop (keep-alive)
6. Cleanup: cancel heartbeat, close socket, decrement rate limiter

**Configuration parameters:**
- `ws_auth_token`: Auth token (empty = disabled)
- `ws_max_connections_per_ip`: Max active connections per IP
- `ws_heartbeat_interval`: Seconds between pings
- `ws_heartbeat_timeout`: Seconds to wait for ping send
- `ws_queue_size`: Per-client message queue capacity

---

## Part 4: Test Infrastructure

### Dependencies for Testing
**From `requirements.txt`:**
```
fastapi>=0.115.0
uvicorn[standard]>=0.34.0
pydantic>=2.10.0
pydantic-settings>=2.7.0
websockets>=14.0
ssi-fc-data>=1.0.0
asyncpg>=0.30.0
python-dotenv>=1.0.0
httpx>=0.28.0
```

**Pytest ecosystem (inferred from test files):**
- `pytest` — test runner
- `pytest-asyncio` — async test support (`@pytest.mark.asyncio`)
- `starlette.testclient.TestClient` — sync TestClient for FastAPI
- `unittest.mock` — MagicMock, AsyncMock, patch

**No pytest.ini, setup.cfg, or conftest.py found** (tests can be run with `pytest backend/tests/`)

---

### Test File Locations & Patterns
**Location:** `/Users/minh/Projects/stock-tracker/backend/tests/`

**20 test files identified:**

#### Unit Tests (Data Models & Services)
1. **`test_pydantic_models.py`** (167 lines)
   - Tests SSI message models (SSITradeMessage, SSIQuoteMessage, etc.)
   - Tests domain models (ClassifiedTrade, SessionStats, IndexData, BasisPoint, etc.)
   - Pattern: Direct model instantiation, assertion of fields
   - Example:
     ```python
     def test_full_construction(self):
         msg = SSITradeMessage(symbol="VNM", last_price=85000, last_vol=100)
         assert msg.symbol == "VNM"
         assert msg.last_vol == 100  # per-trade, NOT cumulative
     ```

2. **`test_ssi_market_service.py`** (54 lines)
   - Tests static extraction methods: `_extract_symbols()`, `_extract_data_list()`
   - Pattern: Class methods tested directly; handles null/empty cases
   - Example:
     ```python
     def test_valid_response(self):
         result = {"data": [{"StockSymbol": "VNM", "Exchange": "HOSE"}]}
         symbols = SSIMarketService._extract_symbols(result)
         assert symbols == ["VNM"]
     ```

3. **`test_ssi_field_normalizer.py`**
4. **`test_futures_resolver.py`**
5. **`test_quote_cache.py`**
6. **`test_trade_classifier.py`**
7. **`test_session_aggregator.py`**
8. **`test_foreign_investor_tracker.py`**
9. **`test_index_tracker.py`**
10. **`test_derivatives_tracker.py`**
11. **`test_market_data_processor.py`**

#### Integration Tests (Database & Services)
12. **`test_history_service.py`** (80+ lines)
    - Tests HistoryService query methods against mock asyncpg pool
    - Pattern: Fixture-based async mocks
    - Example:
      ```python
      @pytest.fixture
      def mock_db():
          db = MagicMock(spec=Database)
          db.pool = AsyncMock()
          return db
      
      @pytest.mark.asyncio
      async def test_returns_rows_as_dicts(self, svc, mock_db):
          mock_db.pool.fetch = AsyncMock(return_value=[...])
          result = await svc.get_candles("VNM", date(2026, 2, 1), date(2026, 2, 7))
          assert result[0]["symbol"] == "VNM"
      ```

13. **`test_batch_writer.py`**

#### WebSocket & Endpoint Tests
14. **`test_websocket.py`** (272 lines)
    - Full WebSocket integration test with TestClient
    - Tests: lifecycle, broadcast, channels, heartbeat, data format
    - Pattern: Uses TestClient context manager + threading for parallel clients
    - Example:
      ```python
      def test_connect_adds_client(self, app, market_mgr):
          with patch(_SETTINGS, _mock_settings()):
              with TestClient(app).websocket_connect("/ws/market"):
                  assert market_mgr.client_count == 1
      ```

15. **`test_connection_manager.py`**
16. **`test_websocket_endpoint.py`**
17. **`test_data_publisher.py`**

#### Data Processing Tests
18. **`test_data_processor_integration.py`**
19. **`test_ssi_stream_service.py`**

---

## Part 5: Data Models & Schemas

### SSI Raw Message Models
**File:** `/Users/minh/Projects/stock-tracker/backend/app/models/ssi_messages.py`

```
SSITradeMessage         # X-TRADE channel — per-trade event
  - symbol, exchange, last_price, last_vol (PER-TRADE!), total_vol, total_val
  - change, ratio_change, trading_session

SSIQuoteMessage         # X-QUOTE channel — order book
  - symbol, exchange, ceiling, floor, ref_price, open, high, low
  - bid/ask levels 1-3 (bid_price_1, bid_vol_1, ask_price_1, ask_vol_1, etc.)

SSIForeignMessage       # R channel — foreign investor cumulative
  - symbol, f_buy_vol, f_sell_vol, f_buy_val, f_sell_val
  - total_room, current_room

SSIIndexMessage         # MI channel — index snapshot
  - index_id, index_value, prior_index_value, change, ratio_change
  - total_qtty, total_val, advances, declines, no_changes

SSIBarMessage           # B channel — OHLC bar
  - symbol, time, open, high, low, close, volume
```

---

### Domain Models (Processed Data)
**File:** `/Users/minh/Projects/stock-tracker/backend/app/models/domain.py`

```
TradeType (Enum)
  - MUA_CHU_DONG = "mua_chu_dong"
  - BAN_CHU_DONG = "ban_chu_dong"
  - NEUTRAL = "neutral"

ClassifiedTrade
  - symbol, price, volume (per-trade), value, trade_type
  - bid_price, ask_price, timestamp

SessionStats            # Aggregated per-session stats
  - symbol, mua_chu_dong_volume, mua_chu_dong_value
  - ban_chu_dong_volume, ban_chu_dong_value, neutral_volume
  - total_volume, last_updated

PriceData              # Last trade + reference levels
  - last_price, change, change_pct, ref_price, ceiling, floor

ForeignInvestorData    # Per-symbol foreign tracking
  - symbol, buy_volume, sell_volume, net_volume
  - buy_value, sell_value, net_value, total_room, current_room
  - buy_speed_per_min, sell_speed_per_min, buy_acceleration, sell_acceleration
  - last_updated

ForeignSummary        # VN30 aggregate + top movers
  - total_buy_value, total_sell_value, total_net_value
  - total_buy_volume, total_sell_volume, total_net_volume
  - top_buy (list[ForeignInvestorData]), top_sell (list[ForeignInvestorData])

IntradayPoint         # Single sparkline point
  - timestamp, value

IndexData             # Real-time index snapshot
  - index_id, value, prior_value, change, ratio_change
  - total_volume, advances, declines, no_changes, intraday (list[IntradayPoint])
  - last_updated
  - @computed_field advance_ratio = advances / (advances + declines)

BasisPoint           # Futures-spot basis
  - timestamp, futures_symbol, futures_price, spot_value
  - basis, basis_pct, is_premium

DerivativesData      # Real-time VN30F snapshot
  - symbol, last_price, change, change_pct, volume
  - bid_price, ask_price, basis, basis_pct, is_premium, last_updated

MarketSnapshot       # Unified API response
  - quotes: dict[str, SessionStats]
  - prices: dict[str, PriceData]
  - indices: dict[str, IndexData]
  - foreign: ForeignSummary | None
  - derivatives: DerivativesData | None
```

---

## Part 6: Service Layer Architecture

### Core Processing Services

#### QuoteCache (`services/quote_cache.py`)
- **Purpose:** Cache latest bid/ask quotes per symbol
- **Methods:**
  - `update(msg: SSIQuoteMessage)` — store latest quote
  - `get_bid_ask(symbol: str) -> (float, float)` — retrieve bid/ask for classification

#### TradeClassifier (`services/trade_classifier.py`)
- **Purpose:** Classify trades as mua_chu_dong / ban_chu_dong / neutral
- **Input:** SSITradeMessage + QuoteCache
- **Logic:**
  - ATO/ATC session → NEUTRAL
  - last_price >= ask → MUA_CHU_DONG
  - last_price <= bid → BAN_CHU_DONG
  - Else → NEUTRAL
- **Output:** `ClassifiedTrade`

#### SessionAggregator (`services/session_aggregator.py`)
- **Purpose:** Accumulate per-session stats (buy vol, sell vol, neutral vol, etc.)
- **Methods:**
  - `add_trade(classified: ClassifiedTrade) -> SessionStats`
  - `get_all_stats() -> dict[str, SessionStats]`

#### ForeignInvestorTracker (`services/foreign_investor_tracker.py`)
- **Purpose:** Track cumulative foreign flow + compute deltas, speed, acceleration
- **Input:** SSIForeignMessage (cumulative values from Channel R)
- **Compute:** Delta between updates, rolling speed (vol/min), acceleration (speed change)
- **Output:** `ForeignInvestorData` per symbol, `ForeignSummary` (VN30 aggregate + top N)

#### IndexTracker (`services/index_tracker.py`)
- **Purpose:** Track VN30, VNINDEX real-time values and breadth
- **Input:** SSIIndexMessage (Channel MI)
- **Maintains:** Intraday sparkline (deque, max 21600 points ~6h)
- **Computed field:** advance_ratio = advances / (advances + declines)
- **Output:** `IndexData` per index_id

#### DerivativesTracker (`services/derivatives_tracker.py`)
- **Purpose:** Track VN30F futures price and compute basis vs VN30 spot
- **Input:** SSITradeMessage for VN30F contracts
- **Logic:**
  - basis = futures_price - VN30_spot_value
  - basis_pct = basis / spot_value * 100
  - is_premium = basis > 0
- **Maintains:** Basis history (deque, max 3600 points ~1h)
- **Output:** `BasisPoint`, `DerivativesData`

---

### Data Integration Service

#### MarketDataProcessor (`services/market_data_processor.py`)
- **Purpose:** Orchestrates all data processing — wired to SSI stream callbacks
- **Composition:**
  - `quote_cache: QuoteCache`
  - `classifier: TradeClassifier`
  - `aggregator: SessionAggregator`
  - `foreign_tracker: ForeignInvestorTracker`
  - `index_tracker: IndexTracker`
  - `derivatives_tracker: DerivativesTracker`
- **Stream Callbacks:**
  - `async handle_quote(msg: SSIQuoteMessage)` → updates cache, notifies
  - `async handle_trade(msg: SSITradeMessage)` → routes futures to derivatives OR classifies + aggregates
  - `async handle_foreign(msg: SSIForeignMessage)` → notifies
  - `async handle_index(msg: SSIIndexMessage)` → notifies
- **Public APIs:**
  - `get_market_snapshot() -> MarketSnapshot`
  - `get_foreign_summary() -> ForeignSummary`
- **Subscriber Pattern:**
  - `subscribe(callback: Callable[[str], None])` — register listener (e.g., WebSocket publisher)
  - `_notify(channel: str)` — broadcast to subscribers

---

### REST API Service

#### SSIMarketService (`services/ssi_market_service.py`)
- **Purpose:** Fetch VN30 component list + securities snapshot via SSI REST API
- **Methods:**
  - `async fetch_vn30_components() -> list[str]` — returns ["VNM", "HPG", ...] (used at startup)
  - `async fetch_securities_snapshot() -> list[dict]` — reconciliation data
- **Pattern:** Wraps `asyncio.to_thread()` with timeout=15s (SSI client is sync-only)
- **Error handling:** Returns [] on exception

---

### WebSocket Infrastructure

#### ConnectionManager (`websocket/connection_manager.py`)
- **Purpose:** Manages WebSocket clients with per-client async queues
- **Data structure:** `dict[WebSocket, (Queue[str], asyncio.Task)]`
- **Methods:**
  - `async connect(ws: WebSocket)` — accept, create queue + sender task
  - `async disconnect(ws: WebSocket)` — cancel task, close socket
  - `broadcast(data: str)` — push to all queues (drop oldest on overflow)
  - `async disconnect_all()` — shutdown cleanup
- **Per-client sender:** Pulls from queue, sends over WS; drops oldest if queue full

#### RateLimiter (`websocket/router.py`)
- **Purpose:** Track active connections per IP address
- **Methods:**
  - `check(ip: str, limit: int) -> bool` — check if under limit
  - `increment(ip: str)` — add connection
  - `decrement(ip: str)` — remove connection
- **Storage:** `dict[str, int]` (IP → count)

---

## Part 7: Test Execution Patterns

### Pattern 1: Direct Model Testing
```python
# Pydantic model instantiation + field assertion
class TestSSITradeMessage:
    def test_defaults(self):
        msg = SSITradeMessage()
        assert msg.symbol == ""
        assert msg.last_vol == 0
```

### Pattern 2: Static Method Testing
```python
# Call class method directly, test edge cases
class TestExtractSymbols:
    def test_valid_response(self):
        result = {"data": [{"StockSymbol": "VNM"}]}
        assert SSIMarketService._extract_symbols(result) == ["VNM"]
    
    def test_empty_data(self):
        assert SSIMarketService._extract_symbols({"data": []}) == []
```

### Pattern 3: Async Service Testing with Fixtures
```python
# Mock asyncpg pool, test async methods
@pytest.fixture
def mock_db():
    db = MagicMock(spec=Database)
    db.pool = AsyncMock()
    return db

@pytest.mark.asyncio
async def test_returns_rows(self, svc, mock_db):
    mock_db.pool.fetch = AsyncMock(return_value=[...])
    result = await svc.get_candles(...)
    assert len(result) == 1
```

### Pattern 4: WebSocket Integration Testing
```python
# TestClient + context manager for sync WS testing
def test_connect_adds_client(self, app, market_mgr):
    with patch(_SETTINGS, _mock_settings()):
        with TestClient(app).websocket_connect("/ws/market"):
            assert market_mgr.client_count == 1
```

### Pattern 5: Multi-client Testing with Threading
```python
# Background thread + foreground thread for parallel client simulation
def test_two_clients_both_receive_data(self, app, market_mgr):
    bg_data = []
    ready = threading.Event()
    
    def bg():
        with client.websocket_connect("/ws/market") as ws:
            ready.set()
            bg_data.append(ws.receive_text())
    
    t = threading.Thread(target=bg, daemon=True)
    t.start()
    ready.wait(timeout=3)
    
    with client.websocket_connect("/ws/market") as ws:
        market_mgr.broadcast(...)
        assert json.loads(ws.receive_text()) == {...}
```

---

## Part 8: App Startup & Lifespan

**File:** `backend/app/main.py`

### Service Initialization Order (in lifespan)
1. **DB Connect:** `await db.connect()` (asyncpg pool)
2. **Batch Writer:** `await batch_writer.start()` (writes to DB)
3. **SSI Auth:** `await auth_service.authenticate()` (obtain session token)
4. **Fetch VN30:** `vn30_symbols = await market_service.fetch_vn30_components()` (cached globally)
5. **Stream Subscribe:** `await stream_service.connect(channels)` (WebSocket to SSI)
6. **Data Processing:** `processor.subscribe(publisher.notify)` (wire callbacks)
7. **WebSocket Publisher:** `publisher.start()` (event-driven broadcast loop)

### Service Singletons (Module-level)
```python
auth_service = SSIAuthService()
market_service = SSIMarketService(auth_service)
stream_service = SSIStreamService(auth_service, market_service)
processor = MarketDataProcessor()
batch_writer = BatchWriter(db)
market_ws_manager = ConnectionManager()
foreign_ws_manager = ConnectionManager()
index_ws_manager = ConnectionManager()
```

### REST Endpoints Registered
- `/api/market/*` (market_router)
- `/api/history/*` (history_router)
- `/ws/*` (websocket router)

---

## Part 9: Key Implementation Details

### Per-Trade vs Cumulative Volume
- **SSITradeMessage.last_vol:** PER-TRADE volume (NOT cumulative)
- **SSITradeMessage.total_vol:** Cumulative session volume
- **ClassifiedTrade.volume:** Uses last_vol (per-trade)
- **Trade value:** `last_price * last_vol * 1000` (price in 1000 VND)

### Foreign Investor Tracking
- **SSI Channel R:** Sends cumulative F_BUY_VOL, F_SELL_VOL from market open
- **ForeignInvestorTracker:** Computes delta between consecutive updates
- **Computed metrics:**
  - Speed: volume change per minute (rolling window)
  - Acceleration: speed change rate (derivative of speed)

### Futures Basis Calculation
- **Basis = futures_price - VN30_spot**
- **basis_pct = basis / spot_value * 100**
- **is_premium = basis > 0** (positive basis = contango)

### WebSocket Heartbeat
- **Interval:** Configurable (default from settings)
- **Message:** Binary `b"ping"`
- **Timeout:** Configurable (default from settings)
- **Failure:** Closes WS if send fails

---

## Part 10: Unresolved Questions

1. **No conftest.py found:** How are pytest plugins configured? Assumption: pytest.ini or direct pytest call with defaults.
2. **No pyproject.toml:** Dependencies specified in requirements.txt. Are dev dependencies separate?
3. **Test coverage:** No coverage reports visible. Coverage target unknown.
4. **Async test runner:** Tests use `@pytest.mark.asyncio` — is pytest-asyncio installed separately (not in requirements.txt)?
5. **Database schema:** HistoryService tests mock the pool but schema not documented.
6. **Rate limiter cleanup:** No persistent state — is it reset on app restart?
7. **WebSocket auth token:** Token configured via settings.ws_auth_token. How is this set in production?
8. **MarketSnapshot response:** Includes all channels (quotes + indices + foreign + derivatives). Serialization overhead?

---

## Summary

**Backend Architecture:**
- **REST APIs:** 2 routers (market, history) — 10 endpoints total
- **WebSocket:** 3 channels (market, foreign, index) — event-driven via DataPublisher
- **Services:** 6 core processors + orchestrator (MarketDataProcessor) + integration (SSIMarketService)
- **Models:** SSI raw messages (5 types) + domain models (9 types) + unified snapshot
- **Tests:** 20 test files — unit, integration, WebSocket, with patterns for sync/async
- **Dependencies:** FastAPI, asyncpg, websockets, ssi-fc-data, pydantic

**Key Strengths:**
- Clear separation: SSI messages → domain models → aggregation services → unified snapshot
- Event-driven WebSocket with per-client queues (no broadcast bottleneck)
- Rate limiting + optional auth on WebSocket
- Lazy service initialization (HistoryService)
- Comprehensive test coverage for models and static methods

**Testing Approach:**
- Pytest with AsyncMock for DB queries
- TestClient for WebSocket integration
- Threading for multi-client scenarios
- Mocking SSI service (static methods)

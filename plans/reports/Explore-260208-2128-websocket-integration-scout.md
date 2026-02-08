# WebSocket Integration Scout Report
**Date:** 2026-02-08 | **Project:** VN Stock Tracker | **Scope:** Phase 4 Planning

---

## 1. WebSocket Module Status

**File:** `backend/app/websocket/__init__.py`

**Status:** EMPTY (1 line only)

This is the allocated location for WebSocket server code (connections, rooms, message routing). No implementation exists yet. Ready for Phase 4 development.

---

## 2. Lifespan & Service Initialization

**File:** `backend/app/main.py` (103 lines) | **Status:** PRODUCTION-READY

### Service Singletons (module-level):
```python
auth_service = SSIAuthService()
market_service = SSIMarketService(auth_service)
stream_service = SSIStreamService(auth_service, market_service)
processor = MarketDataProcessor()
batch_writer = BatchWriter(db)
```

### Lifespan Sequence:
1. Connect DB pool
2. Start batch writer (async task for persistence)
3. Authenticate with SSI
4. Fetch VN30 component symbols (cached)
5. **Register processor callbacks on stream_service:**
   - `stream_service.on_quote(processor.handle_quote)`
   - `stream_service.on_trade(processor.handle_trade)`
   - `stream_service.on_foreign(processor.handle_foreign)`
   - `stream_service.on_index(processor.handle_index)`
6. Connect SSI stream with channels: Trade, Quote, Indices (VN30, VNINDEX), Futures (VN30F), Bars, Foreign

### Shutdown (reverse order):
```python
stream_service.disconnect() → batch_writer.stop() → db.disconnect()
```

### Phase 4 Integration Point:
- Add WebSocket broadcast server startup **after** `stream_service.connect()`
- Add shutdown **before** `stream_service.disconnect()`
- Both within lifespan context manager

---

## 3. MarketDataProcessor: Central Hub

**File:** `backend/app/services/market_data_processor.py` (117 lines) | **Status:** PRODUCTION-READY

### Composition (6 sub-services):
```
QuoteCache                    → Cache latest bid/ask per symbol
TradeClassifier              → Classify trades as mua/ban chu dong (uses QuoteCache)
SessionAggregator            → Running totals (per-symbol, per-session)
ForeignInvestorTracker       → Foreign flow (deltas, speed, acceleration)
IndexTracker                 → VN30, VNINDEX, HNX indices
DerivativesTracker           → VN30F futures contracts
_subscribers (list)          → Phase 4: WebSocket push callbacks (UNUSED)
```

### Unified API (read-only, safe for WebSocket):
```python
get_market_snapshot()        # MarketSnapshot: all quotes + indices + foreign + derivatives
get_foreign_summary()        # ForeignSummary: aggregate + top buy/sell
get_trade_analysis(symbol)   # SessionStats: per-symbol active buy/sell breakdown
get_derivatives_data()       # DerivativesData: futures snapshot
```

### Stream Callbacks (Phase 3 active):
```python
async def handle_quote(msg: SSIQuoteMessage)       # Update QuoteCache
async def handle_trade(msg: SSITradeMessage)       # Classify + aggregate stats
async def handle_foreign(msg: SSIForeignMessage)   # Track delta/speed/acceleration
async def handle_index(msg: SSIIndexMessage)       # Update index values
```

### Subscriber Infrastructure:
```python
def subscribe(self, callback: SubscriberCallback):      # Register async callback
def unsubscribe(self, callback: SubscriberCallback):    # Remove callback
```
- **Type:** `SubscriberCallback = Callable[[...], Coroutine[Any, Any, None]]` (async fn)
- **Status:** Infrastructure exists, **never invoked** — Phase 4 must call these
- **Pattern:** Fire-and-forget async callbacks, supports multiple subscribers

### Session Management:
```python
def reset_session()  # Called at 15:00 VN daily to reset all accumulators
```

---

## 4. SSI Stream Service: Cross-Thread Dispatch

**File:** `backend/app/services/ssi_stream_service.py` (183 lines) | **Status:** PRODUCTION-READY

### Challenge Solved:
SSI FastConnect library (`ssi-fc-data`) is **sync-only**. Solution: Wrap `stream.start()` in `asyncio.to_thread()`.

### Callback Registry:
```python
self._callbacks: dict[str, list[MessageCallback]] = {
    "Trade": [],   # Per-trade events (X channel)
    "Quote": [],   # Order book snapshots (X channel)
    "R": [],       # Foreign investor data (R channel)
    "MI": [],      # Index data: VN30, VNINDEX, HNX (MI channel)
    "B": [],       # OHLC bars (B channel)
}
```

### Message Flow (sync thread → async loop):
1. SSI SignalR sends raw message
2. `_handle_message(raw)` [called from **sync thread**]
3. Extract + parse to typed SSI model, determine RType
4. Retrieve `_callbacks[rtype]` list
5. For each callback: `_schedule_callback(cb, msg)`
6. `asyncio.run_coroutine_threadsafe(self._run_callback(cb, msg), self._loop)`

### Critical Patterns:
- **Event loop capture** (line 77): `self._loop = asyncio.get_running_loop()` at connect time
- **Cross-thread dispatch** (line 137): `asyncio.run_coroutine_threadsafe()` for safe callback execution
- **Fire-and-forget tracking** (lines 40-41, 143-144): Prevent GC of async callback tasks
- **Error isolation** (line 146): Try-catch around each callback execution

### Bonus: Reconnect Reconciliation:
```python
async def reconcile_after_reconnect():
    # Fetch REST snapshot to reseed cumulative values
    # Prevents foreign data delta spikes after reconnect
```

---

## 5. Domain Models: Ready for WebSocket

**File:** `backend/app/models/domain.py` (140 lines) | **Status:** PRODUCTION-READY

All models are Pydantic v2 `BaseModel` — **JSON serializable out-of-box**.

### Key Models for Broadcast:

| Model | Fields | Usage |
|-------|--------|-------|
| `SessionStats` | symbol, mua_chu_dong_volume/value, ban_chu_dong_volume/value, neutral_volume, total_volume, last_updated | Per-symbol active buy/sell breakdown |
| `ForeignInvestorData` | symbol, buy_volume, sell_volume, net_volume, buy_value, sell_value, net_value, total_room, current_room, buy_speed_per_min, sell_speed_per_min, buy_acceleration, sell_acceleration, last_updated | Per-symbol foreign flow tracking |
| `ForeignSummary` | total_buy_value, total_sell_value, total_net_value, total_buy_volume, total_sell_volume, total_net_volume, top_buy[], top_sell[] | VN30 aggregate foreign flow |
| `IndexData` | index_id, value, prior_value, change, ratio_change, total_volume, advances, declines, no_changes, intraday[], last_updated, **advance_ratio** (computed) | Index snapshots + breadth indicator |
| `DerivativesData` | symbol, last_price, change, change_pct, volume, bid_price, ask_price, basis, basis_pct, is_premium, last_updated | Futures snapshot + basis vs spot |
| `MarketSnapshot` | quotes{}, indices{}, foreign, derivatives | **Unified full snapshot** (REST `/api/market/snapshot` returns this) |

### Advantages:
- Pydantic v2 `.model_dump_json()` for WebSocket frames
- Type validation on construction
- `@computed_field` for derived values (e.g., `advance_ratio`)
- Rich metadata for IDE completion

---

## 6. REST Endpoints: Data Shape Reference

**File:** `backend/app/routers/market_router.py` (35 lines) | **Status:** PRODUCTION-READY

### Endpoints (import `processor` from `app.main`):
| Path | Method | Returns | Usage |
|------|--------|---------|-------|
| `/api/market/snapshot` | GET | `MarketSnapshot` | Full state: all quotes + indices + foreign + derivatives |
| `/api/market/foreign-detail` | GET | `{summary, stocks}` | Per-symbol foreign flow for heatmap/table |
| `/api/market/volume-stats` | GET | `{stats}` | Per-symbol SessionStats for volume breakdown |

**Key insight:** All endpoints follow pattern:
```python
from app.main import processor
return processor.get_*()
```

WebSocket can reuse the same `processor` methods for message payload generation.

---

## 7. Broadcast & Event Patterns Analysis

### Current (Phase 3):
**One-directional callback chain:**
```
SSI WebSocket (sync thread)
  ↓ _handle_message(raw)
  ↓ Extract + parse
  ↓ Dispatch to processor.handle_quote/trade/foreign/index (async callbacks)
  ↓
Processor (updates internal state: caches, accumulators, trackers)
```

**Subscriber infrastructure:** Exists but **completely unused**:
```python
processor._subscribers: list[SubscriberCallback] = []
```

### Missing for Phase 4:
1. **WebSocket connection manager** (accept/track/close client sockets)
2. **Broadcast dispatcher** (invoke `processor._subscribers` when state updates)
3. **Message routing** (which updates go to which clients)
4. **Channel subscriptions** (clients subscribe to symbol lists, data types)
5. **Backpressure handling** (slow clients, network buffering)

---

## 8. Integration Points for Phase 4

### A. Lifespan (main.py):
```python
# After stream_service.connect(channels):
broadcast_server = BroadcastServer(processor)
await broadcast_server.start()

yield

# Before stream_service.disconnect():
await broadcast_server.stop()
```

### B. MarketDataProcessor callbacks:
Option 1 (Minimal): Invoke subscribers in processor callbacks
```python
async def handle_trade(self, msg: SSITradeMessage):
    classified, stats = self._classify_and_aggregate(msg)
    # NEW: Broadcast to WebSocket subscribers
    for callback in self._subscribers:
        await callback("trade", {"stats": stats, "trade": classified})
```

Option 2 (Better): Create event dispatcher
```python
# In broadcast_server.py:
class BroadcastServer:
    def notify_trade_update(self, stats: SessionStats, trade: ClassifiedTrade):
        # Route to interested clients
```

### C. SSI stream service:
**No changes needed** — callback chain is working perfectly.

### D. WebSocket module (websocket/__init__.py):
```python
class BroadcastServer:
    def __init__(self, processor: MarketDataProcessor):
        self.processor = processor
        self.clients: dict[str, WebSocketState] = {}
    
    async def start(self):
        # Optional: initialize any background tasks
        pass
    
    async def stop(self):
        # Close all client connections
        pass
    
    @app.websocket("/ws/market")
    async def websocket_endpoint(self, websocket: WebSocket):
        # Accept connection, manage subscriptions, broadcast messages
        pass
```

---

## 9. Key Design Decisions

### 1. Async Dispatch Already Solved
SSI service uses `asyncio.run_coroutine_threadsafe()` to bridge sync thread → async loop.
Pattern is proven. Phase 4 can reuse or extend it.

### 2. Processor is Stateful
- Holds all accumulators: quotes, trades, foreign data, indices, derivatives
- WebSocket clients get snapshots or deltas
- No duplicate state needed in broadcast layer

### 3. Pydantic Models are JSON-Ready
- All domain models support `.model_dump_json()`
- No serialization boilerplate needed
- Type safety guaranteed

### 4. No Symbol Filtering Yet
- Current REST endpoints return full state
- Phase 4 should add: clients subscribe to specific symbols or data types
- Reduces broadcast overhead (don't send VN30F trades to a client watching foreign flow)

### 5. Session Reset Unimplemented
- `processor.reset_session()` exists but **never called**
- Scheduled for 15:00 VN daily (end of trading)
- Phase 4 should: add scheduler + broadcast "session reset" signal to WebSocket clients

---

## 10. Technology Stack

| Component | Library | Version | Notes |
|-----------|---------|---------|-------|
| Framework | FastAPI | (implied) | Built-in WebSocket support |
| Async Runtime | asyncio | stdlib | Event loop already running |
| Validation | Pydantic | v2 | `BaseModel`, `@computed_field` |
| JSON Serialization | pydantic | v2 | `.model_dump_json()` |
| WebSocket | FastAPI native | — | No extra package needed |
| Python | 3.12.12 | — | Modern syntax supported (X \| None, list[str], match/case) |

---

## 11. Readiness Assessment

| Aspect | Status | Evidence | Notes |
|--------|--------|----------|-------|
| SSI stream callbacks | ✅ WORKING | Lines 112-149 in ssi_stream_service.py | Dispatching to processor callbacks correctly |
| Processor unified API | ✅ READY | `get_market_snapshot()`, `get_foreign_summary()`, `get_trade_analysis()` | Methods exist, tested in REST endpoints |
| Subscriber infrastructure | ✅ DESIGNED | Lines 101-107 in market_data_processor.py | Methods exist, infrastructure ready, never called |
| Pydantic models | ✅ READY | All models inherit `BaseModel` | JSON serializable, type-safe |
| WebSocket module | ❌ EMPTY | `backend/app/websocket/__init__.py` | Needs full implementation |
| Lifespan integration | ⚠️ READY | Main.py lifespan context | Just needs broadcast server startup/shutdown hooks |
| REST endpoints | ✅ WORKING | `/api/market/*` endpoints | Reference implementation for data shape |
| Thread safety | ✅ SOLVED | `asyncio.run_coroutine_threadsafe()` | Sync SSI → async loop bridge proven |

---

## 12. Phase 4 Work Breakdown

### High-Level Tasks:
1. **Create broadcast server** (`websocket/broadcast_server.py`)
   - WebSocket connection manager (accept/track/close)
   - Client subscription handling (symbol filters, data types)
   - Message routing (who gets what updates)

2. **Wire broadcast to processor** (market_data_processor.py)
   - Invoke subscribers after state updates
   - OR create event dispatcher (processor → broadcast_server)

3. **Update lifespan** (main.py)
   - Startup broadcast server
   - Shutdown broadcast server

4. **Add scheduler** (new: session_scheduler.py or in main.py)
   - Call `processor.reset_session()` at 15:00 VN daily
   - Broadcast "session reset" event to WebSocket clients

5. **Tests** (backend/tests/)
   - WebSocket connection lifecycle
   - Subscription/unsubscription
   - Message broadcast correctness
   - Backpressure handling

---

## Unresolved Questions

1. **Broadcast granularity:** Send full `MarketSnapshot` per update, or incremental deltas per symbol?
   - Full: Simple, less routing logic, more bandwidth
   - Incremental: Bandwidth efficient, more complex reconciliation

2. **Client subscription schema:** What should clients subscribe to?
   - Option A: Per-symbol (e.g., `["VCB", "VN30"]`)
   - Option B: Per-data-type (e.g., `["quotes", "foreign", "indices", "derivatives"]`)
   - Option C: Combined (e.g., `{quotes: ["VCB"], foreign: ["VN30"], ...}`)

3. **Backpressure strategy:** How to handle slow clients?
   - Drop messages? Buffer? Throttle?

4. **Client reconnection:** If client drops and reconnects, send full snapshot or just deltas from that point?
   - Full snapshot is safer but requires memory of "last sent to client"

5. **Historical data:** Should WebSocket include intraday sparkline data?
   - Currently stored in `IndexData.intraday` (list[IntradayPoint])
   - Expensive to send per update?

---

**Report generated:** 2026-02-08 | **Scout:** Explore subagent
**Status:** Research complete, ready for Phase 4 implementation planning

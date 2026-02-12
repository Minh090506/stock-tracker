# System Architecture

## High-Level Overview

```
┌──────────────────────────────────────────────────────────────────┐
│    SSI FastConnect WebSocket (SignalR)                           │
│    Domain: https://fc-datahub.ssi.com.vn/ (NOT fc-data.ssi...)   │
├──────────────────────────────────────────────────────────────────┤
│ X:ALL           Trade + Quote events combined (RType="X")        │
│ R:ALL           Foreign investor (FBuyVol, FSellVol cumulative)   │
│ MI:ALL          VN30 + VNINDEX index values                       │
│ B:ALL           OHLC bars for charting                            │
│                                                                   │
│ Note: Each channel type subscribed ONCE; X:ALL splits into       │
│       Trade + Quote messages via parse_message_multi()           │
└──────────────────────────────────────────────────────────────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │  FastAPI Backend      │
                │  (Python 3.12+)       │
                └──────────┬────────────┘
                           │ /metrics endpoint
        ┌──────────────────┼──────────────────┬──────────────┐
        ▼                  ▼                  ▼              ▼
    ┌─────────┐      ┌──────────────┐   ┌──────────────┐  ┌─────────────┐
    │ Market  │      │ Market Data  │   │  Analytics   │  │ Database    │
    │ Data    │      │ Processor    │   │  Engine      │  │ Layer       │
    │Services │      │              │   │ (Phase 6)    │  │ (asyncpg)   │
    └─────────┘      └──────────────┘   └──────────────┘  └─────────────┘
        │                   │
        ├─ QuoteCache      ├── AlertService
        │                   │    ├── In-memory buffer (deque maxlen=500)
        │                   │    ├── 60s dedup by (type+symbol)
        │                   │    ├── Subscribe/notify pattern
        │                   │    ├── PriceTracker (4 signal types)
        │                   │    ├── REST: GET /api/market/alerts
        │                   │    └── WS: /ws/alerts channel
        │
        ├─ Database Layer (Phase 7)
        │  └─ Connection Pool (pool.py)
        │     ├─ Min/max configurable (DB_POOL_MIN, DB_POOL_MAX)
        │     ├─ Health check (60s interval)
        │     └─ Graceful startup (optional DB connection)
        │
        └─ Monitoring Stack (Phase 8D)
           ├─ Prometheus v2.53.0 (scrapes /metrics every 30s)
           ├─ Grafana v11.1.0 (4 auto-provisioned dashboards)
           └─ Node Exporter v1.8.1 (system metrics)
        │
        ├─ Database Layer (Phase 7)
        │  └─ Connection Pool (pool.py)
        │     ├─ Min/max configurable (DB_POOL_MIN, DB_POOL_MAX)
        │     ├─ Health check (60s interval)
        │     └─ Graceful startup (optional DB connection)
        │
        ▼
    ┌──────────────────────────────────┐
    │ REST API Routers (Phase 5B)      │
    ├──────────────────────────────────┤
    │ market_router.py:                │
    │ - GET /api/market/snapshot       │
    │ - GET /api/market/foreign-detail │
    │ - GET /api/market/volume-stats   │
    │ - GET /api/market/basis-trend    │
    │ - GET /api/market/alerts         │
    │ history_router.py:               │
    │ - GET /api/history/{symbol}/{...}│
    │ - GET /api/history/index/{name}  │
    │ - GET /api/history/derivatives/..│
    └──────────────────────────────────┘
            │
    ┌──────────────────┐
    │ WebSocket Router │
    │ Multi-Channel    │
    ├──────────────────┤
    │ /ws/market       │
    │ /ws/foreign      │
    │ /ws/index        │
    │ /ws/alerts       │
    └──────────────────┘
            │
            ▼
    ┌──────────────┐
    │ React        │
    │ Frontend     │
    └──────────────┘
            │
            ▼
    ┌──────────────┐
    │ PostgreSQL   │
    │ Database     │
    └──────────────┘
```

## Backend Components

### 1. SSI Services Layer

**SSIAuthService** (`ssi_auth_service.py`)
- Handles OAuth2 authentication with SSI
- Manages access tokens and refresh via SSIAccessTokenRequest dataclass
- Config uses SimpleNamespace (attribute access required by ssi-fc-data v2.2.2)
- Provides credentials for market and stream services

**SSIMarketService** (`ssi_market_service.py`)
- REST API for market data lookups (Domain: https://fc-data.ssi.com.vn/)
- Uses proper dataclasses: IndexComponentsReq, SecuritiesReq from ssi-fc-data
- Futures contract resolver (active VN30F months)
- Instrument information retrieval

**SSIStreamService** (`ssi_stream_service.py`)
- SignalR WebSocket connection management (Domain: https://fc-datahub.ssi.com.vn/)
- Message parsing via parse_message_multi() — handles RType="X" splitting
- Auto-reconnect with exponential backoff
- Callback registration for message types

**SSIFieldNormalizer** (`ssi_field_normalizer.py`)
- Converts SSI field names to internal schema
- Handles double JSON parsing: SSI Content field is JSON string inside dict
- Splits RType="X" messages into Trade + Quote via parse_message_multi()
- Ensures consistent naming across services

**FuturesResolver** (`futures_resolver.py`)
- Determines active VN30F contracts
- Handles rollover periods
- Supports manual override via `FUTURES_OVERRIDE` env

### 2. Data Processing Core (Phase 3)

All services stateful and initialized in `MarketDataProcessor`:

**QuoteCache** (`quote_cache.py`)
- **Purpose**: Store latest bid/ask prices per symbol
- **Input**: X:ALL Quote data (extracted by parse_message_multi)
- **Output**: Bid/ask lookups for trade classification
- **Lifecycle**: Persistent in-memory dictionary; reset daily at 15:00

```python
# Example usage
bid, ask = processor.quote_cache.get_bid_ask("VNM")
```

**TradeClassifier** (`trade_classifier.py`)
- **Purpose**: Classify trades as active buy/sell/neutral
- **Logic**:
  - Get cached bid/ask from QuoteCache
  - Compare trade.last_price against bid/ask thresholds
  - Preserve `trading_session` field (ATO/ATC/continuous) from SSI trade message
  - Mark ATO/ATC as NEUTRAL (batch auctions) for classification type
- **Input**: X:ALL Trade data (extracted by parse_message_multi, includes trading_session)
- **Output**: ClassifiedTrade with trade_type, volume, value, trading_session
- **Performance**: <1ms per trade

```python
# Thresholds
if price >= ask_price:
    trade_type = TradeType.MUA_CHU_DONG  (active buy)
elif price <= bid_price:
    trade_type = TradeType.BAN_CHU_DONG  (active sell)
else:
    trade_type = TradeType.NEUTRAL
```

**SessionAggregator** (`session_aggregator.py`)
- **Purpose**: Accumulate active buy/sell totals per symbol with per-session phase breakdown
- **Data**: Mua/ban/neutral volumes split into ATO/Continuous/ATC phases
- **Input**: ClassifiedTrade from TradeClassifier (includes trading_session)
- **Output**: SessionStats with aggregate totals + SessionBreakdown for each phase
- **Session Phases**:
  - `ato`: ATO (Opening Auction) phase trades
  - `continuous`: Regular continuous trading phase trades
  - `atc`: ATC (Closing Auction) phase trades
- **Invariant**: Sum of all phases totals == SessionStats totals (validated by tests)
- **Reset**: Daily 15:00 VN (clears all stats)

**ForeignInvestorTracker** (`foreign_investor_tracker.py`)
- **Purpose**: Track foreign investor activity with speed metrics
- **Input**: R:ALL messages (cumulative FBuyVol, FSellVol)
- **Processing**:
  - Compute delta from previous update
  - Accumulate deltas in rolling 10-minute window
  - Calculate speed (volume/minute over 5-min rolling window)
  - Calculate acceleration (change in speed)
- **Output**: ForeignInvestorData with buy_speed_per_min, sell_speed_per_min
- **Reset**: Daily 15:00 VN

**IndexTracker** (`index_tracker.py`)
- **Purpose**: Track VN30 and VNINDEX real-time values
- **Input**: MI:ALL messages (VN30, VNINDEX)
- **Data**: Index value, change, change_pct, advances, declines
- **Computed**: advance_ratio = advances / (advances + declines)
- **Output**: IndexData with breadth indicators
- **Intraday Chart**: Sparkline points tracked (maxlen=1440 for 1-day at 1/min)

**DerivativesTracker** (`derivatives_tracker.py`)
- **Purpose**: Track VN30F futures and compute basis
- **Input**: X:ALL Trade data for symbols starting with "VN30F"
- **Logic**:
  - Store futures_price by symbol
  - Compute basis = futures_price - IndexTracker.get_vn30_value()
  - Compute basis_pct = basis / spot_value * 100
  - Detect premium (basis > 0) vs discount (basis < 0)
  - Track active contract by volume (highest volume wins)
- **Output**: BasisPoint, DerivativesData
- **History**: Bounded deque (maxlen=3600 = ~1h at 1 trade/sec)

### 3. Unified Processor

**MarketDataProcessor** (`market_data_processor.py`)
- **Initialization**: Creates all service instances
- **Routing**: Dispatches SSI messages to appropriate handlers
- **Unified API**:

```python
async def handle_quote(msg: SSIQuoteMessage)
    → quote_cache.update()

async def handle_trade(msg: SSITradeMessage)
    → if symbol.startswith("VN30F"):
        derivatives_tracker.update_futures_trade()
    else:
        classified = classifier.classify()
        stats = aggregator.add_trade()

async def handle_foreign(msg: SSIForeignMessage)
    → foreign_tracker.update()

async def handle_index(msg: SSIIndexMessage)
    → index_tracker.update()

def get_market_snapshot() → MarketSnapshot
    Aggregates: quotes, indices, foreign summary, derivatives data
```

## Data Models

### Domain Models (`models/domain.py`)

```
TradeType (Enum)
├── MUA_CHU_DONG (active buy)
├── BAN_CHU_DONG (active sell)
└── NEUTRAL

ClassifiedTrade
├── symbol, price, volume, value
├── trade_type: TradeType
├── bid_price, ask_price (from cache)
└── timestamp

SessionBreakdown (New)
├── mua_chu_dong_volume, ban_chu_dong_volume
├── neutral_volume, total_volume
└── (repeated for ato, continuous, atc phases)

SessionStats (Updated)
├── symbol
├── mua_chu_dong_volume, mua_chu_dong_value
├── ban_chu_dong_volume, ban_chu_dong_value
├── neutral_volume, total_volume
├── last_updated
├── ato: SessionBreakdown (opening auction)
├── continuous: SessionBreakdown (regular trading)
└── atc: SessionBreakdown (closing auction)

PriceData (Phase 5A)
├── last_price
├── change (from ref)
├── change_pct
├── ref_price (prior close)
├── ceiling (TVT)
└── floor (STC)

ForeignInvestorData
├── symbol
├── buy_volume, sell_volume, net_volume
├── buy_value, sell_value, net_value
├── total_room, current_room
├── buy_speed_per_min, sell_speed_per_min
├── buy_acceleration, sell_acceleration
└── last_updated

ForeignSummary
├── total_buy_value, total_sell_value, net_value
├── total_buy_volume, total_sell_volume, net_volume
├── top_buy: list[ForeignInvestorData]
├── top_sell: list[ForeignInvestorData]

IndexData
├── index_id (VN30, VNINDEX)
├── value, prior_value, change, ratio_change
├── total_volume, advances, declines
├── advance_ratio (computed)
├── intraday: list[IntradayPoint]
└── last_updated

BasisPoint
├── timestamp
├── futures_symbol, futures_price, spot_value
├── basis (futures - spot)
├── basis_pct (basis / spot * 100)
└── is_premium (basis > 0)

DerivativesData
├── symbol, last_price, change, change_pct
├── volume (cumulative session)
├── bid_price, ask_price
├── basis, basis_pct
├── is_premium
└── last_updated

MarketSnapshot (Unified API)
├── quotes: dict[symbol → SessionStats]
├── prices: dict[symbol → PriceData] (Phase 5A)
├── indices: dict[index_id → IndexData]
├── foreign: ForeignSummary
└── derivatives: DerivativesData
```

## Message Flow (Summary)

SSI channels (fc-datahub.ssi.com.vn) stream messages split by parse_message_multi():

**X:ALL (Trade + Quote)**: parse_message_multi() splits into Trade + Quote messages
  - **Trade**: VN30F? → DerivativesTracker | Regular → TradeClassifier → SessionAggregator
  - **Quote**: → QuoteCache (bid/ask for trade classification)
**R:ALL (Foreign)**: → ForeignInvestorTracker (delta, speed, acceleration)
**MI:ALL (Indices)**: → IndexTracker (VN30 + VNINDEX, breadth, sparkline)
**Basis**: VN30F trade + VN30 value → DerivativesTracker (basis = futures - spot)

## Daily Reset Cycle

15:05 VN daily_reset_loop() → SessionAggregator.reset(), ForeignInvestorTracker.reset(), IndexTracker.reset(), DerivativesTracker.reset(), AlertService.reset_daily()

## Performance & Memory

| Operation | Latency | Memory |
|-----------|---------|--------|
| Trade classification | <1ms | 50KB (QuoteCache) |
| Foreign delta | <0.5ms | 30KB (10-min history) |
| Index update | <0.1ms | 115KB (intraday) |
| Basis calc | <0.5ms | 360KB (~1h history) |
| **Total** | **<5ms** | **~655KB** |

## Configuration

```
CHANNEL_R_INTERVAL_MS=1000
FUTURES_OVERRIDE=VN30F2603
WS_THROTTLE_INTERVAL_MS=500
WS_AUTH_TOKEN=
WS_MAX_CONNECTIONS_PER_IP=5
```

## REST API Endpoints (Phase 5B)

### Market Data Endpoints (`market_router.py`)
- `GET /api/market/snapshot` → MarketSnapshot (quotes, indices, foreign, derivatives)
- `GET /api/market/foreign-detail` → ForeignSummary (aggregate + top movers)
- `GET /api/market/volume-stats` → Volume breakdown by type
- `GET /api/market/basis-trend?minutes=30` → BasisPoint[] (filtered history)

### Historical Data Endpoints (`history_router.py`)
- `GET /api/history/{symbol}/candles?interval=1m&limit=100` → OHLC bars
- `GET /api/history/{symbol}/ticks?limit=500` → Individual trades
- `GET /api/history/{symbol}/foreign?days=5` → Foreign investor history
- `GET /api/history/{symbol}/foreign/daily` → Daily foreign summary
- `GET /api/history/index/{name}?days=5` → Index historical values
- `GET /api/history/derivatives/{contract}?days=5` → Futures contract history

## Testing Strategy

**Test Pyramid** (380 total tests, 84% coverage):

### Unit Tests (269 tests)
- Each service isolated with mocked dependencies
- Phase 1-3: 232 tests (Quote, Trade, Session, Foreign, Index, Derivatives)
- Phase 4: 37 tests (ConnectionManager, Router, DataPublisher)
- Phase 5B: 38 tests (Market + History REST endpoints)
- Phase 6: 31 tests (PriceTracker signal detection)

### Integration Tests (88 tests)
- Multi-service coordination with real components
- Multi-channel message flow with 100+ tick simulations
- WebSocket auth validation, rate limiting, channel isolation
- REST endpoint validation, parameter filtering, data consistency

### End-to-End Tests (23 tests, Phase 8C)
Full system scenarios from SSI → processing → broadcast → client:

**Test Suite** (`backend/tests/e2e/`, 790 LOC):
- `test_full_flow.py` (7 tests) — Complete pipeline validation
  - Quote caching: SSI X:ALL → parse_message_multi → QuoteCache → bid/ask retrieval
  - Trade classification: LastPrice vs bid/ask → TradeType assignment
  - Session aggregation: Per-trade volume accumulation + session phase breakdown
  - Foreign tracking: Delta computation → speed → acceleration
  - Index tracking: MI:ALL → breadth indicators
  - Derivatives: VN30F trade → basis calculation (futures - spot)
  - Market snapshot: Unified view aggregation across all services

- `test_foreign_tracking.py` (4 tests) — Foreign investor flows E2E
  - R:ALL cumulative → delta computation → net volume/value
  - Speed calculation: 5-min rolling window
  - Acceleration detection: Change in speed over time
  - Summary aggregation: Top buy/sell movers

- `test_alert_flow.py` (3 tests) — Alert generation & delivery
  - VOLUME_SPIKE: Trade volume >3× avg → alert → WS /ws/alerts broadcast
  - PRICE_BREAKOUT: Price hits ceiling/floor → CRITICAL alert
  - FOREIGN_ACCELERATION: Net value Δ >30% → WARNING alert
  - Alert deduplication: 60s cooldown per (type, symbol)

- `test_reconnect_recovery.py` (4 tests) — Resilience scenarios
  - SSI disconnect: Stream interruption → automatic reconnect
  - Data continuity: No message loss during reconnect window
  - Client reconnect: WS client drop → rejoin → catch up
  - Queue overflow: Slow consumer → queue limit → graceful degradation

- `test_session_lifecycle.py` (5 tests) — Session phase transitions
  - ATO routing: trading_session="ATO" → ato breakdown bucket
  - Continuous routing: trading_session="" → continuous breakdown bucket
  - ATC routing: trading_session="ATC" → atc breakdown bucket
  - Volume breakdown invariant: sum(ato + continuous + atc) == total
  - Session reset: 15:00 VN daily reset → all breakdowns cleared

**E2E Test Infrastructure**:
- Mock SSI services (`conftest.py`, 242 LOC): Deterministic message sequences
- Real asyncio event loop: Validates async/await flow
- Real WebSocket connections: Starlette TestClient with WebSocket support
- Shared fixtures: Processor, mock stream, test harness

### Performance Tests
- **Profiling**: `profile-performance-benchmarks.py` (CPU, memory, asyncio, DB pool)
- **Baselines**: 58,874 msg/s throughput, 0.017ms avg latency (verified ✅)
- **Load tests** (Phase 8B): Locust 4 scenarios, WS p99 85-95ms, 0% errors

### Test Execution
```bash
# Unit + integration tests
pytest backend/tests/ -v --cov=app --cov-fail-under=80

# E2E tests only
pytest backend/tests/e2e/ -v

# Performance profiling
./backend/venv/bin/python backend/scripts/profile-performance-benchmarks.py
./backend/venv/bin/python backend/scripts/generate-benchmark-report.py

# Load testing
./scripts/run-load-test.sh market_stream
```

### 4. WebSocket Multi-Channel Router (Phase 4 - COMPLETE)

**WebSocket Router** (`router.py`): 3 channels (/ws/market, /ws/foreign, /ws/index)
**ConnectionManager** (`connection_manager.py`): Per-client async queues, lifecycle management
**DataPublisher** (`data_publisher.py`): Event-driven reactive broadcasting with per-channel throttle (500ms default)

**Config** (`config.py`): ws_throttle_interval_ms (500), ws_heartbeat_interval (30s), ws_auth_token, ws_max_connections_per_ip (5)

**Security**: Token validation (optional), IP rate limiting, per-channel throttle, automatic cleanup

## Frontend WebSocket Client Integration

### useWebSocket Hook

**Purpose**: Generic, reusable React hook for real-time WebSocket data with fallback resilience.

**Features**:
- **Multi-channel support**: "market" (full snapshot), "foreign" (flow data), "index" (indices only)
- **Auto-reconnect**: Exponential backoff (1s → 30s cap) with configurable max attempts
- **REST fallback**: After 3 failed WS attempts, switches to polling; retries WS every 30s
- **Generation counter**: Prevents stale polling responses from overwriting fresh WS data after reconnect
- **Token auth**: Optional Bearer token via query parameter
- **Lifecycle**: Clean cleanup on unmount; resets on channel/token change

**Connection Lifecycle**:
```
1. CONNECTING (initial WebSocket attempt)
   ↓
2. CONNECTED (WebSocket established, data flows live)
   │
   ├─ [ERROR] → exponential backoff retry
   │            (1s → 2s → 4s → 8s → 16s → 30s → 30s → ...)
   │
   └─ [3 attempts failed] → START REST FALLBACK
                            └─ Poll every 5s (configurable)
                            └─ Retry WS every 30s
                               └─ [WS success] → RECONNECTED, kill polling
```

**Return Object**:
- `data: T | null` - Latest message (WS or REST)
- `status: ConnectionStatus` - "connecting" | "connected" | "disconnected"
- `error: Error | null` - Last error encountered
- `isLive: boolean` - true = WS active, false = REST fallback
- `reconnect: () => void` - Manual reconnect (resets attempts counter)

**Configuration**:
```typescript
{
  token?: string;                    // Auth token (appended as ?token=)
  fallbackFetcher?: () => Promise<T>; // REST endpoint for polling fallback
  fallbackIntervalMs?: number;       // Poll interval (default: 5000ms)
  maxReconnectAttempts?: number;     // Attempts before fallback (default: 3)
}
```

### Data Flow (Browser → Backend)

```
React Component
    ↓
useWebSocket<T>("market", options)
    ├─ [Live] WebSocket (/ws/market?token=xxx)
    │          ↓
    │          FastAPI WebSocket Router
    │          ├─ Auth token validation
    │          ├─ Rate limiting (5 conns/IP default)
    │          ├─ Connection lifecycle (heartbeat, queue management)
    │          └─ Event-driven DataPublisher (per-channel throttle 500ms)
    │             ↓
    │             MarketDataProcessor.handle_* (Quotes, Trades, Foreign, Index)
    │             ↓
    │             Emit MarketSnapshot (or ForeignSummary, IndexData)
    │             ↓
    │             Back to Browser (< 5ms latency)
    │
    └─ [Fallback] REST API Polling
       └─ GET /api/market/snapshot
          ↓
          Same processor (but polled every 5s)
          ↓
          Browser receives stale-but-recent data
          └─ [WS retries every 30s] → Eventually reconnect
```

### Backend Integration Points

**ConnectionManager** (`connection_manager.py`)
- Per-client asyncio queues (non-blocking broadcast)
- Connection lifecycle hooks
- Rate limiting enforcement

**WebSocket Router** (`router.py`)
- Endpoint: `GET /ws/{channel}?token=xxx`
- Channels: market, foreign, index
- Token validation, heartbeat, cleanup

**DataPublisher** (`data_publisher.py`)
- Event-driven broadcasting (replaces poll-based loop)
- Per-channel throttle (500ms trailing-edge, configurable)
- Zero overhead when no clients connected

## Frontend Dashboard (Phase 5)

### Price Board (Phase 5A - COMPLETE)

**Price Board Data Flow**:
```
React Component (PriceBoardPage)
    ↓
usePriceBoardData() hook
    ├─ Filters MarketSnapshot.prices to VN30 symbols
    ├─ Maintains per-symbol sparkline history (50 points max)
    └─ Uses useWebSocket("market") internally
        ↓
        WebSocket /ws/market
        ↓
        FastAPI RouterWebSocket, ConnectionManager, DataPublisher
        ↓
        MarketDataProcessor
        ├─ Updates _price_cache on each trade
        ├─ Merges with QuoteCache (ref, ceiling, floor)
        └─ Returns MarketSnapshot.prices
```

**Frontend Components**:
- `price-board-sparkline.tsx` - Inline SVG, renders 50-point history
- `price-board-table.tsx` - Sortable columns, row flash on update
- `price-board-skeleton.tsx` - Loading placeholder with shimmer
- `price-board-page.tsx` - Page layout with live/polling indicator + session status badge
- `market-session-indicator.tsx` - Session badge (pre-market/ATO/continuous/lunch/ATC/PLO/closed)

**UI Color Coding** (VN Market Convention):
- Red = Up (price increase)
- Green = Down (price decrease)
- Fuchsia = Ceiling (TVT)
- Cyan = Floor (STC)

**Performance**:
- Sparkline capped at 50 points (memory efficient)
- Flash animation on price change (CSS transition)
- Table rows virtualized for large lists (future optimization)
- WS latency <100ms typical

### Derivatives Basis Panel (Phase 5B - COMPLETE)

**Derivatives Data Flow**:
```
React Component (DerivativesPage)
    ↓
useDerivativesData() hook
    ├─ WS Market Snapshot → derivatives field
    └─ REST Polling (10s) → GET /api/market/basis-trend?minutes=30
        ↓
        FastAPI market_router.py
        ↓
        DerivativesTracker.get_basis_trend(minutes=30)
        ├─ Filters basis_history by timestamp
        └─ Returns BasisPoint[]
```

**Frontend Components**:
- `derivatives-summary-cards.tsx` - Contract, price, basis, premium/discount
- `basis-trend-area-chart.tsx` - Recharts AreaChart (30-min basis history)
- `convergence-indicator.tsx` - Basis convergence/divergence + slope analysis
- `open-interest-display.tsx` - Open interest (N/A from SSI, graceful display)
- `derivatives-skeleton.tsx` - Loading skeleton

**Basis Chart Features**:
- Red area fill: Premium (basis > 0)
- Green area fill: Discount (basis < 0)
- Recharts AreaChart with responsive container
- 30-min sliding window (~200 data points)

**Performance**:
- Basis trend polling: 10s interval
- Chart renders <100ms with 200 points
- Memory: ~20KB for 30-min history

### Foreign Flow Dashboard (Phase 6B - COMPLETE)

**Hybrid Data Flow**:
```
React Component (ForeignFlowPage)
    ↓
useForeignFlow() hook (102 LOC)
    ├─ WebSocket /ws/foreign (Real-time)
    │  └─ ForeignSummary (aggregate totals)
    │     └─ Summary cards + Cumulative flow chart
    │
    └─ REST Polling /api/market/foreign-detail (10s interval)
       └─ stocks[] (per-symbol foreign detail)
          └─ Sector chart + Top buy/sell tables + Detail table
```

**Architecture Rationale**:
- WS for lightweight real-time aggregate (low bandwidth)
- REST polling for detailed per-symbol data (heavier payload, acceptable 10s delay)
- Session-date boundary detection resets cumulative flow history daily

**Frontend Components**:
- `vn30-sector-map.ts` (53 LOC) - Static sector mapping for VN30 stocks
- `foreign-sector-bar-chart.tsx` (103 LOC) - Horizontal bar chart: net buy/sell by sector
- `foreign-cumulative-flow-chart.tsx` (90 LOC) - Intraday cumulative flow area chart
- `foreign-top-stocks-tables.tsx` (81 LOC) - Side-by-side top 10 net buy + top 10 net sell
- `foreign-flow-page.tsx` (69 LOC) - Layout: header → summary → sector + cumulative → tops → detail
- `foreign-flow-skeleton.tsx` (61 LOC) - Loading skeleton

**Cumulative Flow Chart**:
- Tracks net foreign value every second
- Resets on session-date boundary (prevents cross-day accumulation)
- Max 1440 points/day (~1 per minute effective rate)
- Green area: net positive flow, Red area: net negative flow

**Sector Aggregation**:
- Groups VN30 stocks by sector (Banking, Real Estate, Steel, etc.)
- Sums net buy/sell per sector
- Horizontal bar chart with color coding (green=buy, red=sell)

**Performance**:
- WS latency: <100ms for summary updates
- REST polling: 10s interval (low server load)
- Sector chart: <50ms render with 10 sectors
- Cumulative chart: <100ms render with 1440 points

## Phase 6: Analytics Engine (COMPLETE)

**Alert Infrastructure**: `alert_models.py`, `alert_service.py` (~142 LOC)
- AlertType enum: FOREIGN_ACCELERATION, BASIS_DIVERGENCE, VOLUME_SPIKE, PRICE_BREAKOUT
- AlertSeverity: INFO, WARNING, CRITICAL
- In-memory buffer (deque maxlen=500), 60s dedup

**PriceTracker** (`price_tracker.py`, ~180 LOC):
- 4 signals: VOLUME_SPIKE, PRICE_BREAKOUT, FOREIGN_ACCELERATION, BASIS_DIVERGENCE
- Callbacks wired: `on_trade()`, `on_foreign()`, `on_basis_update()`
- Tests: 31 passing

**Frontend**: useAlerts hook, dual filter chips (type+severity), real-time cards, sound notifications

## Phase 7: Database Persistence (COMPLETE)

**Connection Pool** (`backend/app/database/pool.py`):
- Configurable pool (DB_POOL_MIN=2, DB_POOL_MAX=10)
- Health checks every 60s, graceful startup (continues without DB)

**Alembic Migrations** (`backend/alembic/`):
- 5 hypertables: trades, foreign_snapshots, index_snapshots, basis_points, alerts
- TimescaleDB on PostgreSQL 16 (docker-compose.prod.yml)

**Health Endpoint**: `GET /health` → `{"status": "ok", "database": "connected"|"unavailable"}`

**Graceful Startup**: Logs warning if DB unavailable, history endpoints return 503, market data flows normally

---

## Deployment Architecture (Production Docker Setup)

### Overview

Production deployment uses a containerized architecture with seven services coordinated via docker-compose:

```
┌─────────────────────────────────────────────────┐
│         Nginx (Reverse Proxy - Alpine)          │
│ ┌────────────────┬──────────────────────────┐   │
│ │ Frontend:80    │ Backend:8000             │   │
│ │ (Static)       │ (FastAPI)                │   │
│ └────────────────┴──────────────────────────┘   │
│           Port 80 (HTTP)                        │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
        ┌──────────────────┐
        │  Docker Network  │
        │   app-network    │
        └────────┬─────────────────────┐
                 │                     │
        ┌────────┴────────┐  ┌─────────┴──────────┐
        ▼                 ▼  ▼                    ▼
    ┌──────────┐  ┌──────────────────┐  ┌──────────────────┐
    │ Frontend │  │ Backend          │  │ TimescaleDB      │
    │ (Node)   │  │ (FastAPI)        │  │ (PostgreSQL 16)  │
    │ :80      │  │ :8000            │  │ :5432            │
    │ Static   │  │ asyncio          │  │ Health checks    │
    │ files    │  │ uvloop           │  │ Persistent vol   │
    └──────────┘  │ Connection pool  │  └──────────────────┘
                  │ non-root user    │
                  └──────────────────┘
```

### Service Definitions

**Nginx** (`docker-compose.prod.yml`):
- Image: `nginx:alpine`
- Binds port 80 to container
- Routes `/` → frontend, `/api/` → backend, `/ws` → backend (with WebSocket upgrade)
- Health check: `wget http://localhost/health` (backend health via proxy)
- Depends on backend (healthy) and frontend (started)

**Backend** (`backend/Dockerfile`):
- Multi-stage build: Python 3.12 slim base → prod image
- Non-root user: `stock` (UID 1000)
- Dependencies: fastapi, uvloop, asyncpg
- Healthcheck: `python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"`
- Memory limits: 1GB max, 512MB reserved
- Runs: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --lifespan on`

**Frontend** (`frontend/Dockerfile`):
- Multi-stage: Node 20 builder → Nginx runner
- Build: `npm run build` → static bundle in `dist/`
- Serve: Nginx with gzip compression + cache headers
- Memory limits: 128MB max, 64MB reserved
- Static-only (no proxy to backend; handled by main Nginx)

**TimescaleDB** (`docker-compose.prod.yml`) — Phase 7:
- Image: `timescale/timescaledb:2.16-pg16`
- Credentials: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` via `.env` substitution
- Health check: `pg_isready -U $POSTGRES_USER` (10s interval, 5s timeout)
- Persistent volume: `postgres_data` for data persistence
- Memory limits: 1GB max, 512MB reserved
- Network: Connected to `app-network` bridge
- Backward compat: Supports graceful startup (app continues if unavailable)

**Prometheus** (`docker-compose.prod.yml`) — Phase 8D:
- Image: `prom/prometheus:v2.53.0`
- Scrape config: Targets `/metrics` endpoint every 30s
- Data retention: 30 days
- Port: 9090 (internal only, via Nginx proxy)
- Persistent volume: `prometheus_data`

**Grafana** (`docker-compose.prod.yml`) — Phase 8D:
- Image: `grafana/grafana:v11.1.0`
- Port: 3000 (internal only, via Nginx proxy)
- Auto-provisioned dashboards (4 dashboards)
- Data source: Prometheus (auto-configured)
- Persistent volume: `grafana_data`

**Node Exporter** (`docker-compose.prod.yml`) — Phase 8D:
- Image: `prom/node-exporter:v1.8.1`
- Metrics: CPU, memory, disk, network
- Port: 9100 (Prometheus scrapes internally)
- No persistent storage needed
- NOTE: Skipped on macOS (rslave mount not supported by Docker Desktop)

### Network Configuration

**Bridge Network** (`app-network`):
- Service discovery via container names (DNS resolution)
- Backend ↔ Frontend communication via internal network (no port exposure)
- Nginx routes traffic from external port 80 to internal services

**Reverse Proxy Rules** (`nginx/nginx.conf`):
```
/ (root)           → frontend:80     (static HTML/JS)
/api/*            → backend:8000    (FastAPI REST endpoints)
/ws               → backend:8000    (WebSocket with Upgrade headers)
/health           → backend:8000    (health check, no logs)
```

### Environment Configuration

All configuration via `.env` file (copied into containers):
- SSI credentials (SSI_CONSUMER_ID, SSI_CONSUMER_SECRET)
- Database (DATABASE_URL, DB_POOL_MIN, DB_POOL_MAX)
- TimescaleDB credentials (POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB)
- WebSocket params (WS_THROTTLE_INTERVAL_MS, etc.)
- CORS origins (CORS_ORIGINS)

**Phase 7 Database Variables**:
```
DB_POOL_MIN=2
DB_POOL_MAX=10
POSTGRES_USER=stockuser
POSTGRES_PASSWORD=secure_password
POSTGRES_DB=stock_tracker
DATABASE_URL=postgresql://stockuser:secure_password@timescaledb:5432/stock_tracker
```

See `.env.example` for full template.

### Running Production

```bash
# Build and start all services
docker-compose -f docker-compose.prod.yml up -d

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Stop
docker-compose -f docker-compose.prod.yml down
```

### Security & Performance

- Non-root container user (prevents privilege escalation)
- uvloop for I/O performance (10-40% faster than standard asyncio)
- Nginx Alpine image (lightweight, only 9MB)
- Resource limits enforce memory caps (prevent memory leaks)
- Health checks enable automatic restart on failure
- WebSocket upgrade headers ensure long-lived connections
- No secrets in Dockerfile; all via `.env`

## CI/CD Pipeline

### GitHub Actions Workflow

**File**: `.github/workflows/ci.yml`

**Pipeline Jobs**:

1. **Backend** (Python 3.12, 15min timeout)
   - Install from `requirements-dev.txt` (pytest, pytest-cov, pytest-asyncio, httpx)
   - Create `.env` from `.env.example`
   - Run tests: `pytest --cov=app --cov-report=term-missing --cov-report=xml --cov-fail-under=80`
   - Enforces 80% minimum coverage

2. **Frontend** (Node 20, 10min timeout)
   - Install via `npm ci`
   - Build: `npm run build`
   - Tests: Conditional execution if test script exists

3. **Docker Build** (20min timeout)
   - Depends on: backend + frontend jobs passing
   - Builds production images: `docker compose -f docker-compose.prod.yml build`
   - Verifies: stock-tracker-backend + stock-tracker-frontend images exist

**Triggers**:
- Push to `master` or `main`
- All pull requests

**Caching**:
- Pip dependencies via `actions/setup-python@v5` cache
- npm dependencies via `actions/setup-node@v4` cache

**Test Dependencies**:
- Backend: `backend/requirements-dev.txt`
  - pytest==8.3.5
  - pytest-cov==6.0.0
  - pytest-asyncio==0.24.0
  - httpx==0.28.1

**Quality Gates**:
- Backend: 80% coverage minimum (fail build if below)
- Frontend: Build must succeed
- Docker: Images must build without errors

## Phase 8B: Load Testing Suite (COMPLETE)

**Locust Framework** with 4 scenarios: market_stream, foreign_flow, burst_test, reconnect_storm

**Performance Baselines** (verified):
- WS p99 latency: 85-95ms (target <100ms) ✅
- REST p95 latency: 175-195ms (target <200ms) ✅
- Reconnect time: <1s (target <2s) ✅
- Error rate: 0% ✅

**Docker Integration**: `docker-compose.test.yml` with master/worker nodes
**CI Smoke Test**: 10 users × 30s on master push (automated)
**Files**: `backend/locust_tests/`, `docker-compose.test.yml`, `scripts/run-load-test.sh`

See `docs/deployment-guide.md` for load testing execution details.

## Phase 8C: E2E Tests & Performance Profiling (COMPLETE)

**E2E Test Suite** (`backend/tests/e2e/`, 790 LOC, 23 tests):
- Full system integration: SSI → processor → WS → client
- Alert flows: Detection → AlertService → broadcast
- Resilience: Disconnect/reconnect, queue overflow, error recovery
- Session lifecycle: ATO/Continuous/ATC transitions + volume validation
- Mock SSI services for deterministic testing

**Performance Profiling**:
- `profile-performance-benchmarks.py` — CPU, memory, asyncio, DB profiling
- `generate-benchmark-report.py` — Auto-generated Markdown reports
- `docs/benchmark-results.md` — Performance baseline tracking

**Verified Baselines**:
- Throughput: 58,874 msg/s (target ≥5000 msg/s) ✅
- Avg latency: 0.017ms (target ≤0.5ms) ✅
- Memory: Graceful degradation mode operational ✅
- E2E scenarios: 0% error rate ✅

**Testing Coverage**:
- 380 total tests (357 unit/integration + 23 E2E)
- 84% code coverage (enforced in CI)
- All test suites passing ✅

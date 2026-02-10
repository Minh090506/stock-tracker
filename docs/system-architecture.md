# System Architecture

## High-Level Overview

```
┌─────────────────────────────────────────────────────────────┐
│               SSI FastConnect WebSocket (SignalR)            │
├─────────────────────────────────────────────────────────────┤
│ X-TRADE:ALL     Trade events (LastPrice, LastVol per-trade) │
│ X-Quote:ALL     Order book (BidPrice1-10, AskPrice1-10)     │
│ R:ALL           Foreign investor (FBuyVol, FSellVol cum.)    │
│ MI:VN30         VN30 index value                             │
│ MI:VNINDEX      VNINDEX value                                │
│ X:VN30F{YYMM}   Derivatives futures                          │
│ B:ALL           OHLC bars for charting                       │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │  FastAPI Backend      │
                │  (Python 3.12+)       │
                └───────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
    ┌─────────┐      ┌──────────────┐    ┌───────────┐    ┌──────────────┐
    │ Market  │      │ Market Data  │    │ Analytics │    │ Database     │
    │ Data    │      │ Processor    │    │ Engine    │    │ Layer        │
    │ Services│      │              │    │ (Phase 6) │    │ (asyncpg)    │
    └─────────┘      └──────────────┘    └───────────┘    └──────────────┘
        │                   │                   │
        │                   ├── QuoteCache      ├── AlertService
        │                   ├── TradeClassifier │    ├── In-memory buffer (deque maxlen=500)
        │                   ├── SessionAggregator│   ├── 60s dedup by (type+symbol)
        │                   ├── ForeignInvestorTracker│ Subscribe/notify pattern
        │                   ├── IndexTracker     │    ├── PriceTracker (4 signal types)
        │                   └── DerivativesTracker    ├── REST: GET /api/market/alerts
        │                                            └── WS: /ws/alerts channel
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
- Manages access tokens and refresh
- Provides credentials for market and stream services

**SSIMarketService** (`ssi_market_service.py`)
- REST API for market data lookups
- Futures contract resolver (active VN30F months)
- Instrument information retrieval

**SSIStreamService** (`ssi_stream_service.py`)
- SignalR WebSocket connection management
- Message parsing and routing
- Auto-reconnect with exponential backoff
- Callback registration for message types

**SSIFieldNormalizer** (`ssi_field_normalizer.py`)
- Converts SSI field names to internal schema
- Handles data type transformations
- Ensures consistent naming across services

**FuturesResolver** (`futures_resolver.py`)
- Determines active VN30F contracts
- Handles rollover periods
- Supports manual override via `FUTURES_OVERRIDE` env

### 2. Data Processing Core (Phase 3)

All services stateful and initialized in `MarketDataProcessor`:

**QuoteCache** (`quote_cache.py`)
- **Purpose**: Store latest bid/ask prices per symbol
- **Input**: X-Quote:ALL messages
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
- **Input**: X-TRADE:ALL messages (includes trading_session field)
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
- **Input**: MI:VN30, MI:VNINDEX messages
- **Data**: Index value, change, change_pct, advances, declines
- **Computed**: advance_ratio = advances / (advances + declines)
- **Output**: IndexData with breadth indicators
- **Intraday Chart**: Sparkline points tracked (maxlen=1440 for 1-day at 1/min)

**DerivativesTracker** (`derivatives_tracker.py`)
- **Purpose**: Track VN30F futures and compute basis
- **Input**: X-TRADE messages for symbols starting with "VN30F"
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

**Trade**: X-TRADE → handle_trade → VN30F? (YES: DerivativesTracker, NO: TradeClassifier → SessionAggregator)
**Quote**: X-Quote → handle_quote → QuoteCache
**Foreign**: R:ALL → handle_foreign → ForeignInvestorTracker (delta, speed, acceleration)
**Index**: MI:* → handle_index → IndexTracker (breadth, sparkline)
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

- **Unit tests**: Each service isolated (326 tests)
  - Phase 4: 11 ConnectionManager + 4 endpoint + 7 multi-channel router + 15 DataPublisher = 37 tests
  - Phase 5B: 12 market_router + 26 history_router = 38 tests
- **Integration tests**: Multi-channel message flow with 100+ ticks
- **Performance tests**: Verify <5ms aggregation latency
- **Edge cases**: Missing quotes, zero prices, sparse updates, client disconnects
- **WebSocket tests**: Auth validation, rate limiting, channel isolation
- **REST tests**: Endpoint validation, parameter filtering, data consistency

### 4. WebSocket Multi-Channel Router (Phase 4 - COMPLETE)

**WebSocket Router** (`router.py`)
- Three specialized channels for efficient data delivery:
  - `/ws/market` — Full MarketSnapshot (quotes + indices + foreign + derivatives)
  - `/ws/foreign` — ForeignSummary only (aggregate + top movers)
  - `/ws/index` — VN30 + VNINDEX IndexData only
- Token-based authentication via `?token=xxx` query param (optional)
- Rate limiting: Max connections per IP (default: 5)
- Shared lifecycle: auth → rate limit → connect → heartbeat → read loop → cleanup

**ConnectionManager** (`connection_manager.py`)
- Per-client asyncio queues for non-blocking message distribution
- Connection lifecycle management (connect/disconnect)
- Broadcast to all connected clients
- Queue overflow protection (maxsize=50)

**DataPublisher** (`data_publisher.py`) — Event-Driven Broadcasting
- Replaces poll-based broadcast loop with reactive push model
- Per-channel trailing-edge throttle (default 500ms, configurable via `WS_THROTTLE_INTERVAL_MS`)
- Processor notifies subscribers via `_notify(channel)` after each update
- Immediate broadcast if throttle window expired; deferred broadcast otherwise
- SSI disconnect/reconnect status notifications to all channels
- Zero overhead when no clients connected

**Configuration** (`config.py`):
```python
# Broadcasting
ws_broadcast_interval: float = 1.0      # [DEPRECATED] legacy poll interval
ws_throttle_interval_ms: int = 500      # per-channel event throttle (DataPublisher)
ws_heartbeat_interval: float = 30.0     # ping interval
ws_heartbeat_timeout: float = 10.0      # client timeout
ws_queue_size: int = 50                 # per-client queue limit

# Security
ws_auth_token: str = ""                 # empty = auth disabled
ws_max_connections_per_ip: int = 5      # rate limiting
```

**Integration** (`main.py`):
- Three ConnectionManager singletons: `market_ws_manager`, `foreign_ws_manager`, `index_ws_manager`
- DataPublisher initialized with processor + managers in lifespan context
- Processor subscribes DataPublisher via `processor.subscribe(publisher.notify)`
- WebSocket router registered to FastAPI app

**Security Features**:
- Query param token validation (disabled if `ws_auth_token=""`)
- IP-based rate limiting with connection counting
- Automatic cleanup on disconnect

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

## Phase 6: Analytics Engine (In Progress ~65%)

### Alert Infrastructure + PriceTracker (Callbacks Wired)

**Core Components**:

#### Alert Models (`alert_models.py`, ~39 LOC)
```python
AlertType (Enum):
├── FOREIGN_ACCELERATION    # Foreign net_value >30% change in 5min
├── BASIS_DIVERGENCE        # Futures basis crosses zero
├── VOLUME_SPIKE           # Per-trade volume >3x avg over 20min
└── PRICE_BREAKOUT         # Price touches ceiling/floor

AlertSeverity (Enum):
├── INFO      # Informational
├── WARNING   # Significant activity
└── CRITICAL  # Immediate attention
```

#### AlertService (`alert_service.py`, ~103 LOC)
- In-memory buffer: `deque(maxlen=500)`
- 60s dedup by (alert_type, symbol)
- Subscribe/notify pattern for broadcast

#### PriceTracker (`price_tracker.py`, ~180 LOC)

**4 Real-Time Signal Detectors**:

```
1. VOLUME_SPIKE
   └─ Trigger: last_vol > 3× avg_vol over 20-min window
   └─ Called: on_trade(symbol, last_price, last_vol)
   └─ Severity: WARNING

2. PRICE_BREAKOUT
   └─ Trigger: last_price >= ceiling OR last_price <= floor
   └─ Called: on_trade(symbol, last_price, last_vol)
   └─ Severity: CRITICAL
   └─ Data: direction ("ceiling" | "floor")

3. FOREIGN_ACCELERATION
   └─ Trigger: |net_value_change / past_value| > 30% in 5min window
   └─ Called: on_foreign(symbol)
   └─ Severity: WARNING
   └─ Data: direction ("buying" | "selling"), change_pct

4. BASIS_DIVERGENCE
   └─ Trigger: futures basis crosses zero (premium ↔ discount)
   └─ Called: on_basis_update() after basis recompute
   └─ Severity: WARNING
   └─ Data: basis, basis_pct, direction ("premium→discount" | "discount→premium")
```

**Integration with MarketDataProcessor** (WIRED):
```python
# In handle_trade() - lines 205, 211:
price_tracker.on_trade(symbol, last_price, last_vol)

# In handle_foreign() - line 237:
price_tracker.on_foreign(symbol)

# In update_basis() - line 274 for VN30F trades:
price_tracker.on_basis_update()
```

**Data Sources**:
- QuoteCache: Ceiling/floor for breakout detection
- ForeignInvestorTracker: Net value history
- DerivativesTracker: Current basis + sign tracking
- AlertService: Registers alerts with auto-dedup

**Tests**: 31 tests passing (test_price_tracker.py)

**Remaining Work** (Phase 6 ~35%):
1. Frontend alert notifications UI (toast notifications, alert panel)

## Next Phases

- **Phase 6**: Analytics engine (alerts, correlation, signals) — 20% complete
- **Phase 7**: Database layer for historical persistence
- **Phase 8**: Deployment and load testing

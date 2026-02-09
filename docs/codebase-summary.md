# Codebase Summary

## Directory Structure

```
backend/
├── app/
│   ├── main.py                           # FastAPI app entry point + lifespan
│   ├── config.py                         # Environment configuration (pydantic-settings)
│   ├── models/
│   │   ├── __init__.py
│   │   ├── domain.py                     # Domain models (ClassifiedTrade, SessionStats, etc.)
│   │   ├── schemas.py                    # API request/response schemas
│   │   └── ssi_messages.py               # SSI message models (Quote, Trade, Foreign, etc.)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ssi_auth_service.py           # OAuth2 with SSI
│   │   ├── ssi_market_service.py         # REST API for market data
│   │   ├── ssi_stream_service.py         # WebSocket connection management
│   │   ├── ssi_field_normalizer.py       # Field name mapping
│   │   ├── futures_resolver.py           # Active VN30F contract detection
│   │   ├── quote_cache.py                # Bid/ask caching (Phase 3A)
│   │   ├── trade_classifier.py           # Trade classification (Phase 3A)
│   │   ├── session_aggregator.py         # Session totals (Phase 3A)
│   │   ├── foreign_investor_tracker.py   # Foreign volume tracking (Phase 3B)
│   │   ├── index_tracker.py              # Index tracking (Phase 3B)
│   │   ├── derivatives_tracker.py        # Futures basis calculation (Phase 3C)
│   │   ├── market_data_processor.py      # Unified orchestrator (Phase 3)
│   ├── routers/
│   │   ├── health.py                     # Health check endpoint
│   │   └── market.py                     # Market data REST endpoints (Phase 4)
│   ├── websocket/
│   │   ├── __init__.py                   # Exports
│   │   ├── connection_manager.py        # Per-client queue + connection management
│   │   ├── router.py                     # Multi-channel router (/ws/market, /ws/foreign, /ws/index)
│   │   ├── broadcast_loop.py             # [DEPRECATED] Legacy poll-based broadcast (replaced by data_publisher)
│   │   └── data_publisher.py             # Event-driven publisher with per-channel throttle
│   └── database/
│       └── migrations.py                 # Database schema (Phase 7)
├── tests/
│   ├── conftest.py                       # pytest fixtures
│   ├── test_quote_cache.py               # QuoteCache unit tests
│   ├── test_trade_classifier.py          # TradeClassifier unit tests
│   ├── test_session_aggregator.py        # SessionAggregator unit tests
│   ├── test_foreign_investor_tracker.py  # ForeignInvestorTracker unit tests
│   ├── test_index_tracker.py             # IndexTracker unit tests
│   ├── test_derivatives_tracker.py       # DerivativesTracker unit tests
│   ├── test_market_data_processor.py     # MarketDataProcessor unit tests
│   └── test_data_processor_integration.py # Multi-channel integration tests
├── .env.example                          # Environment template
├── requirements.txt                      # Python dependencies
└── Dockerfile                            # Container image

tests/
├── test_ssi_auth_service.py              # OAuth2 tests
├── test_ssi_stream_service.py            # WebSocket tests
├── test_connection_manager.py            # WebSocket ConnectionManager tests (11 tests)
├── test_websocket_router.py              # Multi-channel router tests (7 tests)
├── test_data_publisher.py                # DataPublisher throttle + notification tests (15 tests)
└── [additional test files per service]
```

## Phase-by-Phase Implementation

### Phase 1: Project Scaffolding (COMPLETE)
- FastAPI application structure
- pydantic config management
- Health check endpoint
- Docker setup

**Key Files**:
- `app/main.py` - FastAPI + lifespan context
- `app/config.py` - Settings from `.env`

### Phase 2: SSI Integration & Stream Demux (COMPLETE)
- OAuth2 authentication
- WebSocket connection
- Message demultiplexing by RType
- Field normalization

**Key Files**:
- `app/services/ssi_auth_service.py` - OAuth2 token management
- `app/services/ssi_stream_service.py` - SignalR WebSocket
- `app/services/ssi_market_service.py` - REST API lookups
- `app/services/ssi_field_normalizer.py` - Field mapping
- `app/services/futures_resolver.py` - VN30F contract resolution
- `app/models/ssi_messages.py` - Message models

### Phase 3A: Trade Classification (COMPLETE)
Core trade processing pipeline:

**Key Files**:
- `app/services/quote_cache.py` - Bid/ask storage
- `app/services/trade_classifier.py` - Classification logic
- `app/services/session_aggregator.py` - Per-symbol accumulation

**Data Flow**:
```
Quote Message → QuoteCache (stores bid/ask)
Trade Message → TradeClassifier (compares vs bid/ask) → SessionAggregator (accumulates)
```

**Models**:
- `ClassifiedTrade` - Single trade with trade_type
- `SessionStats` - Aggregated mua/ban/neutral totals

**Tests**: 20+ unit tests covering:
- Classification logic (MUA/BAN/NEUTRAL)
- ATO/ATC handling
- Session aggregation
- Reset behavior

### Phase 3B: Foreign Investor & Index Tracking (COMPLETE)
Extended market data tracking:

**Key Files**:
- `app/services/foreign_investor_tracker.py` - Foreign flow analytics
- `app/services/index_tracker.py` - Index monitoring

**Data Flow**:
```
Foreign Message (R:ALL) → ForeignInvestorTracker (delta + speed calculation)
Index Message (MI:*) → IndexTracker (stores values + breadth)
```

**Models**:
- `ForeignInvestorData` - Buy/sell volume, speed, acceleration
- `ForeignSummary` - Aggregate + top movers
- `IndexData` - Index value, advances/declines, intraday sparkline
- `IntradayPoint` - Sparkline data point

**Tests**: 56+ unit tests covering:
- Delta computation from cumulative data
- Speed calculation (5-min rolling window)
- Acceleration tracking
- Index breadth ratios
- Sparkline management
- Reset and rollover

### Phase 3C: Derivatives Tracking (COMPLETE)
Futures and basis analysis:

**Key Files**:
- `app/services/derivatives_tracker.py` - Basis calculation
- `app/models/domain.py` - Updated with BasisPoint, DerivativesData, MarketSnapshot

**Data Flow**:
```
Futures Trade (VN30F*) → DerivativesTracker (basis = futures - VN30 spot)
                      ↓
                 BasisPoint + DerivativesData
```

**Models**:
- `BasisPoint` - Futures/spot prices + basis + premium/discount flag
- `DerivativesData` - Current futures snapshot (price, bid/ask, basis, basis_pct)
- `MarketSnapshot` - Unified view (quotes + indices + foreign + derivatives)

**Key Features**:
- Volume-based active contract selection (handles rollover)
- Multi-contract tracking
- Bounded basis history (maxlen=3600 = ~1h at 1 trade/sec)
- Time-filtered trend analysis

**Tests**: 34 Phase 3C tests covering:
- Basis calculation (positive, negative, zero)
- Premium vs discount detection
- Percentage computation
- Multi-contract tracking
- Active contract selection logic
- Volume accumulation
- Basis trend filtering
- Reset behavior
- Integration with other trackers (100+ tick simulation)

### Phase 3 Unified API (COMPLETE)
Centralized market data orchestration:

**Key Files**:
- `app/services/market_data_processor.py` - Central dispatcher + unified API

**Public API**:
```python
async def handle_quote(msg: SSIQuoteMessage)
async def handle_trade(msg: SSITradeMessage)
async def handle_foreign(msg: SSIForeignMessage)
async def handle_index(msg: SSIIndexMessage)

def get_market_snapshot() → MarketSnapshot
def get_trade_analysis(symbol: str) → SessionStats
def get_foreign_summary() → ForeignSummary
def get_derivatives_data() → DerivativesData | None

def reset_daily()  # Called at 15:00 VN
```

**Tests**: 232 total tests passing (Phase 3A+3B+3C included)

## Service Architecture

### Service Initialization Pattern

```python
class MarketDataProcessor:
    def __init__(self):
        # Create component instances
        self.quote_cache = QuoteCache()
        self.classifier = TradeClassifier(self.quote_cache)
        self.aggregator = SessionAggregator()
        self.foreign_tracker = ForeignInvestorTracker()
        self.index_tracker = IndexTracker()
        self.derivatives_tracker = DerivativesTracker(self.index_tracker)
```

All services:
- Stateful (hold in-memory data)
- Resetable (daily reset at 15:00 VN)
- Thread-safe (accessed via asyncio in FastAPI)
- Type-hinted (Python 3.12 syntax)

### Data Model Hierarchy

```
BaseModel (Pydantic)
├── ClassifiedTrade
├── SessionStats
├── ForeignInvestorData
├── ForeignSummary
├── IntradayPoint
├── IndexData
├── BasisPoint
├── DerivativesData
└── MarketSnapshot

Enum
├── TradeType (MUA_CHU_DONG, BAN_CHU_DONG, NEUTRAL)
```

## Key Implementation Details

### Trade Classification Algorithm

```python
def classify(self, trade: SSITradeMessage) -> ClassifiedTrade:
    bid, ask = self.quote_cache.get_bid_ask(trade.symbol)
    volume = trade.last_vol  # PER-TRADE, not cumulative

    # Skip auction sessions
    if trade.trading_session in ("ATO", "ATC"):
        trade_type = TradeType.NEUTRAL
    elif ask > 0 and trade.last_price >= ask:
        trade_type = TradeType.MUA_CHU_DONG
    elif bid > 0 and trade.last_price <= bid:
        trade_type = TradeType.BAN_CHU_DONG
    else:
        trade_type = TradeType.NEUTRAL

    return ClassifiedTrade(
        symbol=trade.symbol,
        price=trade.last_price,
        volume=volume,
        value=trade.last_price * volume * 1000,  # price in 1000 VND
        trade_type=trade_type,
        bid_price=bid,
        ask_price=ask,
        timestamp=datetime.now(),
    )
```

**Critical**: Uses `trade.last_vol` (per-trade) NOT `trade.total_vol` (cumulative)

### Foreign Investor Speed Calculation

```python
def update(self, msg: SSIForeignMessage) -> ForeignInvestorData:
    # Compute delta from previous cumulative
    if prev:
        delta_buy = max(0, msg.f_buy_vol - prev.f_buy_vol)
        delta_sell = max(0, msg.f_sell_vol - prev.f_sell_vol)
    else:
        delta_buy = msg.f_buy_vol
        delta_sell = msg.f_sell_vol

    # Store in rolling window
    self._history[symbol].append(ForeignDelta(
        buy_delta=delta_buy,
        sell_delta=delta_sell,
        timestamp=datetime.now(),
    ))

    # Calculate speed over 5-min window
    speed = self._compute_speed(symbol, window_minutes=5)
```

### Basis Calculation

```python
def _compute_basis(self, futures_symbol: str) -> BasisPoint | None:
    futures_price = self._futures_prices.get(futures_symbol, 0)
    spot_value = self._index.get_vn30_value()

    if futures_price <= 0 or spot_value <= 0:
        return None

    basis = futures_price - spot_value
    basis_pct = basis / spot_value * 100

    bp = BasisPoint(
        timestamp=datetime.now(),
        futures_symbol=futures_symbol,
        futures_price=futures_price,
        spot_value=spot_value,
        basis=basis,
        basis_pct=basis_pct,
        is_premium=basis > 0,
    )

    self._basis_history.append(bp)
    return bp
```

**Guards**: Zero-division protection, negative price handling

## Testing Structure

All tests use pytest + fixtures from `conftest.py`:

```
tests/
├── conftest.py                        # Shared fixtures
├── test_quote_cache.py                # 10 tests
├── test_trade_classifier.py           # 8 tests
├── test_session_aggregator.py         # 2 tests
├── test_foreign_investor_tracker.py   # 29 tests
├── test_index_tracker.py              # 27 tests
├── test_derivatives_tracker.py        # 17 tests
├── test_market_data_processor.py      # 14 tests
└── test_data_processor_integration.py # 3 multi-channel tests
```

**Phase 4**: 37 WebSocket tests (11 ConnectionManager + 4 endpoint + 7 router + 15 DataPublisher)
**Total**: 269 tests, all passing

## Data Model — PriceData (Phase 5A)

**PriceData** — Per-symbol price snapshot for price board:
```python
# backend/models/domain.py
class PriceData(BaseModel):
    last_price: float      # Latest trade price
    change: float          # Price change from ref
    change_pct: float      # Percentage change
    ref_price: float       # Reference price (prior close)
    ceiling: float         # Daily ceiling (TVT)
    floor: float           # Daily floor (STC)
```

**MarketSnapshot Update**:
- Added `prices: dict[str, PriceData]` field
- Populated from `_price_cache` merged with QuoteCache ref/ceiling/floor at snapshot time

**Price Cache Lifecycle**:
- `_price_cache: dict[str, PriceData]` in MarketDataProcessor
- Updated on every trade (stores last_price, change, change_pct)
- Merged with Quote ref/ceiling/floor for complete PriceData
- Cleared on daily reset at 15:00 VN

## Frontend Structure

### Hooks

**useWebSocket** (`frontend/src/hooks/use-websocket.ts`)
- Generic React hook for WebSocket real-time data
- Channels: "market" | "foreign" | "index"
- Auto-reconnect with exponential backoff (1s → 30s cap)
- REST polling fallback after 3 failed WS attempts
- Periodic WS retry (30s) while in fallback mode
- Generation counter prevents stale poll data from overwriting fresh WS data
- Clean disconnect on unmount
- Auth token support via query param

**usePriceBoardData** (`frontend/src/hooks/use-price-board-data.ts`) — Price Board Specific
- Specialized hook for price board with sparkline accumulation
- Filters MarketSnapshot to VN30 symbols only
- Maintains per-symbol sparkline history (50 points max)
- Returns: `{ priceData: PriceData[], sparklines: dict[symbol → number[]], status, isLive }`
- Uses useWebSocket("market") internally

**Type Definition**:
```typescript
export type WebSocketChannel = "market" | "foreign" | "index";
export type ConnectionStatus = "connecting" | "connected" | "disconnected";

export interface WebSocketResult<T> {
  data: T | null;                    // Latest parsed message
  status: ConnectionStatus;           // Connection state
  error: Error | null;               // Last error
  isLive: boolean;                   // true = WS active, false = REST fallback
  reconnect: () => void;             // Manual reconnect trigger
}

export interface UseWebSocketOptions<T> {
  token?: string;                    // Auth token query param
  fallbackFetcher?: () => Promise<T>; // REST polling fallback
  fallbackIntervalMs?: number;       // Poll interval (default: 5000ms)
  maxReconnectAttempts?: number;     // Attempts before fallback (default: 3)
}
```

**Usage Example**:
```typescript
const { data, status, error, isLive, reconnect } = useWebSocket<MarketSnapshot>(
  "market",
  {
    token: authToken,
    fallbackFetcher: async () => await fetchMarketData(),
    fallbackIntervalMs: 5000,
    maxReconnectAttempts: 3,
  }
);
```

### Components

**Price Board** (`frontend/src/components/price-board/`)
- `price-board-sparkline.tsx` - Inline SVG sparkline chart (50 points max)
- `price-board-table.tsx` - Sortable table with flash animation + color coding
  - Columns: Symbol, Last Price, Change, Change %, Ref, Ceiling, Floor, Last Vol, Avg Price
  - Row flash on price update; VN color coding (red=up, green=down, fuchsia=ceiling, cyan=floor)
- `market-session-indicator.tsx` - Colored badge showing current session status, auto-refresh every 15s

**UI Components** (`frontend/src/components/ui/`)
- `price-board-skeleton.tsx` - Loading skeleton with 10 placeholder rows
- error-boundary.tsx - Error handling wrapper
- error-banner.tsx - Error message display
- Loading skeletons (volume, foreign, signals, page)

**Layout Components** (`frontend/src/components/layout/`)
- app-sidebar-navigation.tsx - Sidebar menu (updated: "Price Board" as first nav item)
- app-layout-shell.tsx - Main layout wrapper

**Data Visualization** (`frontend/src/components/`)
- foreign/ - Foreign investor flow charts and tables
- volume/ - Trade volume analysis
- signals/ - Alert/signal display

**Pages** (`frontend/src/pages/`)
- `price-board-page.tsx` - Price board page component (live/polling indicator)
- dashboard-page.tsx, foreign-flow-page.tsx, etc.

### Utilities

**api-client** (`frontend/src/utils/api-client.ts`)
- Centralized API client wrapper
- REST endpoint abstraction

**format-number** (`frontend/src/utils/format-number.ts`)
- Number formatting utilities (currency, percentages, etc.)

**market-session** (`frontend/src/utils/market-session.ts`)
- Time-based VN market session detection (HOSE schedule)
- Uses Intl.DateTimeFormat with Asia/Ho_Chi_Minh timezone
- Detects: pre-market, ATO, continuous, lunch, ATC, PLO, closed
- Weekend detection (no holiday support)

### Types

**index** (`frontend/src/types/index.ts`)
- Shared TypeScript interfaces and types
- API response/request schemas
- PriceData interface: last_price, change, change_pct, ref_price, ceiling, floor
- MarketSnapshot updated: prices field (dict[symbol → PriceData])

## Code Quality Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Type Coverage | 100% | ✓ 100% |
| Test Coverage | >90% | ✓ ~95% |
| Latency (<5ms) | ✓ | ✓ All ops <5ms |
| Memory Bounded | ✓ | ✓ All capped |
| Python 3.12 | ✓ | ✓ Modern syntax |
| React 19 | ✓ | ✓ Latest |

## Dependencies

**Core**:
- `fastapi` - Web framework
- `pydantic` - Data validation
- `pydantic-settings` - Config management
- `ssi-fc-data` - SSI WebSocket SDK (sync-only)
- `asyncpg` - PostgreSQL driver (Phase 7)

**Testing**:
- `pytest` - Test runner
- `pytest-asyncio` - Async test support

**See `requirements.txt` for full list**

## Configuration

Environment variables defined in `.env`:

```
# SSI Credentials
SSI_CONSUMER_ID=<your-id>
SSI_CONSUMER_SECRET=<your-secret>

# Market Data
CHANNEL_R_INTERVAL_MS=1000
FUTURES_OVERRIDE=VN30F2603,VN30F2606

# WebSocket (Phase 4)
WS_BROADCAST_INTERVAL=1.0       # [DEPRECATED] Legacy poll interval
WS_THROTTLE_INTERVAL_MS=500     # Per-channel event throttle (DataPublisher)
WS_HEARTBEAT_INTERVAL=30.0      # Ping every 30s
WS_HEARTBEAT_TIMEOUT=10.0       # Timeout after 10s
WS_QUEUE_SIZE=50                # Per-client queue limit
WS_AUTH_TOKEN=                  # Optional token auth (empty = disabled)
WS_MAX_CONNECTIONS_PER_IP=5     # Rate limiting per IP

# Database (Phase 7)
DATABASE_URL=postgresql://user:pass@localhost/stock_tracker

# Server
LOG_LEVEL=INFO
FASTAPI_ENV=development
```

## Performance Notes

- All trade classification: <1ms
- Foreign delta calc: <0.5ms
- Index update: <0.1ms
- Basis calculation: <0.5ms
- **Aggregation (all 500+ symbols)**: <5ms

## Memory Usage

- In-memory services: ~655 KB total (all capped)
- QuoteCache: ~50 KB (500 symbols)
- SessionAggregator: ~100 KB (500 symbols)
- ForeignTracker history: ~30 KB (10-min window)
- IndexTracker intraday: ~115 KB (1-day window)
- DerivativesTracker basis: ~360 KB (~1-hour window)

## Completed Phases (Continued)

**Phase 4**: WebSocket Multi-Channel Router (COMPLETE)
- Three specialized channels: `/ws/market`, `/ws/foreign`, `/ws/index`
- Token-based authentication (optional, query param `?token=xxx`)
- Rate limiting: max connections per IP (default: 5)
- ConnectionManager with per-client queues (maxsize=50)
- Event-driven DataPublisher with per-channel throttle (500ms default)
- SSI connection status notifications (disconnect/reconnect)
- Application-level heartbeat (30s ping, 10s timeout)
- 37 tests (11 ConnectionManager + 4 endpoint + 7 router + 15 DataPublisher)
- All tests passing (288 total)

**Phase 5**: VN30 Price Board (COMPLETE)
- First frontend dashboard feature — real-time stock price monitoring
- WebSocket integration with sparkline chart and sortable price table
- Active buy/sell/neutral color coding per VN market conventions
- Flash animation for price changes; loading skeleton
- All TypeScript compiles clean; zero new dependencies
- Files: 6 new frontend components, 1 hook, 1 types update
- Code review grade: A-

## Future Phases (Pending)

**Phase 5**: Frontend Dashboard
- React 19 + TypeScript
- TradingView Lightweight Charts
- Real-time chart updates

**Phase 6**: Analytics Engine
- NN alerts
- Correlation analysis
- Basis divergence signals

**Phase 7**: Database Persistence
- Trade history
- Foreign snapshots
- Index historical values
- Basis backtesting

**Phase 8**: Testing & Deployment
- Load testing
- Docker deployment
- Production hardening

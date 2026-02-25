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
│   ├── analytics/
│   │   ├── __init__.py                   # Package exports (Alert, AlertType, AlertSeverity, AlertService, PriceTracker)
│   │   ├── alert_models.py               # Alert domain models (AlertType, AlertSeverity, Alert)
│   │   ├── alert_service.py              # In-memory alert buffer with dedup + subscriber pattern
│   │   └── price_tracker.py              # Real-time signal detector (4 signal types, callbacks wired)
│   ├── routers/
│   │   ├── health.py                     # Health check endpoint
│   │   ├── market_router.py              # Market data REST endpoints (Phase 5B)
│   │   └── history_router.py             # Historical data REST endpoints (Phase 5B)
│   ├── websocket/
│   │   ├── __init__.py                   # Exports
│   │   ├── connection_manager.py        # Per-client queue + connection management
│   │   ├── router.py                     # Multi-channel router (/ws/market, /ws/foreign, /ws/index)
│   │   ├── broadcast_loop.py             # [DEPRECATED] Legacy poll-based broadcast (replaced by data_publisher)
│   │   └── data_publisher.py             # Event-driven publisher with per-channel throttle
│   └── database/
│       ├── __init__.py
│       └── pool.py                       # Connection pool management + health check (Phase 7)
├── tests/
│   ├── conftest.py                       # pytest fixtures (unit/integration)
│   ├── test_quote_cache.py               # QuoteCache unit tests
│   ├── test_trade_classifier.py          # TradeClassifier unit tests
│   ├── test_session_aggregator.py        # SessionAggregator unit tests
│   ├── test_foreign_investor_tracker.py  # ForeignInvestorTracker unit tests
│   ├── test_index_tracker.py             # IndexTracker unit tests
│   ├── test_derivatives_tracker.py       # DerivativesTracker unit tests
│   ├── test_market_data_processor.py     # MarketDataProcessor unit tests
│   ├── test_data_processor_integration.py # Multi-channel integration tests
│   ├── test_price_tracker.py             # PriceTracker signal detection tests (31 tests)
│   └── e2e/                              # End-to-end test suite (Phase 8C, 790 LOC, 23 tests)
│       ├── __init__.py
│       ├── conftest.py                   # E2E fixtures, mock SSI services (242 LOC)
│       ├── test_full_flow.py             # SSI → processor → WS client (155 LOC, 7 tests)
│       ├── test_foreign_tracking.py      # Foreign investor E2E scenarios (90 LOC, 4 tests)
│       ├── test_alert_flow.py            # Alert generation → WS delivery (118 LOC, 3 tests)
│       ├── test_reconnect_recovery.py    # SSI disconnect/reconnect (87 LOC, 4 tests)
│       └── test_session_lifecycle.py     # ATO/Continuous/ATC transitions (97 LOC, 5 tests)
├── .env.example                          # Environment template
├── .dockerignore                         # Docker build context exclusions
├── requirements.txt                      # Python dependencies (includes alembic, psycopg2)
├── Dockerfile                            # Multi-stage backend container
├── scripts/                              # Utility scripts (Phase 8C)
│   ├── profile-performance-benchmarks.py # CPU, memory, asyncio, DB profiling (11.5KB)
│   └── generate-benchmark-report.py      # Performance report generator (11KB)
├── alembic/                              # Alembic migration system (Phase 7)
│   ├── versions/
│   │   └── 001_initial_schema.py         # Initial migration (5 hypertables)
│   ├── env.py                            # Alembic configuration
│   ├── script.py.mako                    # Migration template
│   └── alembic.ini                       # Alembic settings
└── locust_tests/                         # Load testing suite (Phase 8B, 4 scenarios)
    ├── helper.py
    ├── market_stream.py
    ├── foreign_flow.py
    ├── burst_test.py
    └── reconnect_storm.py

frontend/
├── Dockerfile                            # Multi-stage Node → Nginx static server
├── .dockerignore                         # Docker build context exclusions
├── nginx.conf                            # Static file serving with gzip + cache
└── [other frontend files]

nginx/
└── nginx.conf                            # Reverse proxy: frontend + backend + ws upgrade

docker-compose.prod.yml                   # Production orchestration (3 services)
.env.example                              # Environment variables template

tests/
├── test_ssi_auth_service.py              # OAuth2 tests
├── test_ssi_stream_service.py            # WebSocket tests
├── test_quote_cache.py                   # QuoteCache unit tests (10 tests)
├── test_trade_classifier.py              # TradeClassifier unit tests (8 tests)
├── test_session_aggregator.py            # SessionAggregator unit tests (2 tests)
├── test_foreign_investor_tracker.py      # ForeignInvestorTracker unit tests (29 tests)
├── test_index_tracker.py                 # IndexTracker unit tests (27 tests)
├── test_derivatives_tracker.py           # DerivativesTracker unit tests (17 tests)
├── test_market_data_processor.py         # MarketDataProcessor unit tests (14 tests)
├── test_data_processor_integration.py    # Multi-channel integration tests (3 tests)
├── test_connection_manager.py            # WebSocket ConnectionManager tests (11 tests)
├── test_websocket_router.py              # Multi-channel router tests (7 tests)
├── test_data_publisher.py                # DataPublisher throttle + notification tests (15 tests)
├── test_market_router.py                 # Market REST endpoint tests (12 tests)
├── test_history_router.py                # History REST endpoint tests (26 tests)
└── e2e/                                  # E2E test suite (23 tests total)
    ├── test_full_flow.py                 # SSI → processor → WS (7 tests)
    ├── test_foreign_tracking.py          # Foreign E2E (4 tests)
    ├── test_alert_flow.py                # Alert delivery (3 tests)
    ├── test_reconnect_recovery.py        # Reconnect scenarios (4 tests)
    └── test_session_lifecycle.py         # Session transitions (5 tests)
```

## Phase Overview

**Phases 1-8**: Core platform (scaffolding → SSI integration → data processing → WebSocket → Frontend → Analytics → Database → CI/CD/Testing)
**Phase 7B**: Backtest analysis dashboard (cross-correlation, threshold discovery, pattern analysis)
**Phase 9+**: Velocity analysis, VPS deployment, advanced features

### Core Data Processing (Phases 3A-3C)

**Trade Classification**: QuoteCache → TradeClassifier (MUA/BAN/NEUTRAL) → SessionAggregator (ATO/Continuous/ATC breakdown)
- Uses per-trade `LastVol` (not cumulative `TotalVol`)
- 28 unit tests with invariant validation

**Foreign & Index Tracking**: Delta computation + 5-min speed window, index breadth tracking
- 56+ tests covering speed, acceleration, breadth ratios, sparklines

**Derivatives Basis**: futures_price - spot_index, multi-contract support with volume-based active selection
- 34 tests covering basis calc, premium/discount, multi-contract tracking

**Unified API**: MarketDataProcessor orchestrates all services, provides get_market_snapshot(), reset_daily()
- 232 total Phase 3 tests passing

## Backend Architecture

**Service Layer**: 10+ services (QuoteCache, TradeClassifier, SessionAggregator, ForeignInvestorTracker, IndexTracker, DerivativesTracker, MarketDataProcessor, AlertService, PriceTracker, BacktestEngine)

**Stateful & Resetable**: All in-memory, daily reset at 15:00 VN, thread-safe via asyncio

**API Routers**: health, market_router, history_router, backtest_router (4 endpoints), WebSocket router (3 channels)

**Analytics**: AlertService (in-mem buffer, 60s dedup), PriceTracker (4→6 signal types), BacktestEngine (cross-correlation, threshold discovery, pattern analysis)

## Critical Implementation Notes

- **Trade Classification**: Uses `trade.last_vol` (per-trade, NOT cumulative `total_vol`)
- **Session Phases**: Trades routed to ATO/Continuous/ATC buckets based on `trading_session` field
- **Foreign Speed**: Delta computed from cumulative SSI data, speed over 5-min rolling window
- **Basis**: futures_price - spot_index; zero-division guarded; tracks premium/discount
- **SSI Config**: Two domains (REST=fc-data.ssi.com.vn, WebSocket=fc-datahub.ssi.com.vn); X:ALL split via parse_message_multi()
- **Alert Dedup**: 60s window per (type, symbol) pair; buffer maxlen=500
- **Backtest**: Pre-compute daily at 15:30 VN; pure Python correlation (no numpy)

## Test Coverage

**Unit Tests** (~280): QuoteCache, TradeClassifier, SessionAggregator, Foreign/Index/Derivatives trackers, Market processor
**Router Tests** (~40): market_router, history_router, backtest_router endpoints
**WebSocket Tests** (~35): ConnectionManager, DataPublisher, multi-channel router
**PriceTracker Tests** (~31): All 6 signal types (VOLUME_SPIKE, PRICE_BREAKOUT, FOREIGN_ACCEL, BASIS_DIVERGENCE, VELOCITY_DIVERGENCE, IMBALANCE_EXTREME)
**Backtest Tests** (~435): BacktestEngine (253 tests), BacktestRouter (181 tests)
**E2E Tests** (~23): Full system flow, foreign tracking, alert generation, reconnect, session lifecycle
**Total**: 434+ tests, 84% coverage enforced in CI

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

## Phase 6: Analytics Engine - Frontend Integration

### Alert Infrastructure (Frontend)
- Real Alert types: `AlertType` enum (VOLUME_SPIKE, PRICE_BREAKOUT, FOREIGN_ACCELERATION, BASIS_DIVERGENCE)
- Alert severity: INFO, WARNING, CRITICAL
- Alert data model: id, alert_type, severity, symbol, message, timestamp, data

### Alert Hooks
- `useAlerts` (`frontend/src/hooks/use-alerts.ts`)
  - WebSocket stream + REST fallback (GET /api/market/alerts)
  - Dedup by (type, symbol) matching backend
  - Sound notifications on new alerts
  - Returns: `{ alerts, status, isLive, soundEnabled, toggleSound }`

## Frontend Structure (50 files, 3257 LOC)

### Hooks

**useWebSocket** (`frontend/src/hooks/use-websocket.ts`, 201 LOC)
- Generic React hook for WebSocket real-time data
- Channels: "market" | "foreign" | "index" | "alerts"
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

**useDerivativesData** (`frontend/src/hooks/use-derivatives-data.ts`) — Derivatives Specific
- Combines WS market snapshot + REST basis-trend polling
- Returns: `{ derivatives, basisTrend, status, isLive }`
- Polls `GET /api/market/basis-trend?minutes=30` every 10s

**useForeignFlow** (`frontend/src/hooks/use-foreign-flow.ts`, 102 LOC) — Foreign Flow Hybrid
- **Hybrid architecture**: WS `/ws/foreign` for real-time ForeignSummary + REST `/api/market/foreign-detail` (10s poll) for per-symbol detail
- Accumulates cumulative flow history (1 point/sec, max 1440/day)
- Session-date boundary detection resets cumulative history daily
- Returns: `{ summary, stocks, cumulativeFlow, status, isLive }`

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
- `derivatives-skeleton.tsx` - Derivatives page loading skeleton
- error-boundary.tsx - Error handling wrapper
- error-banner.tsx - Error message display
- Loading skeletons (volume, foreign, signals, page)

**Layout Components** (`frontend/src/components/layout/`)
- app-sidebar-navigation.tsx - Sidebar menu (updated: "Price Board" as first nav item)
- app-layout-shell.tsx - Main layout wrapper

**Signals/Alerts** (`frontend/src/components/signals/`)
- `signal-filter-chips.tsx` - Dual filter (type + severity) with colored badges
- `signal-feed-list.tsx` - Real-time alert cards with icons, timestamps, auto-scroll

**Data Visualization** (`frontend/src/components/`)
- foreign/ - Foreign investor flow charts and tables
  - `foreign-sector-bar-chart.tsx` (103 LOC) - Net buy/sell by sector (horizontal bar)
  - `foreign-cumulative-flow-chart.tsx` (90 LOC) - Intraday cumulative net flow (area chart)
  - `foreign-top-stocks-tables.tsx` (81 LOC) - Top 10 net buy + top 10 net sell tables
  - `foreign-detail-table.tsx` - Per-symbol foreign detail table
  - `foreign-summary-cards.tsx` - Aggregate foreign flow summary
  - `foreign-heatmap.tsx` - Foreign flow heatmap visualization
- volume/ - Trade volume analysis
- signals/ - Alert/signal display (updated with real alerts)
- derivatives/ - Derivatives basis tracking
  - `derivatives-summary-cards.tsx` - Futures contract overview
  - `basis-trend-area-chart.tsx` - Historical basis chart
  - `convergence-indicator.tsx` - Basis convergence/divergence
  - `open-interest-display.tsx` - Open interest display (N/A from SSI)

**Pages** (`frontend/src/pages/`)
- `price-board-page.tsx` (48 LOC) - Price board page component (live/polling indicator)
- `derivatives-page.tsx` (39 LOC) - Derivatives basis analysis panel
- `foreign-flow-page.tsx` (69 LOC) - Foreign flow dashboard (hybrid WS+REST)
- dashboard-page.tsx, volume-analysis-page.tsx, signals-page.tsx

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

**vn30-sector-map** (`frontend/src/utils/vn30-sector-map.ts`, 53 LOC)
- Static VN30 sector mapping (Banking, Real Estate, Steel, etc.)
- Used by foreign-sector-bar-chart for sector aggregation

### Types

**index** (`frontend/src/types/index.ts`)
- Shared TypeScript interfaces and types
- API response/request schemas
- PriceData interface: last_price, change, change_pct, ref_price, ceiling, floor
- MarketSnapshot updated: prices field (dict[symbol → PriceData])

## Recent Additions

**Backtest Analysis Dashboard** (Phase 7B): Cross-correlation engine (velocity vs price), threshold discovery (imbalance→direction), time-of-day patterns. 4 REST endpoints + daily pre-compute + interactive frontend dashboard (8 components).

**Velocity Analysis**: Order velocity tracking (VN30F vs VN30 basket), correlation metrics, 3 REST endpoints, TimescaleDB continuous aggregates, 3 new alert types (VELOCITY_DIVERGENCE, IMBALANCE_EXTREME).

## Code Quality Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Type Coverage | 100% | ✓ 100% |
| Test Coverage | >80% | ✓ 84% |
| All operations | <5ms | ✓ <5ms |
| Memory bounded | ✓ | ✓ Capped |
| Python 3.12 | ✓ | ✓ Modern |
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
- 37 tests (11 ConnectionManager + 7 router + 4 endpoint + 15 DataPublisher)
- All tests passing (269 total after Phase 4)

**Phase 5**: VN30 Price Board + Derivatives Panel + REST API Routers (COMPLETE)
- Price board: Real-time VN30 stock monitoring with sparklines + market session indicator
- Derivatives: Basis analysis panel with trend chart + convergence indicator
- REST API Routers: Market + History endpoints with comprehensive test coverage
  - `market_router.py`: `/snapshot`, `/foreign-detail`, `/volume-stats`, `/basis-trend`
  - `history_router.py`: `/history/{symbol}/{candles,ticks,foreign}`, `/index/{name}`, `/derivatives/{contract}`
- WebSocket integration with sparkline chart and sortable price table
- Active buy/sell/neutral color coding per VN market conventions
- Flash animation for price changes; loading skeleton
- All TypeScript compiles clean; zero new dependencies
- Files: 13 frontend components, 2 hooks, 2 routers, 38 router tests, 1 types update
- Code review grade: A-
- Test coverage: 357 total tests (38 new router tests, 31 PriceTracker tests)

## Phase 6: Analytics Engine (COMPLETE 100%)

### Core Alert Infrastructure (COMPLETE)
- Alert models: AlertType (FOREIGN_ACCELERATION, BASIS_DIVERGENCE, VOLUME_SPIKE, PRICE_BREAKOUT)
- Alert severity: INFO, WARNING, CRITICAL
- AlertService: in-memory buffer (deque maxlen=500), 60s dedup by (type, symbol)
- Subscriber pattern for alert notifications (WS broadcast)
- Daily reset clears buffer and cooldowns (scheduled at 15:05 VN time)

### Backend REST/WS Endpoints (COMPLETE)
- `GET /api/market/alerts?limit=50&type=&severity=` — Retrieve recent alerts with filtering
- `/ws/alerts` — Real-time alert broadcasts via WebSocket channel
- `alerts_ws_manager` registered in DataPublisher for stream status notifications

### PriceTracker — Real-Time Signal Detection (COMPLETE + WIRED)
**File**: `app/analytics/price_tracker.py` (~180 LOC)

**4 Signal Types**:
1. **VOLUME_SPIKE**: Current trade volume > 3× avg over 20-min window
2. **PRICE_BREAKOUT**: Price hits daily ceiling (TVT) or floor (STC)
3. **FOREIGN_ACCELERATION**: Net foreign value changes >30% in 5-min window
4. **BASIS_DIVERGENCE**: Futures basis crosses zero (premium ↔ discount)

**Callbacks** (wired in MarketDataProcessor.handle_* methods):
- `on_trade(symbol, last_price, last_vol)` — lines 205, 211 in handle_trade()
- `on_foreign(symbol)` — line 237 in handle_foreign()
- `on_basis_update()` — line 274 in update_basis() for VN30F trades

**Data Sources**:
- QuoteCache: Ceiling/floor prices for breakout detection
- ForeignInvestorTracker: Net value + symbol history for acceleration
- DerivativesTracker: Current basis for flip detection
- AlertService: Registers generated alerts with auto-dedup

**Tests**: `tests/test_price_tracker.py` (31 tests, all passing)

**Status**: Phase 6 COMPLETE (357 tests passing, 80% coverage enforced in CI)

---

## Phase 7: Database Persistence (COMPLETE)

### Connection Pool Management

**File**: `backend/app/database/pool.py`

**Purpose**: Manage PostgreSQL connections with health checks and graceful startup

**Features**:
- Configurable pool size (DB_POOL_MIN, DB_POOL_MAX)
- Health check every 60 seconds (SELECT 1)
- Graceful startup (optional DB connection)
- Automatic reconnection on failure
- Thread-safe for asyncio environment

**API**:
```python
async def create_pool(db_url, min_size, max_size) -> AsyncPool
async def get_connection() -> AsyncConnection
async def health_check() -> bool
```

### Alembic Migrations

**Directory**: `backend/alembic/` with standard Alembic structure

**Files**:
- `alembic.ini` — Main configuration file
- `env.py` — Migration environment setup
- `script.py.mako` — Migration template
- `versions/001_initial_schema.py` — Initial migration

**Initial Schema** (5 Hypertables for TimescaleDB):
- `trades` (partition by timestamp)
- `foreign_snapshots` (partition by timestamp)
- `index_snapshots` (partition by timestamp)
- `basis_points` (partition by timestamp)
- `alerts` (partition by timestamp)

**Usage**:
```bash
# Apply migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"
```

### Integration with FastAPI

**Initialization** (`app/main.py`):
```python
# In lifespan context
pool = await create_pool(
    DATABASE_URL,
    min_size=config.db_pool_min,
    max_size=config.db_pool_max,
)
```

**Health Check** (`app/routers/health.py`):
- `/health` endpoint reports database status
- Response: `{"status": "ok", "database": "connected"|"unavailable"}`

### Graceful Startup

**Behavior**:
- If DATABASE_URL not set: app starts with warning, DB mode disabled
- If pool creation fails: logs error, retries, continues in-memory
- Market data (quotes, trades, foreign, index): unaffected (in-memory)
- History endpoints: return 503 Service Unavailable if DB unavailable

**Configuration**:
- Environment variables: DB_POOL_MIN, DB_POOL_MAX (optional)
- DATABASE_URL optional (graceful startup enabled if not set)

---

## Phase 6-7: Analytics Engine + Database Persistence

**Phase 6 (COMPLETE)**: AlertService, PriceTracker (4 signal types), Frontend alert UI (filters, cards, notifications)

**Phase 7 (COMPLETE)**: Connection pool (pool.py), Alembic migrations (5 hypertables), TimescaleDB in docker-compose.prod.yml

**Phase 7A (COMPLETE)**: Session breakdown (ATO/Continuous/ATC), SessionAggregator routing, session-phase volume analysis

**Status**: 394 tests passing (357 unit/integration + 23 E2E, 14 load tests), 80% CI coverage, all phases integrated

## Phase 8B: Load Testing Suite (COMPLETE)

**Locust Framework** with 4 scenarios:
- `market_stream.py` — WebSocket /ws/market (100-500 users, WS p99 <100ms)
- `foreign_flow.py` — WebSocket /ws/foreign (50-200 users, p99 <100ms)
- `burst_test.py` — REST /api/market/snapshot (500 req/s, p95 <200ms)
- `reconnect_storm.py` — Connection churn, reconnect <2s, 0% errors

**Performance Verified**: WS p99 85-95ms, REST p95 175-195ms, reconnect <1s, linear memory scaling

**Docker Integration**: `docker-compose.test.yml` with master/worker nodes
**CI Smoke Test**: 10 users × 30s automated on master push
**Files**: `backend/locust_tests/`, `scripts/run-load-test.sh`, `pytest.ini` (load tests excluded)

## Phase 8C: E2E Tests & Performance Profiling (COMPLETE)

**Monitoring Stack** (Phase 8D):

**Prometheus** (`monitoring/prometheus.yml`, v2.53.0):
- Scrapes `/metrics` endpoint every 30s
- Retention: 30 days
- Stores time-series metrics for performance analysis

**Grafana** (v11.1.0, 4 dashboards auto-provisioned):
- Application Performance: Request rates, latencies, error counts
- WebSocket Monitoring: Connected clients, message throughput
- Database Health: Pool connections, query latency, transaction counts
- System Metrics: CPU, memory, disk via Node Exporter

**Node Exporter** (v1.8.1):
- System-level metrics (CPU, memory, disk, network)
- Integrated with Prometheus for infrastructure visibility

**Metrics Instrumentation** (`backend/app/metrics.py`, 74 LOC):
- `prometheus_client>=0.21.0` dependency
- HTTP request duration histogram (bucket sizes: 0.01, 0.1, 1, 10s)
- Counters for SSI messages, WS connections, trade classifications, alerts, DB writes
- Per-endpoint latency tracking

**Deployment Integration** (`docker-compose.prod.yml` updated):
- All 7 services orchestrated (Nginx, Backend, Frontend, TimescaleDB, Prometheus, Grafana, Node Exporter)
- Health checks for each service
- Persistent volumes for Prometheus data + Grafana configs

**Deployment Script** (`scripts/deploy.sh`):
- One-command production deployment with preflight checks
- Verifies Docker, Docker Compose, environment configuration
- Runs health checks post-deployment
- Logs deployment status and system resources

**Documentation Suite** (5 new files):
- `docs/README.md` — Documentation index and navigation
- `docs/api-reference.md` — API endpoint documentation
- `docs/architecture.md` — System architecture detailed diagrams
- `docs/deployment.md` — Production deployment procedures
- `docs/monitoring.md` — Grafana dashboards and metrics guide

**Overall Status**: Phase 8D COMPLETE (monitoring stack operational, docs updated, deploy.sh ready)

**E2E Test Suite** (`backend/tests/e2e/`, 790 LOC, 23 tests):
- Full system integration: SSI connection → data processing → WS broadcast → client consumption
- Alert flows: Signal detection → AlertService → WS /ws/alerts channel
- Resilience: SSI reconnect, client reconnect, queue overflow handling
- Session lifecycle: ATO/Continuous/ATC transitions with volume breakdown validation
- Mock SSI services via conftest fixtures for deterministic testing

**Test Coverage Breakdown**:
- `test_full_flow.py` (7 tests): Quote caching, trade classification, session aggregation, foreign tracking, index tracking, derivatives basis, market snapshot generation
- `test_foreign_tracking.py` (4 tests): Delta computation, speed calculation, acceleration tracking, summary aggregation
- `test_alert_flow.py` (3 tests): VOLUME_SPIKE, PRICE_BREAKOUT, FOREIGN_ACCELERATION alert generation + WS broadcast
- `test_reconnect_recovery.py` (4 tests): SSI disconnect handling, graceful reconnect, data continuity, client reconnect resilience
- `test_session_lifecycle.py` (5 tests): ATO/Continuous/ATC phase routing, volume breakdown accumulation, session boundary resets

**Performance Profiling Suite** (`backend/scripts/`):
- `profile-performance-benchmarks.py` (11.5KB) — CPU profiling (cProfile), memory tracking (tracemalloc), asyncio monitoring, DB pool health
- `generate-benchmark-report.py` (11KB) — Markdown report generator with pass/fail criteria (≥5000 msg/s, ≤0.5ms latency)
- `docs/benchmark-results.md` — Auto-generated report with performance baselines (58,874 msg/s throughput, 0.017ms avg latency)

**Key Metrics** (verified via profiling):
- Throughput: 58,874 msg/s (target ≥5000 msg/s) ✅
- Avg latency: 0.017ms (target ≤0.5ms) ✅
- Memory: Graceful degradation when DB unavailable ✅
- All E2E scenarios: 0% error rate ✅

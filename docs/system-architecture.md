# System Architecture

## High-Level Overview

```
SSI FastConnect WebSocket (fc-datahub.ssi.com.vn)
├─ X:ALL     Trade + Quote (RType="X", split via parse_message_multi)
├─ R:ALL     Foreign investor (cumulative FBuyVol, FSellVol)
├─ MI:ALL    VN30 + VNINDEX indices
└─ B:ALL     OHLC bars
           │
           ▼
    FastAPI Backend (Python 3.12, uvloop, asyncio)
           │
    ┌──────┴─────────────────────────────────────┐
    ▼                                             ▼
Market Data Processing                    Analytics & REST API
├─ QuoteCache (bid/ask)                  ├─ AlertService (6 signal types)
├─ TradeClassifier (MUA/BAN/NEUTRAL)     ├─ PriceTracker (real-time detection)
├─ SessionAggregator (ATO/Cont/ATC)      ├─ BacktestEngine (correlation analysis)
├─ ForeignInvestorTracker (speed/accel)  ├─ REST Routers (market, history, backtest)
├─ IndexTracker (breadth metrics)        └─ WebSocket Router (4 channels)
└─ DerivativesTracker (basis calc)
           │
           ▼
    TimescaleDB (PostgreSQL 16)
    ├─ Hypertables: trades, foreign_snapshots, index_snapshots, basis_points, alerts
    └─ Continuous aggregates: order_velocity_1m, vn30_basket_velocity_1m
           │
           ▼
React Frontend (React 19, TypeScript)
├─ Price Board (VN30 with sparklines)
├─ Foreign Flow (sector aggregation + cumulative flow)
├─ Derivatives (basis trends)
├─ Signals/Alerts (real-time feed)
├─ Volume Analysis (session breakdown)
└─ Backtest Dashboard (correlation analysis)
```

## Backend Architecture

### Data Processing Pipeline (Phases 1-3)

**SSI Services** (6 services):
- SSIAuthService: OAuth2 token management (SimpleNamespace config, requires attribute access)
- SSIMarketService: REST API for market lookups (fc-data.ssi.com.vn domain)
- SSIStreamService: WebSocket connection (fc-datahub.ssi.com.vn domain — DIFFERENT!)
- SSIFieldNormalizer: Field mapping + parse_message_multi() for X:ALL splitting
- FuturesResolver: Active VN30F contract detection with manual override support
- Message models for SSI data types

**Core Processing** (6 stateful services in MarketDataProcessor):
- **QuoteCache**: Stores latest bid/ask; accessed by trade classifier
- **TradeClassifier**: MUA/BAN/NEUTRAL classification using bid/ask; uses per-trade `LastVol` (critical!)
- **SessionAggregator**: Routes trades to ATO/Continuous/ATC phase buckets; invariant validation
- **ForeignInvestorTracker**: Delta computation from cumulative SSI data, 5-min speed window
- **IndexTracker**: VN30/VNINDEX values with breadth ratios and 1440-point sparkline
- **DerivativesTracker**: Basis = futures - spot; multi-contract with volume-based active selection

**Critical Notes**:
- Uses per-trade `LastVol` NOT cumulative `TotalVol`
- Two SSI domains: REST=fc-data.ssi.com.vn, WebSocket=fc-datahub.ssi.com.vn (DIFFERENT!)
- X:ALL channel splits into Trade+Quote via parse_message_multi()
- Session phases: ATO (opening), Continuous (regular), ATC (closing)
- All services resetable (daily at 15:00 VN), thread-safe (asyncio), ~655 KB memory bounded

### Analytics & Persistence (Phases 6-7)

**Alert Infrastructure**:
- AlertService: In-memory buffer (deque maxlen=500), 60s dedup by (type, symbol)
- 6 Alert types: VOLUME_SPIKE, PRICE_BREAKOUT, FOREIGN_ACCELERATION, BASIS_DIVERGENCE, VELOCITY_DIVERGENCE, IMBALANCE_EXTREME
- Severity: INFO, WARNING, CRITICAL

**PriceTracker** (Real-time signal detection):
- VOLUME_SPIKE: vol > 3× avg (20-min window)
- PRICE_BREAKOUT: price hits ceiling/floor
- FOREIGN_ACCELERATION: |net_value_Δ| > 30% (5-min window)
- BASIS_DIVERGENCE: Basis crosses zero
- VELOCITY_DIVERGENCE: Buy velocity up, price flat (WARNING)
- IMBALANCE_EXTREME: Buy/sell ratio > 3× (WARNING)
- Callbacks wired: on_trade(), on_foreign(), on_basis_update()

**BacktestEngine** (Cross-correlation analysis):
- Computes Pearson correlation(velocity[t-k], price_change[t]) for k=0..10 min
- Threshold discovery: Bin imbalance_ratio, compute P(price_up|bin)
- Pattern analysis: Group by hour-of-day + session phase
- Daily pre-compute at 15:30 VN; results cached for instant summary retrieval
- 4 REST endpoints: /summary, /correlation, /threshold, /patterns

**Database Layer**:
- Connection pool (configurable min/max) with 60s health checks
- Alembic migrations: 5 hypertables + 2 continuous aggregates
- Graceful startup: App continues without DB (logs warning)
- Health endpoint reports database status

### REST & WebSocket API (Phase 4-5)

**REST Routers** (44 endpoints):
- health_router: GET /health (with DB status)
- market_router: /snapshot, /foreign-detail, /volume-stats, /basis-trend, /alerts, /velocity, /velocity/history, /velocity/basket-history
- history_router: /history/{symbol}/{candles,ticks,foreign}, /index/{name}, /derivatives/{contract}
- backtest_router: /backtest/{summary,correlation,threshold,patterns}

**WebSocket Channels** (4 real-time streams):
- /ws/market: Full MarketSnapshot (500ms throttle)
- /ws/foreign: ForeignSummary only (500ms throttle)
- /ws/index: Index data only (500ms throttle)
- /ws/alerts: Real-time alerts (no throttle)

**Features**:
- Token-based optional auth (WS_AUTH_TOKEN env)
- IP-based rate limiting (WS_MAX_CONNECTIONS_PER_IP)
- Per-client async queues (non-blocking distribution)
- Application-level heartbeat (30s ping, 10s timeout)
- Event-driven DataPublisher with per-channel throttle

## Frontend Architecture

**Dashboard Pages** (8 pages, ~70 components):
- Price Board: VN30 stock list with sparklines, flash animation, color coding
- Derivatives: Futures basis trends, convergence indicator
- Foreign Flow: Sector aggregation, cumulative intraday flow, top buy/sell tables
- Volume Analysis: Trade classification, session phase breakdown
- Signals: Real-time alert feed with type + severity filters
- Backtest: Correlation charts, threshold tables, pattern heatmaps
- Velocity: Order velocity comparison (VN30F vs VN30 basket)

**Data Fetching Patterns**:
- useWebSocket<T>: Generic hook with auto-reconnect + REST fallback
- usePriceBoardData: VN30-filtered, sparkline accumulation
- useForeignFlow: Hybrid WS (summary) + REST polling (detail)
- useVelocityData: WS snapshot + REST history polling
- useBacktestData: Pre-computed summary polling + on-demand parallel analysis

**Key Features**:
- Exponential backoff reconnection (1s → 30s cap)
- REST polling fallback after 3 failed WS attempts
- Generation counter prevents stale data overwrites
- Session-aware cumulative flow reset (daily)
- Color coding: VN market conventions (red=up, green=down)

## Production Deployment

**Docker Services** (7 containers):
- Nginx (reverse proxy, Alpine): Port 80 → frontend/backend/ws routing
- Backend (FastAPI, non-root user): Python 3.12, uvloop, connection pool
- Frontend (React static, Nginx): Multi-stage build, gzip compression
- TimescaleDB (PostgreSQL 16): Persistent hypertables + continuous aggregates
- Prometheus (v2.53.0): /metrics scraping, 30-day retention
- Grafana (v11.1.0): 4 auto-provisioned dashboards, Prometheus data source
- Node Exporter (v1.8.1): System metrics (CPU, memory, disk, network)
  - NOTE: Skipped on macOS (rslave mount incompatibility)

**Network**: Bridge network (app-network) with service discovery via DNS

**Configuration**: All via `.env` file (credentials, database, WebSocket params, CORS)

**Graceful Startup**: App works without database (history endpoints return 503, market data flows)

## CI/CD Pipeline

**GitHub Actions** (`.github/workflows/ci.yml`):
- Backend job (Python 3.12): pytest with 80% coverage enforcement (15min timeout)
- Frontend job (Node 20): npm build (10min timeout)
- Docker job: docker-compose build production images (20min timeout)

**Triggers**: Push to master/main, all PRs

**Quality Gates**: 80% coverage minimum, all tests pass, Docker builds succeed

## Performance & Testing

**Test Coverage**:
- 280+ unit tests (core services + APIs)
- 40+ router tests (all endpoints)
- 35+ WebSocket tests
- 31+ PriceTracker tests (all signal types)
- 435+ Backtest tests (engine + router)
- 23+ E2E tests (full system integration)
- **Total**: 434+ tests, 84% code coverage

**Performance Baselines** (verified via profiling):
- Message throughput: 58,874 msg/s (target ≥5000 msg/s)
- Trade classification latency: <1ms per trade
- WS p99 latency: 85-95ms (target <100ms)
- REST p95 latency: 175-195ms (target <200ms)
- Reconnect time: <1s
- Memory: Bounded, ~655 KB core services + capped history windows

**Load Testing**: Locust framework with 4 scenarios (market_stream, foreign_flow, burst_test, reconnect_storm)

## Deployment Status

- **Infrastructure**: 7 Docker containers, all health checks passing
- **Database**: TimescaleDB with 5 hypertables + 2 continuous aggregates
- **Monitoring**: Prometheus + Grafana with 4 dashboards
- **Tests**: 434+ tests passing (84% coverage enforced)
- **Code**: Python 3.12, React 19, TypeScript strict mode

---

For detailed API endpoints, see [API Reference](./api-reference.md)
For deployment procedures, see [Deployment Guide](./deployment-guide.md)
For codebase details, see [Codebase Summary](./codebase-summary.md)

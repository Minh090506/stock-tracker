# Project Changelog

All notable changes to the VN Stock Tracker project.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)

---

## [Unreleased]

### In Progress
- Phase 9: Advanced features (GraphQL API, Redis caching, WebSocket compression)

---

## [Deployment Fixes] - 2026-02-11

### Critical Bug Fixes

**SSI FastConnect URL Configuration**:
- FIXED: SSI uses TWO different domains, not one
  - REST API: `https://fc-data.ssi.com.vn/` (market data lookups)
  - WebSocket/SignalR: `https://fc-datahub.ssi.com.vn/` (streaming) — DIFFERENT!
- Impact: Incorrect SSI_STREAM_URL caused 502 Bad Gateway errors in Docker deployment
- Files Updated: `.env.example`, deployment documentation

**SSI Channel Names (Corrected)**:
- FIXED: Channel subscription syntax was incorrect
  - OLD (WRONG): `X-TRADE:ALL`, `X-Quote:ALL`, `MI:VN30`, `MI:VNINDEX`, `X:VN30F{YYMM}`, `B:ALL`
  - NEW (CORRECT): `X:ALL`, `R:ALL`, `MI:ALL`, `B:ALL`
- Reason: SSI v2.2.2 only allows one subscription per channel type; `X:ALL` combines Trade+Quote
- Implementation: `parse_message_multi()` splits RType="X" messages into separate Trade+Quote results
- Files Updated: `ssi_stream_service.py`, system-architecture.md

**SSI Auth Service Configuration**:
- FIXED: ssi-fc-data v2.2.2 requires SimpleNamespace (attribute access), not dict
- FIXED: Authentication now uses SSIAccessTokenRequest dataclass from ssi_fc_data.model.model
- Impact: Dict-based config caused AttributeError during OAuth2 authentication
- Files Updated: `ssi_auth_service.py`, codebase-summary.md

**SSI Market Service**:
- FIXED: REST API calls now use proper dataclasses (IndexComponentsReq, SecuritiesReq)
- Impact: Improves type safety and alignment with ssi-fc-data v2.2.2 API
- Files Updated: `ssi_market_service.py`

**SSI Field Normalizer**:
- FIXED: Handles double JSON parsing — SSI Content field is JSON string inside dict
- FIXED: Integrated `parse_message_multi()` to split combined X:ALL messages
- Impact: Prevents JSON decode errors and message duplication
- Files Updated: `ssi_field_normalizer.py`

### Deployment Milestone

**Docker Deployment - 2026-02-11** ✅
- Successfully deployed on macOS with docker-compose.prod.yml
- 6 services running (7 minus Node Exporter which requires Linux rslave mount):
  - Nginx (reverse proxy)
  - Backend (FastAPI with uvloop)
  - Frontend (React static site)
  - TimescaleDB (PostgreSQL 16)
  - Prometheus (metrics)
  - Grafana (dashboards)
- Data validation:
  - 2004 quotes flowing
  - 2004 prices updated
  - 29 indices tracked
  - Derivatives basis calculated correctly
  - All health checks passing

**Configuration Changes**:
- Updated .env.example with correct SSI URLs (two domains)
- Added troubleshooting guide for SSI stream connection issues
- Documented Node Exporter incompatibility on macOS (rslave mount not supported)

### Testing
- All 380 tests passing (84% coverage enforced)
- Performance baselines verified during deployment
- No new test failures or regressions

### Documentation Updates
- `system-architecture.md` — Fixed SSI channel names, removed duplicate content, noted domain separation
- `deployment-guide.md` — Fixed SSI_STREAM_URL, added troubleshooting section, documented macOS note
- `codebase-summary.md` — Updated Phase 2 with SimpleNamespace config and parse_message_multi
- `project-overview-pdr.md` — Added SSI URL configuration and deployment status
- `development-roadmap.md` — Updated Phase 8 completion and deployment milestone

### Version Info
- Python: 3.12.12
- ssi-fc-data: v2.2.2 (requires attribute access for config)
- Docker: Verified on Docker Desktop for Mac

---

## [Phase 8D - Monitoring Stack & Documentation] - 2026-02-11

### Added

**Prometheus Metrics Instrumentation**:
- `backend/app/metrics.py` (74 LOC) with prometheus-client>=0.21.0
- HTTP request duration histogram (buckets: 0.01, 0.1, 1, 10s)
- Counters for SSI messages, WS connections, trade classifications, alerts, DB writes
- `/metrics` endpoint for Prometheus scraping

**Monitoring Stack** (docker-compose.prod.yml updated):
- Prometheus v2.53.0 — Scrapes /metrics every 30s, 30-day retention
- Grafana v11.1.0 — 4 auto-provisioned dashboards (App Performance, WS, Database, System)
- Node Exporter v1.8.1 — System metrics (CPU, memory, disk, network)

**Documentation Suite** (5 new files):
- `docs/README.md` — Documentation index and navigation
- `docs/api-reference.md` — API endpoint documentation
- `docs/architecture.md` — System architecture detailed diagrams
- `docs/deployment.md` — Production deployment procedures
- `docs/monitoring.md` — Grafana dashboards and metrics guide

**Deployment Script**:
- `scripts/deploy.sh` — One-command deployment with preflight checks
- Verifies Docker, Docker Compose, environment configuration
- Health checks post-deployment
- System resource reporting

### Docker Compose Updates
- Added Prometheus service (port 9090, persistent volume)
- Added Grafana service (port 3000, persistent volume, auto-provisioned dashboards)
- Added Node Exporter service (port 9100)
- Updated dependency chain for service health checks
- Total services: 7 (Nginx, Backend, Frontend, TimescaleDB, Prometheus, Grafana, Node Exporter)

### Status
**Phase 8D: 100% COMPLETE** — Monitoring stack operational, all documentation updated

---

---

## [Phase 8C - E2E Tests & Performance Profiling] - 2026-02-11

### Added

**E2E Test Suite** (`backend/tests/e2e/`, 790 LOC, 23 tests):
- `test_full_flow.py` (155 LOC, 7 tests) — SSI → processor → WS client end-to-end pipeline
- `test_foreign_tracking.py` (90 LOC, 4 tests) — Foreign investor tracking E2E scenarios
- `test_alert_flow.py` (118 LOC, 3 tests) — Alert generation and WebSocket delivery
- `test_reconnect_recovery.py` (87 LOC, 4 tests) — SSI disconnect/reconnect handling
- `test_session_lifecycle.py` (97 LOC, 5 tests) — ATO/Continuous/ATC session transitions
- `conftest.py` (242 LOC) — Shared fixtures, mock SSI services, test harness

**Performance Profiling Suite**:
- `profile-performance-benchmarks.py` (11.5KB) — CPU, memory, asyncio, DB pool profiling
- `generate-benchmark-report.py` (11KB) — Markdown report generator with pass/fail criteria
- `docs/benchmark-results.md` — Auto-generated performance baseline report

**Coverage**:
- Full system integration: SSI connection → data processing → WS broadcast → client consumption
- Alert detection and notification flows (VOLUME_SPIKE, PRICE_BREAKOUT, FOREIGN_ACCELERATION, BASIS_DIVERGENCE)
- Resilience scenarios: SSI reconnect, client reconnect, queue overflow, error handling
- Session phase transitions: ATO → Continuous → ATC with volume breakdown validation

**Performance Baselines** (verified via profiling):
- Throughput: 58,874 msg/s (target ≥5000 msg/s) ✅
- Avg latency: 0.017ms (target ≤0.5ms) ✅
- Memory: Graceful degradation when DB unavailable
- All metrics within targets

### Files Created
- `backend/tests/e2e/` (5 test modules + conftest + __init__)
- `backend/scripts/profile-performance-benchmarks.py`
- `backend/scripts/generate-benchmark-report.py`
- `docs/benchmark-results.md` (auto-generated)

### Testing Strategy
- E2E tests isolated from unit tests (separate conftest, mock SSI services)
- Real asyncio event loop, real WebSocket connections (via Starlette TestClient)
- Mock SSI stream to simulate real-world message sequences
- Validates: data transformation accuracy, alert triggering logic, WS broadcast integrity, reconnect recovery

### Status
**Phase 8C: 100% COMPLETE** — E2E test suite + performance profiling operational with verified baselines

---

## [Phase 8B - Load Testing Suite] - 2026-02-11

### Added

**Locust Framework** with 4 load test scenarios:
- `market_stream.py` (100 LOC) — WebSocket /ws/market, 100-500 users, WS p99 <100ms
- `foreign_flow.py` (95 LOC) — WebSocket /ws/foreign, 50-200 users, p99 <100ms
- `burst_test.py` (85 LOC) — REST /api/market/snapshot, 500 req/s, p95 <200ms
- `reconnect_storm.py` (80 LOC) — WS connection churn, reconnect <2s, zero data loss

**Docker Integration**: `docker-compose.test.yml` (master/worker architecture)
**CI Smoke Test**: Automated 10 users × 30s on master push
**Runner Script**: `scripts/run-load-test.sh` with configurable parameters
**Performance Verified**: WS p99 85-95ms, REST p95 175-195ms, reconnect <1s, 0% errors

### Files Created
- `backend/locust_tests/` (4 scenario files + helper.py)
- `docker-compose.test.yml`
- `scripts/run-load-test.sh`

### Configuration
- `LOAD_TEST_USERS=100`, `LOAD_TEST_DURATION=300`, `LOAD_TEST_SPAWN_RATE=10`
- Test environment only: `WS_MAX_CONNECTIONS_PER_IP=1000` override

### Status
**Phase 8B: 100% COMPLETE** — Load testing suite operational with verified performance baselines

---

## [Phase 8A - CI/CD Pipeline] - 2026-02-10

### Added

**GitHub Actions Workflow** (`.github/workflows/ci.yml`, 82 LOC):
- 3-job pipeline: backend (Python 3.12) → frontend (Node 20) → docker-build
- Backend: pytest with 80% coverage enforcement (`--cov-fail-under=80`)
- Frontend: npm build (conditional tests)
- Docker: production image build verification
- Triggers: Push to master/main, all pull requests
- Timeouts: backend (15min), frontend (10min), docker (20min)

**Test Dependencies** (`backend/requirements-dev.txt`):
- pytest==8.3.5, pytest-cov==6.0.0, pytest-asyncio==0.24.0, httpx==0.28.1

### Quality Gates
- Backend: 80% minimum coverage (enforced, build fails if below)
- Frontend: Build must succeed
- Docker: Images must build without errors
- All tests pass before merge allowed

### Status
**Phase 8A: 100% COMPLETE** — CI/CD pipeline operational, all tests passing

---

## [Phase 7 - Database Persistence] - 2026-02-10

### Added

**Connection Pool** (`backend/app/database/pool.py`):
- Configurable pool (DB_POOL_MIN=2, DB_POOL_MAX=10)
- Health checks every 60s
- Graceful startup: app continues without DB (logs warning)
- Automatic reconnection on failure

**Alembic Migrations** (`backend/alembic/`):
- 5 hypertables: trades, foreign_snapshots, index_snapshots, basis_points, alerts
- TimescaleDB 2.16 on PostgreSQL 16
- docker-compose.prod.yml service with persistent volume

**Graceful Startup**:
- If DATABASE_URL not set: app starts with warning, DB mode disabled
- Market data processing continues unaffected
- History endpoints return 503 Service Unavailable when DB unavailable
- Health endpoint reports: `{"status": "ok", "database": "connected"|"unavailable"}`

### Configuration
- New env vars: `DB_POOL_MIN`, `DB_POOL_MAX`, `DATABASE_URL` (optional)
- Dependencies: alembic>=1.14.0, psycopg2-binary>=2.9.0

### Status
**Phase 7: 100% COMPLETE** — PostgreSQL persistence with Alembic migrations + graceful startup

---

## [Phase 7A - Volume Analysis Session Breakdown] - 2026-02-10

### Added

**Session Phase Tracking**:
- New model: SessionBreakdown (per-phase volume split: mua/ban/neutral)
- Updated SessionStats with ato/continuous/atc breakdown fields
- ClassifiedTrade preserves trading_session field from SSI

**SessionAggregator Enhancement**:
- Router logic maps phase to breakdown bucket
- Per-trade accumulation updates both overall totals AND phase bucket
- 28 unit tests with invariant validation (sum of phases == totals)

**Frontend Volume Analysis**:
- useVolumeStats hook polls /api/market/volume-stats
- volume-detail-table: Buy/sell pressure bars per session phase
- volume-session-comparison-chart: Stacked bar comparing phase contribution

### Status
**Phase 7A: 100% COMPLETE** — Session breakdown with per-phase volume analysis

---

## [Phase 6 - Analytics Engine] - 2026-02-10

### Added (Complete)

**Backend**:
- AlertService (in-memory buffer, deque maxlen=500, 60s dedup by type+symbol)
- PriceTracker (4 signal types: VOLUME_SPIKE, PRICE_BREAKOUT, FOREIGN_ACCELERATION, BASIS_DIVERGENCE)
- REST endpoint: GET /api/market/alerts?limit=50&type=&severity=
- WebSocket channel: /ws/alerts
- Callbacks wired: on_trade(), on_foreign(), on_basis_update()

**Frontend**:
- useAlerts hook (WS stream + REST fallback + dedup + sound notifications)
- signal-filter-chips: Type + severity dual filter
- signal-feed-list: Real-time alert cards with icons, timestamps, auto-scroll
- signals-page: Connection status, sound toggle, error banner

### Signal Details
- VOLUME_SPIKE: vol > 3× avg over 20min, WARNING severity
- PRICE_BREAKOUT: price hits ceiling/floor, CRITICAL severity
- FOREIGN_ACCELERATION: |net_value_Δ| >30% in 5min, WARNING severity
- BASIS_DIVERGENCE: basis crosses zero (premium↔discount), WARNING severity

### Tests
- 31 PriceTracker tests (all passing)
- 357 total tests (84% coverage)
- All signal types validated, backends integration verified

### Status
**Phase 6: 100% COMPLETE** — Full analytics engine with alerts + signal detection + frontend UI

---

## [Phase 5C - Foreign Flow Dashboard] - 2026-02-10

### Added

**Hybrid Data Flow**:
- WS /ws/foreign → ForeignSummary (real-time aggregate)
- REST /api/market/foreign-detail (10s poll) → stocks[] (per-symbol detail)

**New Components** (7 files, ~689 LOC):
- vn30-sector-map.ts (53 LOC) — Static VN30 sector mapping
- foreign-sector-bar-chart.tsx (103 LOC) — Net buy/sell by sector
- foreign-cumulative-flow-chart.tsx (90 LOC) — Intraday cumulative flow with session-date reset
- foreign-top-stocks-tables.tsx (81 LOC) — Top 10 net buy + sell
- use-foreign-flow.ts (102 LOC) — Hybrid WS+REST hook
- foreign-flow-page.tsx (69 LOC) — Updated layout
- foreign-flow-skeleton.tsx (61 LOC) — Updated skeleton

### Performance
- WS latency: <100ms
- REST polling: 10s interval (low overhead)
- Sector chart render: <50ms
- Cumulative chart render: <100ms with 1440 points

### Status
**Phase 5C: 100% COMPLETE** — Foreign flow dashboard with hybrid architecture

---

## [Phase 5A/5B - Frontend Dashboard] - 2026-02-09

### Added

**Price Board** (Phase 5A):
- price-board-table.tsx — Sortable table with flash animation
- price-board-sparkline.tsx — Inline SVG (50 points max)
- PriceData model (last_price, change, change_pct, ref, ceiling, floor)
- usePriceBoardData hook with VN30 filtering

**Derivatives Panel** (Phase 5B):
- derivatives-page.tsx — Basis analysis panel
- basis-trend-area-chart.tsx — Recharts AreaChart (30-min history)
- convergence-indicator.tsx — Premium/discount detection
- useDerivativesData hook (WS market + REST basis-trend polling)

**REST API Routers**:
- market_router.py: /snapshot, /foreign-detail, /volume-stats, /basis-trend
- history_router.py: /{symbol}/{candles,ticks,foreign}, /index/{name}, /derivatives/{contract}

### Performance
- Price board latency: <100ms
- Basis trend polling: 10s interval
- Chart render: <100ms

### Tests
- 38 new router tests
- 326 total tests passing
- Code quality: A- grade

### Status
**Phases 5A/5B: 100% COMPLETE** — Frontend dashboard + REST API routers

---

## [Phase 4 - Backend WebSocket Router] - 2026-02-08 to 2026-02-09

### Added

**Multi-Channel WebSocket Router** (`router.py`):
- 3 channels: /ws/market (full snapshot), /ws/foreign (flow only), /ws/index (indices only)
- Token-based auth (optional query param ?token=xxx)
- IP-based rate limiting (WS_MAX_CONNECTIONS_PER_IP)
- Application-level heartbeat (30s ping, 10s timeout)

**ConnectionManager** (`connection_manager.py`):
- Per-client asyncio queues (non-blocking distribution)
- Connection lifecycle management
- Queue overflow protection (maxsize=50)

**DataPublisher** (`data_publisher.py`):
- Event-driven reactive broadcasting (replaces poll-based loop)
- Per-channel throttle (default 500ms, configurable via WS_THROTTLE_INTERVAL_MS)
- SSI disconnect/reconnect status notifications

**Configuration**:
- ws_throttle_interval_ms (500ms default)
- ws_heartbeat_interval (30s)
- ws_heartbeat_timeout (10s)
- ws_queue_size (50)
- ws_auth_token (optional)

### Tests
- 37 new Phase 4 tests (11 ConnectionManager + 7 router + 15 DataPublisher)
- 269 total tests passing

### Status
**Phase 4: 100% COMPLETE** — Event-driven WebSocket multi-channel router

---

## [Phase 3 - Data Processing Core] - 2026-02-07

### Added (Complete)

**Phase 3A: Trade Classification**
- QuoteCache, TradeClassifier, SessionAggregator
- Per-trade LastVol (NOT cumulative TotalVol) ✓ CORRECTED
- Session phase tracking (ATO/Continuous/ATC)
- 20+ unit tests

**Phase 3B: Foreign & Index Tracking**
- ForeignInvestorTracker (delta + speed calculation, 5-min window)
- IndexTracker (VN30/VNINDEX with breadth indicators)
- 56+ unit tests (29 foreign + 27 index)

**Phase 3C: Derivatives Tracking**
- DerivativesTracker (basis = futures - spot, multi-contract support)
- 34 Phase 3C tests, 100+ tick integration tests

**Unified API**:
- MarketDataProcessor orchestrating all services
- get_market_snapshot() aggregating all data
- 232 total Phase 3 tests passing

### Status
**Phase 3: 100% COMPLETE** — Full data processing core with trade classification, foreign tracking, index monitoring, derivatives basis calculation

---

## [Phase 2 - SSI Integration & Stream Demux] - 2026-02-06 to 2026-02-07

### Added

**OAuth2 Authentication** (`ssi_auth_service.py`)
**WebSocket Connection** (`ssi_stream_service.py`)
**REST API Client** (`ssi_market_service.py`)
**Field Normalization** (`ssi_field_normalizer.py`)
**Futures Resolver** (`futures_resolver.py`)
**Message Models** (`ssi_messages.py`)

### Tests
- 60+ unit tests covering all services
- OAuth2 flow, WebSocket connection, message parsing, field mapping
- All tests passing

### Status
**Phase 2: 100% COMPLETE** — SSI integration with live WebSocket connection + message demultiplexing

---

## [Phase 1 - Project Scaffolding] - 2026-02-06

### Added

**FastAPI Application** (`app/main.py`):
- Lifespan context for startup/shutdown
- Health check endpoint

**Configuration** (`app/config.py`):
- Pydantic-settings for .env variables

**Docker Setup**:
- Dockerfile (multi-stage build)
- docker-compose.yml

### Status
**Phase 1: 100% COMPLETE** — FastAPI + Docker scaffolding complete

---

## Summary of Completed Phases

| Phase | Status | Key Achievement | Tests |
|-------|--------|-----------------|-------|
| 1-2 | ✅ | FastAPI + SSI Integration | 65 |
| 3 | ✅ | Trade/Foreign/Index/Derivatives Processing | 232 |
| 4 | ✅ | Event-Driven WebSocket Router | 269 |
| 5A-5C | ✅ | Frontend Dashboard (Price + Derivatives + Foreign) | 326 |
| 6 | ✅ | Analytics Engine (Alerts + PriceTracker) | 357 |
| 7 | ✅ | PostgreSQL Persistence + Alembic | 357 |
| 7A | ✅ | Session Breakdown (ATO/Continuous/ATC) | 357 |
| 8A | ✅ | GitHub Actions CI/CD (3-job pipeline) | 357 |
| 8B | ✅ | Load Testing Suite (Locust 4 scenarios) | - |
| 8C | ✅ | E2E Tests + Performance Profiling | 380 |
| 8 | 🔄 | Production Monitoring (remaining) | 380 |

**Overall Status**: 95% complete (9 of 10 phase-groups complete + monitoring), 394 tests passing (23 E2E + 357 unit/integration, 80% coverage enforced)
**Latest Change**: 2026-02-11 — Phase 8D Monitoring stack (Prometheus + Grafana) + documentation suite + deploy.sh COMPLETE

# Development Roadmap

**Last Updated**: 2026-02-09 15:55
**Overall Progress**: 75% (6 of 8 phases complete, Phase 5B includes API routers)

## Phase Overview

| # | Phase | Status | Progress | ETA | Tests | Notes |
|---|-------|--------|----------|-----|-------|-------|
| 1 | Project Scaffolding | ✅ COMPLETE | 100% | ✓ | Setup | FastAPI + config + Docker |
| 2 | SSI Integration & Stream Demux | ✅ COMPLETE | 100% | ✓ | 60+ | OAuth2 + WebSocket + field normalization |
| 3 | Data Processing Core | ✅ COMPLETE | 100% | ✓ | 232 | 3A/3B/3C: Trade, Foreign, Index, Derivatives |
| 4 | Backend WS + REST API | ✅ COMPLETE | 100% | ✓ | 269 | WebSocket multi-channel + event-driven publisher |
| 5 | Frontend Dashboard & REST Routers | ✅ COMPLETE | 100% | ✓ | 326 | Price board + derivatives + market/history endpoints |
| 6 | Analytics Engine | 🔄 IN PROGRESS | 25% | 1-2w | - | Core models + AlertService + PriceTracker complete |
| 7 | Database Persistence | 🔄 PENDING | 0% | 1-2w | - | PostgreSQL schema + ORM |
| 8 | Testing & Deployment | 🔄 PENDING | 0% | 1-2w | - | Load tests + Docker + CI/CD |

## Completed Phases

### Phase 1: Project Scaffolding ✅

**Dates**: 2026-02-06 to 2026-02-06
**Status**: Complete
**Duration**: 1 day

**Deliverables**:
- FastAPI application structure (`app/main.py`)
- Configuration management (`app/config.py` with pydantic-settings)
- Health check endpoint (`/health`)
- Docker setup (Dockerfile, docker-compose.yml)
- Python environment (venv, requirements.txt)

**Files Created**: 6
**Tests**: Core setup validated
**Review**: ✓ Approved

### Phase 2: SSI Integration & Stream Demux ✅

**Dates**: 2026-02-06 to 2026-02-07
**Status**: Complete
**Duration**: 2 days

**Deliverables**:
- OAuth2 authentication service (`ssi_auth_service.py`)
- WebSocket connection management (`ssi_stream_service.py`)
- REST API client (`ssi_market_service.py`)
- Field normalization (`ssi_field_normalizer.py`)
- Futures resolver (`futures_resolver.py`)
- SSI message models (`ssi_messages.py`)

**Files Created**: 6 services + 60+ tests
**Test Coverage**: 60+ tests, all passing
**Review**: ✓ Approved
**Key Achievement**: Live WebSocket connection with message demultiplexing by RType

### Phase 3: Data Processing Core ✅

**Dates**: 2026-02-07 (3A/3B/3C)
**Status**: Complete
**Duration**: 1 day (intensive)

**Sub-Phases**:

#### 3A: Trade Classification (COMPLETE)
- QuoteCache (`quote_cache.py`)
- TradeClassifier (`trade_classifier.py`) - CORRECTED: uses LastVol per-trade
- SessionAggregator (`session_aggregator.py`)
- Tests: 20+ unit tests

**Key Fix**: Changed from cumulative TotalVol (wrong) to per-trade LastVol (correct)

#### 3B: Foreign & Index Tracking (COMPLETE)
- ForeignInvestorTracker (`foreign_investor_tracker.py`) - with delta + speed calculation
- IndexTracker (`index_tracker.py`) - VN30/VNINDEX with breadth indicators
- Tests: 56+ unit tests (29 foreign + 27 index)

**Key Features**:
- Speed calculated over rolling 5-min window
- Acceleration tracking (speed change rate)
- Index advance/decline ratios
- Intraday sparkline (1440 points per day)

#### 3C: Derivatives Tracking (COMPLETE)
- DerivativesTracker (`derivatives_tracker.py`)
- Basis calculation: futures_price - spot_index
- Multi-contract support with volume-based active contract selection
- Unified API: MarketSnapshot aggregating all data sources
- Tests: 34 Phase 3C tests (17 derivatives + 14 processor + 3 integration)

**Key Metrics**:
- 232 total tests passing
- Performance: 34 Phase 3C tests in 0.04s
- All operations <5ms latency
- Memory: ~655 KB bounded across all services

**Files Created**: 10 services + 232 tests
**Review**: ✓ Approved with "EXCELLENT" rating

---

## Pending Phases

### Phase 4: Backend WebSocket + REST API ✅

**Dates**: 2026-02-08 to 2026-02-09
**Status**: Complete (Enhanced with event-driven publisher)
**Duration**: 2 days
**Tests**: 269 total (37 new Phase 4 tests)

**Deliverables**:
- [x] Multi-channel WebSocket router (3 channels)
- [x] ConnectionManager with per-client queues
- [x] Event-driven DataPublisher with per-channel throttle (500ms default)
- [x] SSI connection status notifications (disconnect/reconnect)
- [x] Application-level heartbeat (30s ping, 10s timeout)
- [x] Token-based authentication (optional)
- [x] IP-based rate limiting
- [x] 7 WebSocket configuration settings (added WS_THROTTLE_INTERVAL_MS)

**WebSocket Channels**:
```
GET /ws/market?token=xxx
- Full MarketSnapshot (quotes + indices + foreign + derivatives)

GET /ws/foreign?token=xxx
- ForeignSummary only (aggregate + top movers)

GET /ws/index?token=xxx
- VN30 + VNINDEX IndexData only
```

**Files Created**:
- `app/websocket/connection_manager.py` (84 LOC)
- `app/websocket/router.py` (138 LOC)
- `app/websocket/broadcast_loop.py` (56 LOC, DEPRECATED)
- `app/websocket/data_publisher.py` (158 LOC)
- `app/websocket/__init__.py` (exports)
- `tests/test_connection_manager.py` (11 tests)
- `tests/test_websocket_router.py` (7 tests)
- `tests/test_data_publisher.py` (15 tests)

**Files Modified**:
- `app/config.py` - Added ws_throttle_interval_ms (default 500)
- `app/main.py` - DataPublisher initialized, processor.subscribe() wiring
- `app/services/market_data_processor.py` - Added subscriber pattern (_notify after each update)
- `app/services/ssi_stream_service.py` - Added disconnect/reconnect status callbacks

**Files Deprecated**:
- `app/websocket/broadcast_loop.py` - Replaced by DataPublisher event-driven model

**Configuration Added**:
```python
WS_BROADCAST_INTERVAL=1.0       # [DEPRECATED] Legacy poll interval
WS_THROTTLE_INTERVAL_MS=500     # Per-channel event throttle (DataPublisher)
WS_HEARTBEAT_INTERVAL=30.0      # Ping every 30s
WS_HEARTBEAT_TIMEOUT=10.0       # Timeout after 10s
WS_QUEUE_SIZE=50                # Per-client queue limit
WS_AUTH_TOKEN=                  # Optional token (empty = disabled)
WS_MAX_CONNECTIONS_PER_IP=5     # Rate limiting per IP
```

**Test Results**: 269 tests passing (232 Phase 1-3 + 37 Phase 4)
**Review**: ✓ Approved
**Key Achievement**: Event-driven reactive broadcasting with per-channel throttle

**Dependencies**: Phase 3 complete ✓
**Unblocks**: Phase 5 (Frontend Dashboard)

### Phase 5: Frontend Dashboard: VN30 Price Board ✅

**Dates**: 2026-02-09
**Status**: Complete
**Duration**: 1 day

**Deliverables**:
- [x] Create React 19 + TypeScript project (Vite)
- [x] Implement generic WebSocket hook with auto-reconnect & REST fallback
  - `useWebSocket<T>(channel, options?)` → `{ data, status, error, isLive, reconnect }`
  - Multi-channel support: "market" | "foreign" | "index"
  - Exponential backoff (1s → 30s cap)
  - REST fallback after 3 failed attempts + periodic 30s retry
  - Generation counter prevents stale data overwrites
  - Token-based auth + clean unmount cleanup
- [x] Real-time price board with active buy/sell coloring + sparklines
  - `price-board-sparkline.tsx` - Inline SVG (50 points)
  - `price-board-table.tsx` - Sortable columns + flash animation
  - `price-board-skeleton.tsx` - Loading placeholder
  - VN color coding: red=up, green=down, fuchsia=ceiling, cyan=floor
- [x] Backend PriceData model + price cache
  - `PriceData` domain model (last_price, change, change_pct, ref, ceiling, floor)
  - `_price_cache` in MarketDataProcessor
  - Price merged with QuoteCache at snapshot time

**Files Created**:
- `frontend/src/hooks/use-price-board-data.ts` (VN30-filtered hook)
- `frontend/src/components/price-board/price-board-sparkline.tsx`
- `frontend/src/components/price-board/price-board-table.tsx`
- `frontend/src/components/ui/price-board-skeleton.tsx`
- `frontend/src/pages/price-board-page.tsx`
- Backend: Updated `domain.py`, `market_data_processor.py`, `schemas.py`

**Files Modified**:
- `frontend/src/App.tsx` - Added /price-board route, changed default redirect
- `frontend/src/components/layout/app-sidebar-navigation.tsx` - "Price Board" as first nav item
- `frontend/src/types/index.ts` - PriceData interface, MarketSnapshot.prices field

**Test Results**: 288 tests passing (unchanged from Phase 4)
**Code Review**: Grade A- | Zero new dependencies | All files <200 LOC
**Dependencies**: Phase 4 complete ✓
**Unblocks**: Phase 6

### Phase 5B: Frontend Dashboard: Derivatives + REST API Routers ✅

**Dates**: 2026-02-09
**Status**: Complete
**Duration**: 1 day
**Tests**: 326 total (38 new router tests)

**Deliverables**:
- [x] Frontend derivatives page with basis analysis
- [x] REST API routers: market_router.py + history_router.py
- [x] Comprehensive router test coverage (38 new tests)
- [x] Session indicator component
- [x] All TypeScript compiles clean

**Components Built**:
- `derivatives-summary-cards.tsx` - Contract info + basis display
- `basis-trend-area-chart.tsx` - 30-min historical basis
- `convergence-indicator.tsx` - Basis convergence/divergence
- `open-interest-display.tsx` - Graceful N/A handling
- `market-session-indicator.tsx` - Live session status badge

**API Endpoints**:
- `GET /api/market/snapshot` - Full MarketSnapshot
- `GET /api/market/foreign-detail` - Foreign summary
- `GET /api/market/volume-stats` - Volume breakdown
- `GET /api/market/basis-trend?minutes=30` - Filtered basis history
- `GET /api/history/{symbol}/{candles,ticks,foreign}` - Historical data
- `GET /api/history/index/{name}` - Index history
- `GET /api/history/derivatives/{contract}` - Futures history

**Test Coverage**:
- `test_market_router.py` - 12 endpoint tests
- `test_history_router.py` - 26 historical data tests
- All 326 tests passing with 82% coverage

**Code Quality**: A- | Zero new dependencies | All files <200 LOC

**Dependencies**: Phase 4 + Phase 5A complete ✓
**Unblocks**: Phase 6 (Analytics Engine)

### Phase 6: Analytics Engine 🔄

**Dates**: 2026-02-09 (Started)
**Status**: In Progress (25% complete)
**Estimated Duration**: 1-2 weeks
**Priority**: P3

**Completed**:
- [x] Alert domain models (alert_models.py ~39 LOC)
  - AlertType enum: FOREIGN_ACCELERATION, BASIS_DIVERGENCE, VOLUME_SPIKE, PRICE_BREAKOUT
  - AlertSeverity enum: INFO, WARNING, CRITICAL
  - Alert BaseModel: id, alert_type, severity, symbol, message, timestamp, data
- [x] AlertService core (alert_service.py ~103 LOC)
  - In-memory alert buffer (deque maxlen=500)
  - 60s dedup by (alert_type, symbol)
  - get_recent_alerts with type/severity filters
  - Subscribe/notify pattern for alert consumers
  - reset_daily clears buffer and cooldowns
- [x] PriceTracker signal detection (price_tracker.py ~180 LOC)
  - 4 signal types: VOLUME_SPIKE, PRICE_BREAKOUT, FOREIGN_ACCELERATION, BASIS_DIVERGENCE
  - Callbacks: on_trade(), on_foreign(), on_basis_update()
  - Volume history tracking (20-min window, ~1200 entries per symbol)
  - Foreign net_value history (5-min window, ~300 entries per symbol)
  - Basis flip detection via sign tracking
  - Data sources: QuoteCache, ForeignInvestorTracker, DerivativesTracker
- [x] Main app integration (alert_service + price_tracker singleton in main.py)

**In Progress**:
- MarketDataProcessor callback wiring (handle_trade → on_trade, handle_foreign → on_foreign, etc.)

**Remaining Objectives**:
- [ ] REST API endpoints (GET /api/alerts, POST /api/alerts/{id}/acknowledge)
- [ ] WebSocket alert channel (/ws/alerts)
- [ ] Frontend alert notifications (toast, banner, sidebar)
- [ ] Tests: 20+ PriceTracker + 15+ integration tests

**Signal Generation Details**:

| Signal | Trigger | Severity | Data |
|--------|---------|----------|------|
| VOLUME_SPIKE | vol > 3× avg (20min) | WARNING | last_vol, avg_vol, ratio, price |
| PRICE_BREAKOUT | price == ceiling/floor | CRITICAL | price, ceiling/floor, direction |
| FOREIGN_ACCEL | \|net_value_Δ\| > 30% (5min) | WARNING | net_value, prev_value, change_pct, direction |
| BASIS_FLIP | basis crosses zero | WARNING | basis, basis_pct, futures/spot, direction |

**Files Created**:
- `app/analytics/__init__.py`
- `app/analytics/alert_models.py`
- `app/analytics/alert_service.py`
- `app/analytics/price_tracker.py`
- `tests/test_price_tracker.py` (planned: 20+ tests)

**Files to Create**:
- `app/routers/alerts.py` (REST endpoints)
- Integration: Wire PriceTracker callbacks in MarketDataProcessor

**Dependencies**: Phase 3, 4, 5 complete ✓
**Blocking**: Phase 8

### Phase 7: Database Persistence 🔄

**Estimated Duration**: 1-2 weeks
**Priority**: P3
**Effort**: 5h planning + implementation

**Objectives**:
- [ ] Design PostgreSQL schema
- [ ] Implement migration system (Alembic)
- [ ] Create ORM models (SQLAlchemy or similar)
- [ ] Batch insert trades/foreign/index snapshots
- [ ] Implement data retention policies

**Schema Overview**:
```sql
trades (
  id, symbol, price, volume, trade_type, value,
  bid_price, ask_price, timestamp
)

foreign_snapshots (
  symbol, buy_volume, sell_volume, buy_speed, sell_speed,
  buy_accel, sell_accel, timestamp
)

index_snapshots (
  index_id, value, change, advances, declines, timestamp
)

basis_points (
  futures_symbol, futures_price, spot_value, basis,
  basis_pct, is_premium, timestamp
)

alerts (
  alert_type, symbol, value, severity, acknowledged, timestamp
)
```

**Batch Strategy**:
- Insert every 1 second (not per-trade) to reduce I/O
- Keep 30 days of trade history
- Archive older data monthly

**Files to Create**:
- `app/database/schema.py`
- `app/database/models.py`
- `app/database/repositories.py`
- Alembic migrations
- Tests: 10+ persistence tests

**Dependencies**: Phase 4 complete ✓
**Blocking**: Phase 8

### Phase 8: Testing & Deployment 🔄

**Estimated Duration**: 1-2 weeks
**Priority**: P1
**Effort**: 4h planning + implementation

**Objectives**:
- [ ] Load testing (1000+ TPS, 500+ concurrent symbols)
- [ ] End-to-end scenario testing
- [ ] Docker Compose production setup
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Performance profiling
- [ ] Documentation finalization

**Load Test Scenarios**:
- Sustained 1000 trades/sec
- 500+ symbols concurrently
- Foreign investor updates at 1Hz
- Index updates at 1Hz
- All services <5ms latency under load

**Deployment**:
- Docker images for backend + frontend
- docker-compose.yml with PostgreSQL, Redis (optional)
- Environment-specific configs (.env.production)
- Health checks, monitoring setup

**CI/CD Pipeline** (GitHub Actions):
- Run linting on push
- Run 254 tests on PR
- Build Docker images
- Deploy to staging on merge to develop
- Manual approval for production

**Files to Create/Modify**:
- `.github/workflows/test.yml`
- `.github/workflows/deploy.yml`
- `docker-compose.production.yml`
- Load test scripts
- Performance benchmarks

**Dependencies**: All phases complete ✓

---

## Timeline & Milestones

### Completed
- ✅ **2026-02-06**: Phase 1 + Phase 2 scaffolding
- ✅ **2026-02-07**: Phase 3 (3A/3B/3C) - Trade, Foreign, Index, Derivatives
- ✅ **2026-02-08 to 2026-02-09**: Phase 4 - WebSocket multi-channel router
- ✅ **2026-02-09**: Phase 5 (Price Board) - Real-time VN30 price tracking

### Next 3 Weeks (Projected)
- **Week 1 (2026-02-10 to 2026-02-14)**: Phase 5B (Index + Foreign + Derivatives UI)
- **Week 2 (2026-02-17 to 2026-02-21)**: Phase 6 (Analytics Engine)
- **Week 3 (2026-02-24 to 2026-02-28)**: Phase 7 (Database) + Phase 8 (Testing)

### Go-Live Target
- **2026-02-28**: Production ready

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|-----------|
| SSI API changes | High | Monitor SSI docs; maintain compatibility layer |
| WebSocket reconnect issues | High | Implement exponential backoff + circuit breaker |
| High trade volume (>3000 TPS) | Medium | Async processing + message batching |
| Database bottleneck | Medium | Batch writes every 1s; archive old data |
| React frontend performance | Medium | Virtual lists for large datasets; lazy loading |
| Time zone confusion | Low | All times UTC+7; document explicitly |

---

## Success Criteria by Phase

### Phase 4 ✅
- [x] Multi-channel WebSocket router (3 channels)
- [x] Token-based authentication (optional)
- [x] IP-based rate limiting
- [x] Connection/disconnection handled cleanly
- [x] Per-client queues prevent blocking
- [x] Heartbeat prevents zombie connections
- [x] Event-driven reactive broadcasting (DataPublisher)
- [x] SSI connection status notifications
- [x] 37 tests passing (11 ConnectionManager + 7 router + 4 legacy + 15 DataPublisher)

### Phase 5 ✅
- [x] Dashboard loads in <3 seconds
- [x] Real-time price updates <100ms latency (WS)
- [x] Price board displays VN30 symbols with sparklines
- [x] Sortable table with flash animation on price change
- [x] Color coding matches VN market conventions (red=up, green=down)
- [x] TypeScript compiles clean, zero new dependencies

### Phase 5B ✅
- [x] Derivatives basis analyzer (basis trends, convergence indicator)
- [x] REST API routers (market_router, history_router)
- [x] Comprehensive router test coverage (38 tests)
- [x] Session indicator component
- [ ] Index charts (VN30, VNINDEX) with intraday sparklines (future)
- [ ] Foreign investor flow dashboard (future)
- [ ] All responsive at 1920x1080 and mobile (future)

### Phase 6
- [ ] Alerts generated within 5 seconds
- [ ] >95% accuracy on buy/sell acceleration
- [ ] Basis divergence detected correctly
- [ ] Alert UI responsive and non-intrusive

### Phase 7
- [ ] Trade history queryable by date/symbol
- [ ] Batch insert <100ms per 1000 records
- [ ] Retention policies working correctly
- [ ] Database queries <50ms latency

### Phase 8
- [ ] Load test passes 1000 TPS sustained
- [ ] All 326+ tests passing in CI/CD
- [ ] Production deployment automated
- [ ] Monitoring/alerting operational

---

## Technical Debt & Cleanup

### Current Phase 3 Notes
- Daily reset at 15:00 VN trigger not yet implemented (deferred; reset methods ready)
- Basis history time-based eviction optional if data sparse
- Front-end percentage rounding handled at API/UI layer, not in backend

### Future Considerations
- Add Redis for distributed caching (if multi-instance backend)
- Implement GraphQL for flexible querying (Phase 6+)
- Add WebSocket compression for lower latency
- Consider gRPC for backend-to-frontend if latency critical

---

## Resource Requirements

**Team**: 1 full-time developer
**Infrastructure**:
- Development: Laptop/workstation
- Staging: 1x Docker host (2 vCPU, 4 GB RAM, 50 GB disk)
- Production: 2x Docker hosts (HA), PostgreSQL cluster, optional Redis

**External**:
- SSI iBoard API credentials (already have)
- PostgreSQL 16+
- Docker + Docker Compose

---

## Success Metrics (Upon Completion)

- Live market data feed: <5ms latency across 500+ symbols
- Foreign investor tracking: 1 Hz update frequency
- Futures basis analysis: Real-time with historical trend
- Dashboard responsiveness: <100ms update latency
- Uptime: >99.5% (SLA)
- Error rate: <0.1% (trades misclassified, data loss)

---

## Communication Plan

- **Weekly standup**: Every Friday 10 AM VN
- **Issues/blockers**: Async via Slack
- **Code review**: Within 24 hours
- **Documentation**: Continuous (every phase end)

---

**Current Status**: Phase 5B Complete | Phase 6 In Progress (25%) | 326 tests passing (82% coverage) | Analytics: AlertService + PriceTracker ✅ | Next: MarketDataProcessor integration + REST endpoints

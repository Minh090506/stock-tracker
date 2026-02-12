# VN Stock Tracker - Project Overview & PDR

## Project Vision

Real-time Vietnamese stock market tracking and analytics platform focused on VN30 stocks with integrated foreign investor monitoring, derivatives basis analysis, and active buy/sell classification.

## Core Features

1. **Bảng giá VN30** - Live price board for VN30 stocks with bid/ask, volume, active buyer/seller classification, and sparkline charts
2. **Chỉ số** - Real-time VN30 and VNINDEX tracking with breadth indicators and intraday charts
3. **Phái sinh** - VN30F futures tracking with basis calculation (futures - spot index), basis trend chart, convergence indicator
4. **Theo dõi NDTNN** - Foreign investor volume tracking with:
   - Real-time aggregate summary (WS)
   - Per-symbol detail tables (REST polling)
   - Sector aggregation bar chart (10 VN30 sectors)
   - Cumulative intraday flow chart with session-date reset
   - Top 10 net buy + top 10 net sell tables
5. **Mua/Bán chủ động** - Active buy/sell volume classification per trade
6. **Analytics** - Real-time alerts (VOLUME_SPIKE, PRICE_BREAKOUT, FOREIGN_ACCELERATION, BASIS_DIVERGENCE) with dual filtering and sound notifications

## Technical Stack

- **Backend**: Python 3.12+, FastAPI, asyncpg
- **Frontend**: React 19, TypeScript, Vite, TailwindCSS v4
- **Data Source**: SSI FastConnect WebSocket (exclusive, real-time)
- **Database**: PostgreSQL 16
- **Deployment**: Docker Compose

## Architecture Overview

```
SSI FastConnect WebSocket → FastAPI Backend → PostgreSQL
                                    ↓
                            Unified Market Processor
                         (Trade, Quote, Foreign, Index, Derivatives)
                                    ↓
                            React Frontend Dashboard
```

### Data Processing Pipeline

1. **Quote Messages** → QuoteCache (bid/ask storage)
2. **Trade Messages** → TradeClassifier + SessionAggregator (active buy/sell classification)
3. **Foreign Messages** → ForeignInvestorTracker (delta computation, speed tracking)
4. **Index Messages** → IndexTracker (VN30/VNINDEX updates)
5. **Futures Trades** → DerivativesTracker (basis calculation)

### Unified API

`MarketDataProcessor.get_market_snapshot()` aggregates all data:
- Stock session stats (quotes)
- Index data (VN30, VNINDEX)
- Foreign summary (totals, top movers)
- Derivatives data (basis, premium/discount)

## Functional Requirements

### Trade Classification
- Classify each trade as: Mua chủ động (active buy) | Bán chủ động (active sell) | Neutral
- Uses LastVol (per-trade volume) + cached bid/ask price
- Neutral for ATO/ATC (batch auctions)
- Accumulate per-symbol session totals

### Foreign Investor Tracking
- Compute buy/sell deltas from Channel R cumulative data
- Calculate speed (volume/minute over 5-min rolling window)
- Track acceleration (change in speed)
- Support top movers and VN30 aggregate

### Index Tracking
- Monitor VN30 and VNINDEX in real-time
- Calculate advance/decline ratios
- Maintain intraday sparkline

### Derivatives (Futures)
- Track VN30F contracts in real-time
- Compute basis = VN30F price - VN30 index value
- Detect premium (basis > 0) vs discount (basis < 0)
- Support multi-contract tracking during rollover

## Non-Functional Requirements

- **Latency**: <5ms per trade classification
- **Scale**: Support 500+ symbols
- **Reliability**: Handle WebSocket reconnects, buffer market gaps
- **Memory**: Bounded caches with configurable retention
- **Precision**: Maintain float precision for basis percentages; round at UI layer
- **MVP Scope**: VN30/HOSE only; schema includes `exchange` field for future expansion

## Configuration

All configuration via environment variables (`.env`):

```
# SSI Credentials
SSI_CONSUMER_ID=<your-id>
SSI_CONSUMER_SECRET=<your-secret>

# SSI URLs (CRITICAL: Two different domains!)
SSI_BASE_URL=https://fc-data.ssi.com.vn/          # REST API
SSI_STREAM_URL=https://fc-datahub.ssi.com.vn/     # WebSocket/SignalR (NOT fc-data.ssi.com.vn!)

# Market Data
CHANNEL_R_INTERVAL_MS=1000  # Foreign investor update frequency
FUTURES_OVERRIDE=VN30F2603,VN30F2606  # Active contracts

# Database
DATABASE_URL=postgresql://user:pass@localhost/stock_tracker

# Server
LOG_LEVEL=INFO
```

**Important**: SSI uses two different domains:
- **REST API** (market lookup): `fc-data.ssi.com.vn`
- **WebSocket/SignalR** (streaming): `fc-datahub.ssi.com.vn` (discovered during deployment 2026-02-11)

## Key Design Decisions

1. **SSI as single data source** - Includes trades, foreign, indices, and derivatives
2. **No vnstock / TCBS** - Both deprecated and unnecessary (SSI has all data)
3. **LastVol for classification** - Per-trade volume, not cumulative TotalVol
4. **asyncio.to_thread()** - ssi-fc-data is sync-only library
5. **Channel R deltas** - Compute from cumulative values to get per-update activity
6. **Unified processor** - All logic flows through MarketDataProcessor
7. **Full backend proxy** - Centralized processing, secure credentials, DB persistence

## Quality Metrics

- **Test Coverage**: 394 tests passing (phases 1-8C, 80% code coverage)
- **Performance**: All 394 tests execute in ~4s (including E2E)
- **Type Safety**: 100% type hints (Python 3.12 syntax)
- **Code Review**: All phases approved
- **Throughput**: 58,874 msg/s (verified via profiling)
- **Latency**: 0.017ms avg (target ≤0.5ms) ✅

## Phase Breakdown

| Phase | Name | Status | Tests | Details |
|-------|------|--------|-------|---------|
| 1-2 | Scaffolding + SSI Integration | ✓ Complete | 65 | FastAPI + OAuth2 + WebSocket |
| 3 | Data Processing Core | ✓ Complete | 232 | Trade, Foreign, Index, Derivatives tracking |
| 4 | Backend WS Router | ✓ Complete | 269 | Multi-channel event-driven publisher |
| 5A-5C | Frontend Dashboard | ✓ Complete | 326 | Price board + derivatives + foreign flow |
| 6 | Analytics Engine | ✓ Complete | 357 | Alerts (4 types) + PriceTracker + Frontend UI |
| 7 | Database Persistence | ✓ Complete | 357 | PostgreSQL + Alembic + connection pool |
| 7A | Session Breakdown | ✓ Complete | 357 | ATO/Continuous/ATC volume analysis |
| 8A | CI/CD Pipeline | ✓ Complete | 357 | GitHub Actions (3-job workflow) |
| 8B | Load Testing Suite | ✓ Complete | - | Locust (4 scenarios, verified performance) |
| 8C | E2E Tests + Profiling | ✓ Complete | 380 | Full system integration + performance baselines |
| 8D | Monitoring Stack | ✓ Complete | - | Prometheus + Grafana + deploy.sh + docs |

## Success Criteria

- [x] Trade classification uses per-trade LastVol + session phase tracking
- [x] Foreign tracker: live deltas, 5-min rolling speed window, acceleration
- [x] Index tracking: real-time VN30/VNINDEX with breadth + sparkline
- [x] Derivatives: basis calculation (futures - spot) + multi-contract support
- [x] All operations <5ms (357 tests prove this)
- [x] 357 tests passing, 84% code coverage
- [x] Frontend dashboard: Price Board + Derivatives + Foreign Flow (hybrid WS+REST)
- [x] WebSocket: 3 channels, token auth, IP rate limiting, event-driven publisher
- [x] Analytics: PriceTracker (4 signals) + AlertService (dedup) + REST/WS endpoints + Frontend UI
- [x] Session breakdown: ATO/Continuous/ATC volume analysis + pressure visualization
- [x] Database: PostgreSQL + Alembic migrations + connection pool + graceful startup
- [x] CI/CD: GitHub Actions (3-job pipeline, 80% coverage enforcement)
- [x] Load testing: Locust framework (4 scenarios, WS p99 <100ms, REST p95 <200ms verified)
- [x] Production monitoring: Prometheus metrics + Grafana dashboards + deploy.sh (Phase 8D complete)

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Quote before Trade | Cache fill within seconds at market open; classify as NEUTRAL initially |
| Channel R frequency | Speed calc adapts to actual interval via timestamp tracking |
| Sparse VN30F trades | Memory bounded by deque maxlen; basis history time-filtered |
| WebSocket disconnect | Implement reconnect with state recovery in Phase 4 |
| Time zone issues | All times in VN timezone (UTC+7) |

## Dependencies

- Python 3.12.12+
- Node.js 20+
- PostgreSQL 16
- Docker & Docker Compose
- SSI iBoard credentials (Cons ID + Secret)

## Team & Contact

- Developer: Minh N.
- Repository: /Users/minh/Projects/stock-tracker
- Plan: /Users/minh/Projects/stock-tracker/plans/260206-1418-vn-stock-tracker-revised/

## Deployment Status

**Successfully Deployed**: 2026-02-11 (Docker on macOS)
- 6 services running: Nginx, Backend, Frontend, TimescaleDB, Prometheus, Grafana
- Node Exporter skipped (rslave mount not supported on Docker Desktop)
- 2004 quotes, 2004 prices, 29 indices, derivatives data flowing correctly
- All health checks passing

## Next Steps

1. **Phase 9**: Documentation finalization and project handoff
2. **Phase 10**: Advanced features (GraphQL API, Redis caching for multi-instance, WebSocket compression)
3. **Production**: Deploy to staging/production environment with monitoring dashboard

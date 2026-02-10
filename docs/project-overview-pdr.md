# VN Stock Tracker - Project Overview & PDR

## Project Vision

Real-time Vietnamese stock market tracking and analytics platform focused on VN30 stocks with integrated foreign investor monitoring, derivatives basis analysis, and active buy/sell classification.

## Core Features

1. **Bảng giá VN30** - Live price board for VN30 stocks with bid/ask, volume, and active buyer/seller classification
2. **Chỉ số** - Real-time VN30 and VNINDEX tracking with breadth indicators and intraday charts
3. **Phái sinh** - VN30F futures tracking with basis calculation (futures - spot index)
4. **Theo dõi NDTNN** - Foreign investor volume tracking with speed and acceleration metrics
5. **Mua/Bán chủ động** - Active buy/sell volume classification per trade
6. **Analytics** - Foreign investor alerts, correlation analysis, basis divergence signals

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

# Market Data
CHANNEL_R_INTERVAL_MS=1000  # Foreign investor update frequency
FUTURES_OVERRIDE=VN30F2603,VN30F2606  # Active contracts

# Database
DATABASE_URL=postgresql://user:pass@localhost/stock_tracker

# Server
LOG_LEVEL=INFO
```

## Key Design Decisions

1. **SSI as single data source** - Includes trades, foreign, indices, and derivatives
2. **No vnstock / TCBS** - Both deprecated and unnecessary (SSI has all data)
3. **LastVol for classification** - Per-trade volume, not cumulative TotalVol
4. **asyncio.to_thread()** - ssi-fc-data is sync-only library
5. **Channel R deltas** - Compute from cumulative values to get per-update activity
6. **Unified processor** - All logic flows through MarketDataProcessor
7. **Full backend proxy** - Centralized processing, secure credentials, DB persistence

## Quality Metrics

- **Test Coverage**: 357 tests passing (all phases 1-6, 84% code coverage)
- **Performance**: All 357 tests execute in 3.45s
- **Type Safety**: 100% type hints (Python 3.12 syntax)
- **Code Review**: All phases approved

## Phase Breakdown

| Phase | Name | Status | Tests | Coverage |
|-------|------|--------|-------|----------|
| 1 | Project Scaffolding | ✓ Complete | 5 | Core setup |
| 2 | SSI Integration & Stream Demux | ✓ Complete | 60+ | OAuth2 + WebSocket |
| 3 | Data Processing Core | ✓ Complete | 232 | Trade, Foreign, Index, Derivatives |
| 4 | Backend WS + REST API | ✓ Complete | 269 | Multi-channel + Event-driven |
| 5A | Frontend Price Board | ✓ Complete | 288 | VN30 price + sparklines |
| 5B | Frontend Derivatives Panel | ✓ Complete | 326 | Basis trends + convergence |
| 6 | Analytics Engine | In Progress (~65%) | 357 | PriceTracker + AlertService + REST/WS endpoints wired |
| 7 | Database Persistence | Pending | - | PostgreSQL schema + ORM |
| 8 | Testing & Deployment | Pending | - | Load tests + CI/CD |

## Success Criteria

- [x] Trade classification uses per-trade LastVol
- [x] Foreign tracker computes live deltas and speed
- [x] Index tracking updates in real-time
- [x] Basis calculation correct (futures - spot)
- [x] All operations <5ms
- [x] 357 tests passing with 84% coverage
- [x] Frontend dashboard deployed (Price Board + Derivatives)
- [x] WebSocket multi-channel router with event-driven publisher
- [x] PriceTracker engine with callbacks wired to MarketDataProcessor
- [x] AlertService and alert buffer infrastructure complete
- [ ] Frontend alert notifications UI (75% of Phase 6 remaining)
- [ ] Database persistence working
- [ ] Production deployment complete

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

## Next Steps

1. **Phase 6 (Remaining ~35%)**: Frontend alert notifications UI + possible REST/WS endpoint enhancements
2. **Phase 7**: Database schema and persistence layer
3. **Phase 8**: Full testing suite and Docker deployment

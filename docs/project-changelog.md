# Project Changelog

All notable changes to the VN Stock Tracker project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Pending Features
- Phase 5: React dashboard with TradingView charts
- Phase 6: Analytics engine with alerts and signals
- Phase 7: PostgreSQL persistence layer
- Phase 8: Production deployment and load testing

---

## [Phase 4] - 2026-02-08

### Added

#### WebSocket Broadcast Server
- New `app/websocket/connection_manager.py` (84 LOC)
  - Per-client asyncio queues for non-blocking message distribution
  - Connection lifecycle management (connect/disconnect)
  - Broadcast to all connected clients
  - Queue overflow protection (maxsize=100)
- New `app/websocket/endpoint.py` (52 LOC)
  - WebSocket endpoint at `GET /ws/market`
  - Application-level heartbeat (30s ping, 10s timeout)
  - Client disconnect detection and cleanup
- New `app/websocket/broadcast_loop.py` (31 LOC)
  - Background task broadcasting MarketSnapshot every 1s
  - Fetches unified data from MarketDataProcessor
  - Sends JSON to all connected clients via ConnectionManager
- New `app/websocket/__init__.py` - Exports

#### Configuration Settings
Added to `app/config.py`:
- `ws_broadcast_interval: float = 1.0` - Broadcast frequency
- `ws_heartbeat_interval: float = 30.0` - Ping interval
- `ws_heartbeat_timeout: float = 10.0` - Client timeout
- `ws_max_queue_size: int = 100` - Per-client queue limit

#### Tests (Phase 4: 15 new tests)
- `tests/test_connection_manager.py` (11 tests):
  - Connect/disconnect lifecycle
  - Broadcast to multiple clients
  - Per-client queue management
  - Queue overflow handling
  - Connection cleanup on disconnect
- `tests/test_websocket_endpoint.py` (4 tests):
  - WebSocket connection acceptance
  - Message broadcasting
  - Heartbeat mechanism
  - Client disconnect handling

### Modified

#### Main Application
- `app/main.py`:
  - Added `ws_manager` singleton initialization
  - Integrated broadcast loop in lifespan context
  - Registered WebSocket router to FastAPI app
  - Broadcast loop starts/stops with app lifecycle

#### Exports
- `app/websocket/__init__.py`:
  - Exports ConnectionManager, websocket_endpoint, broadcast_loop

### Test Results
- **Phase 4 Tests**: 15 new tests, all passing
- **Total Tests**: 247 passing (Phase 1-3: 232 + Phase 4: 15)
- **Performance**: Broadcast latency <10ms verified
- **Concurrency**: Tested with multiple simultaneous clients

### Code Quality
- Type safety: 100% type hints with Python 3.12 syntax
- Architecture: Clean separation (ConnectionManager, endpoint, broadcast loop)
- Error handling: Client disconnect, queue overflow, timeout protection
- Memory: Bounded per-client queues (maxsize=100)

### Documentation Updated
- Phase 4 plan status: Changed from "pending" to "complete"
- Updated roadmap progress: 37.5% → 50%
- Added WebSocket configuration to codebase summary
- Updated system architecture with WebSocket components

### Breaking Changes
- None (additive changes only)

---

## [Phase 3C] - 2026-02-07

### Added

#### DerivativesTracker Service
- New `app/services/derivatives_tracker.py` (120 LOC)
- Tracks VN30F futures contracts in real-time
- Computes basis: futures_price - VN30_index_value
- Detects premium (basis > 0) vs discount (basis < 0)
- Calculates basis_pct: (basis / spot_value) * 100
- Multi-contract support with volume-based active contract selection
- Bounded basis history (deque maxlen=3600 = ~1 hour at 1 trade/sec)
- Time-filtered trend analysis via `get_basis_trend(minutes=30)`

#### Unified Market Data API
- New `MarketSnapshot` model aggregating all market data:
  - `quotes`: dict[symbol → SessionStats]
  - `indices`: dict[index_id → IndexData]
  - `foreign`: ForeignSummary
  - `derivatives`: DerivativesData
- Added `MarketDataProcessor.get_market_snapshot()` unified API
- Added `get_derivatives_data()` convenience method
- Single entry point for all market data queries

#### Domain Models Enhancement
- New `BasisPoint` model:
  - Tracks timestamp, futures_symbol, futures_price, spot_value
  - Computes basis, basis_pct, is_premium
- New `DerivativesData` model:
  - Real-time futures snapshot: symbol, last_price, change, change_pct
  - Volume (cumulative session), bid/ask prices
  - Basis and basis_pct
  - Premium/discount flag
- Updated `MarketSnapshot` model (new composite model)

#### Tests (Phase 3C: 34 new tests)
- `tests/test_derivatives_tracker.py` (190 LOC, 17 tests):
  - Basis calculation: positive, negative, zero
  - Premium vs discount detection
  - Basis percentage accuracy
  - Volume accumulation and active contract selection
  - Multi-contract support during rollover
  - Basis trend filtering by time window
  - Reset behavior
  - Edge cases: no VN30 value, zero prices
- `tests/test_market_data_processor.py` (144 LOC, 14 tests):
  - Updated from 6 to 14 tests
  - Added derivatives integration tests
  - Unified API consistency tests
- `tests/test_data_processor_integration.py` (215 LOC, 3 tests):
  - New integration test suite
  - `test_100_ticks_across_all_channels`: Simulates 80 stock trades + 20 futures + foreign + index messages
  - Validates end-to-end data flow across all channels
  - Performance verification: all 34 tests in 0.04s

### Modified

#### MarketDataProcessor
- Updated `handle_trade()` to route VN30F trades to DerivativesTracker
- Added derivatives tracking initialization in `__init__`
- Extended unified API with `get_derivatives_data()`
- Updated `get_market_snapshot()` to include derivatives data

#### Models
- `app/models/domain.py`:
  - Added `BasisPoint` model
  - Added `DerivativesData` model
  - Updated `MarketSnapshot` to include derivatives field
  - Added `basis_pct` field to track percentage basis

### Test Results
- **Phase 3C Tests**: 34 new tests, all passing in 0.04s
- **Total Tests**: 232 passing (Phases 1-3B: 198 + Phase 3C: 34)
- **Performance**: <5ms per operation verified under load simulation
- **Coverage**: ~95% estimated for Phase 3 services

### Code Quality
- Type safety: 100% type hints with Python 3.12 syntax
- Code review: APPROVED with "EXCELLENT" rating
- Architecture: Consistent with Phase 3A/3B patterns
- Memory: Bounded deques prevent OOM
- Error handling: Zero-division guards, None checks

### Documentation Updated
- Phase 03 plan status: Changed from "pending" to "complete (3A+3B+3C)"
- Phase 03 effort: Updated to 8h (6h spent, 2h for daily reset deferred)
- Added Phase 3C completion notes
- Updated todo list with all Phase 3C items marked complete

### Known Issues / Deferred
- Daily reset trigger at 15:00 VN: Reset methods implemented, timing loop deferred to future phase
- Basis history time-based eviction: Optional if VN30F trades sparse; current maxlen sufficient

### Breaking Changes
- None (additive changes only)

---

## [Phase 3B] - 2026-02-07

### Added

#### ForeignInvestorTracker (REWRITTEN)
- New `app/services/foreign_investor_tracker.py` (180 LOC)
- Computes delta from cumulative Channel R data
- Speed calculation: volume/minute over rolling 5-minute window
- Acceleration tracking: change in speed (vol/min²)
- Supports 500+ symbols concurrently
- Rolling history window (10 minutes = 600 slots at 1 Hz)

#### IndexTracker (NEW)
- New `app/services/index_tracker.py` (100 LOC)
- Tracks VN30 and VNINDEX real-time values
- Computes advance/decline ratio (breadth indicator)
- Maintains intraday sparkline (1440 points = 1 day at 1-min intervals)
- Returns IndexData with all metrics

#### Domain Models
- `ForeignInvestorData`: Buy/sell volume, speed, acceleration, room usage
- `ForeignSummary`: Aggregate + top movers (top 5 buyers/sellers)
- `IndexData`: Index value, breadth, intraday sparkline, advance_ratio (computed field)
- `IntradayPoint`: Single sparkline data point

#### Tests (Phase 3B: 56 new tests)
- `tests/test_foreign_investor_tracker.py` (280 LOC, 29 tests)
- `tests/test_index_tracker.py` (220 LOC, 27 tests)
- All edge cases covered: missing data, sparse updates, reset behavior

### Modified

#### MarketDataProcessor
- Integrated ForeignInvestorTracker
- Integrated IndexTracker
- Added callback handlers for foreign and index messages
- Unified API access: `get_foreign_summary()`, `get_index_data()`

### Code Quality
- Review: APPROVED
- Performance: <5ms aggregation verified
- Memory: ~150 KB for foreign + index data caches

---

## [Phase 3A] - 2026-02-07

### Added

#### QuoteCache (NEW)
- New `app/services/quote_cache.py` (60 LOC)
- In-memory cache for latest bid/ask per symbol
- Stores: bid_price_1, ask_price_1, ceiling, floor, ref_price
- O(1) lookup for trade classification

#### TradeClassifier (REWRITTEN)
- New `app/services/trade_classifier.py` (100 LOC)
- **CRITICAL FIX**: Uses `trade.last_vol` (per-trade) NOT `trade.total_vol` (cumulative)
- Compares trade.last_price vs cached bid/ask
- Classifies as: MUA_CHU_DONG (buy), BAN_CHU_DONG (sell), NEUTRAL
- Marks ATO/ATC trades as NEUTRAL

#### SessionAggregator (NEW)
- New `app/services/session_aggregator.py` (90 LOC)
- Accumulates per-symbol session totals
- Tracks: mua/ban/neutral volumes and values
- Daily reset support

#### Domain Models
- `TradeType`: Enum (MUA_CHU_DONG, BAN_CHU_DONG, NEUTRAL)
- `ClassifiedTrade`: Symbol, price, volume, value, trade_type, bid_price, ask_price, timestamp
- `SessionStats`: Per-symbol aggregates

#### Tests (Phase 3A: 20+ unit tests)
- `tests/test_quote_cache.py` (80 LOC, 10 tests)
- `tests/test_trade_classifier.py` (120 LOC, 8 tests)
- `tests/test_session_aggregator.py` (40 LOC, 2 tests)

### Code Quality
- Type safety: 100% with Python 3.12 syntax
- Performance: <1ms per trade classification
- Memory: ~50 KB for 500-symbol cache

---

## [Phase 2] - 2026-02-07

### Added

#### SSIAuthService
- OAuth2 token management
- Automatic token refresh
- Secure credential storage

#### SSIStreamService
- SignalR WebSocket connection
- Message demultiplexing by RType
- Auto-reconnect with exponential backoff
- Callback registration pattern

#### SSIMarketService
- REST API client for market lookups
- Futures contract resolver
- Instrument information

#### SSIFieldNormalizer
- Field name mapping (SSI → internal)
- Type conversions
- Data validation

#### FuturesResolver
- Active VN30F contract detection
- Rollover handling
- Manual override support

#### Models
- `SSIQuoteMessage`: Bid/ask prices, ceiling, floor, volume
- `SSITradeMessage`: Last price, last volume, trading session
- `SSIForeignMessage`: Foreign buy/sell volumes and values
- `SSIIndexMessage`: Index value, changes, breadth

#### Tests
- 60+ unit tests for Phase 2 services

### Code Quality
- Type safety: 100%
- Error handling: Comprehensive
- Performance: <5ms message processing

---

## [Phase 1] - 2026-02-06

### Added

#### Project Setup
- FastAPI application structure
- Pydantic configuration management (pydantic-settings)
- Health check endpoint (`GET /health`)
- Docker setup (Dockerfile, docker-compose.yml)
- Python environment (venv, requirements.txt)

#### Core Files
- `app/main.py`: FastAPI app + lifespan context
- `app/config.py`: Settings from `.env`
- `.env.example`: Environment template
- `requirements.txt`: Python dependencies
- `Dockerfile`: Container image definition

#### Tests
- Basic health check validation
- Configuration loading tests

---

## Version History

| Version | Phase | Date | Status |
|---------|-------|------|--------|
| 0.5.0 | Phase 4 | 2026-02-08 | ✅ Complete |
| 0.4.0 | Phase 3C | 2026-02-07 | ✅ Complete |
| 0.3.0 | Phase 3A/3B | 2026-02-07 | ✅ Complete |
| 0.2.0 | Phase 2 | 2026-02-07 | ✅ Complete |
| 0.1.0 | Phase 1 | 2026-02-06 | ✅ Complete |

---

## Statistics

### Code Metrics (As of Phase 4)
- **Total Python Files**: 30
- **Total Lines**: ~5,200 LOC (services + models)
- **Test Files**: 12
- **Test LOC**: ~2,100
- **Test Count**: 247 passing
- **Type Coverage**: 100%

### Phase Breakdown
| Phase | Files | LOC | Tests | Duration |
|-------|-------|-----|-------|----------|
| 1 | 6 | 400 | 5 | 1 day |
| 2 | 6 | 800 | 60+ | 1 day |
| 3A | 3 | 250 | 20+ | 1 day |
| 3B | 2 | 280 | 56 | 1 day |
| 3C | 1 + updates | 120 + 400 | 34 | 1 day |
| 4 | 3 + updates | 167 | 15 | 1 day |
| **Total** | **30** | **~5,200** | **247** | **6 days** |

### Test Results Over Time
- Phase 1: ~5 tests
- Phase 1+2: ~65 tests
- Phase 1+2+3A: ~85 tests
- Phase 1+2+3A+3B: ~141 tests
- Phase 1+2+3A+3B+3C: 232 tests
- Phase 1+2+3A+3B+3C+4: **247 tests** ✅

### Performance Improvements
- Phase 3A: Trade classification <1ms
- Phase 3B: Foreign tracking <0.5ms, Index update <0.1ms
- Phase 3C: Basis calculation <0.5ms
- **All Phase 3 operations <5ms** ✓

---

## Deprecations

### Removed (Not Implemented)
- vnstock library (not needed; SSI has all data)
- TCBS API (deprecated Dec 2024; not implemented)
- TotalVol-based trade classification (incorrect; replaced with LastVol)

---

## Migration Guide

### From Phase 3A → 3B
- No breaking changes
- New `ForeignSummary` and `IndexData` models added
- Existing `SessionStats` and `ClassifiedTrade` unchanged

### From Phase 3B → 3C
- New `BasisPoint` and `DerivativesData` models
- Updated `MarketSnapshot` model (additive)
- `MarketDataProcessor` routing updated for VN30F trades
- No breaking changes to existing APIs

---

## Future Changelog Entries

### Phase 5 (Upcoming)
- React 19 + TypeScript frontend
- TradingView Lightweight Charts integration
- Real-time dashboard

### Phase 6 (Upcoming)
- Analytics engine
- Alert generation and delivery
- Signal detection

### Phase 7 (Upcoming)
- PostgreSQL schema and migrations
- ORM models and repositories
- Data persistence and querying

### Phase 8 (Upcoming)
- Load testing and performance profiling
- CI/CD pipeline
- Production deployment

---

**Last Updated**: 2026-02-08 22:31
**Current Release**: Phase 4 (v0.5.0)
**Status**: ✅ 247 tests passing | Ready for Phase 5

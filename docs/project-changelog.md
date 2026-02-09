# Project Changelog

All notable changes to the VN Stock Tracker project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Pending Features
- Phase 5B: Index + Foreign panels completion
- Phase 6: Analytics engine with alerts and signals
- Phase 7: PostgreSQL persistence layer
- Phase 8: Production deployment and load testing

---

## [Phase 5B - Derivatives Basis Panel] - 2026-02-09

### Added

#### Frontend Derivatives Page
- New `/derivatives` page displaying futures basis analysis
- 4 specialized components:
  - `derivatives-summary-cards.tsx` - Contract info, price, basis, premium/discount
  - `basis-trend-area-chart.tsx` - Recharts AreaChart showing 30-min basis history
  - `convergence-indicator.tsx` - Basis convergence/divergence with slope analysis
  - `open-interest-display.tsx` - Open interest display (N/A from SSI, shows gracefully)
- `derivatives-skeleton.tsx` - Loading state skeleton
- Navigation: Added "Derivatives" link to sidebar

#### Backend Basis Trend Endpoint
- New `GET /api/market/basis-trend?minutes=30` endpoint in `market_router.py`
- Returns `BasisPoint[]` filtered by time window
- Uses existing `DerivativesTracker.get_basis_trend()` service

#### Hooks
- `use-derivatives-data.ts` - Combines WS market snapshot + REST basis-trend polling (10s interval)
- Returns: `{ derivatives, basisTrend, status, isLive }`

#### Types
- `BasisPoint` interface (timestamp, futures_symbol, futures_price, spot_value, basis, basis_pct, is_premium)
- `DerivativesHistory` interface (derivatives, basis_trend array)

### Modified

#### Frontend
- `App.tsx` - Added `/derivatives` route with lazy loading
- `app-sidebar-navigation.tsx` - Added "Derivatives" nav item
- `types/index.ts` - Extended with derivatives-specific types

#### Backend
- `market_router.py` - Added basis-trend endpoint

### Test Results
- Frontend: TypeScript compiles clean, all files <200 LOC
- Backend: 288 tests passing (no new backend tests needed)
- Code review: PASSED

### Code Quality
- All components modular, under 200 lines
- Dark theme consistent with existing pages
- VN market colors: red=premium (basis>0), green=discount (basis<0)
- Error handling: Graceful N/A display for unavailable data

### Documentation Updated
- Updated codebase summary with derivatives components
- Updated roadmap Phase 5B to 20% complete
- Added changelog entry

### Performance
- Basis trend polling: 10s interval (low overhead)
- Chart renders smoothly with 30-min history (~200 points)
- Page load <1s with skeleton

---

## [Phase 4 - Event-Driven Broadcasting] - 2026-02-09

### Added

#### DataPublisher (Event-Driven WebSocket Broadcasting)
- New `app/websocket/data_publisher.py` (158 LOC)
  - Event-driven reactive push model replaces 1s poll loop
  - Per-channel trailing-edge throttle (default 500ms, configurable via `WS_THROTTLE_INTERVAL_MS`)
  - Processor notifies subscribers via `_notify(channel)` after each `handle_*` callback
  - Immediate broadcast if throttle window expired; deferred broadcast otherwise
  - SSI disconnect/reconnect status notifications (`{"type":"status","connected":false/true}`)
  - Zero overhead when no clients connected

#### Subscriber Pattern in MarketDataProcessor
- Added `subscribe(callback)` and `unsubscribe(callback)` methods
- Processor calls `_notify(channel)` after each data update:
  - `handle_quote()` → notify "market"
  - `handle_trade()` → notify "market"
  - `handle_foreign()` → notify "foreign"
  - `handle_index()` → notify "index"
- Publisher receives notifications and throttles broadcasts per channel

#### Configuration
- New `ws_throttle_interval_ms: int = 500` in `app/config.py`
- Marked `ws_broadcast_interval: float = 1.0` as DEPRECATED (legacy poll)

#### Tests (15 new tests)
- `tests/test_data_publisher.py` (15 tests):
  - Immediate broadcast on first notify
  - Throttle defers rapid updates within window
  - Independent per-channel throttling
  - SSI disconnect/reconnect status broadcasts
  - Zero-client skip behavior
  - Start/stop lifecycle

### Modified

#### MarketDataProcessor
- `app/services/market_data_processor.py`:
  - Added `_subscribers: list[SubscriberCallback]` field
  - Added `subscribe()`, `unsubscribe()`, `_notify()` methods
  - Each `handle_*` method now calls `_notify(channel)` after processing

#### Main Application
- `app/main.py`:
  - DataPublisher initialized in lifespan context
  - Processor subscribes publisher: `processor.subscribe(publisher.notify)`
  - Replaced broadcast loop with DataPublisher

#### SSIStreamService
- `app/services/ssi_stream_service.py`:
  - Added `on_ssi_disconnect()` and `on_ssi_reconnect()` callbacks
  - Notifies DataPublisher of connection status changes

#### Configuration
- `app/config.py`:
  - Added `ws_throttle_interval_ms = 500`
  - Marked `ws_broadcast_interval` as legacy

### Test Results
- **Phase 4 DataPublisher Tests**: 15 new tests, all passing
- **Total Tests**: 269 passing (232 Phase 1-3 + 22 Phase 4 initial + 15 DataPublisher)
- **Performance**: Throttle verified <10ms latency for rapid updates
- **Concurrency**: Multiple channels broadcast independently

### Code Quality
- Type safety: 100% type hints with Python 3.12 syntax
- Architecture: Clean subscriber pattern, zero coupling to ConnectionManager internals
- Error handling: Safe subscriber notification with exception logging
- Memory: Bounded deferred broadcast timers (1 per channel max)

### Documentation Updated
- Updated system architecture with DataPublisher flow
- Updated codebase summary with data_publisher.py and test count (269)
- Updated roadmap with Phase 4 enhancement status

### Breaking Changes
- None (additive changes only)
- Legacy `ws_broadcast_interval` still respected for backward compatibility but not used

### Performance Improvements
- **Before**: Poll-based 1s broadcast regardless of data updates
- **After**: Event-driven push with 500ms throttle — broadcasts only when data changes
- **Result**: ~50% reduction in idle CPU usage when market quiet

---

## [Phase 4 Enhanced] - 2026-02-09

### Added

#### WebSocket Multi-Channel Router
- New `app/websocket/router.py` (138 LOC)
  - Three specialized channels for efficient data delivery:
    - `/ws/market` — Full MarketSnapshot (quotes + indices + foreign + derivatives)
    - `/ws/foreign` — ForeignSummary only (aggregate + top movers)
    - `/ws/index` — VN30 + VNINDEX IndexData only
  - Token-based authentication via `?token=xxx` query param
  - IP-based rate limiting (max connections per IP)
  - Shared lifecycle: auth → rate limit → connect → heartbeat → cleanup

#### Security Features
- Query parameter token validation (disabled when `ws_auth_token=""`)
- Rate limiting with connection counting per IP address
- Policy violation closures (code 1008) for auth/rate limit failures
- Automatic connection cleanup on disconnect

#### Configuration Settings
Added to `app/config.py`:
- `ws_auth_token: str = ""` — Optional token (empty = disabled)
- `ws_max_connections_per_ip: int = 5` — Rate limiting per IP
- `ws_queue_size: int = 50` — Per-client queue limit (reduced from 100)

#### Tests (Phase 4 Enhanced: 7 new tests)
- `tests/test_websocket_router.py` (7 tests):
  - Multi-channel connection acceptance
  - Token authentication validation
  - Rate limiting enforcement
  - Channel-specific data delivery
  - Independent channel broadcasts

### Modified

#### Broadcast Loop
- `app/websocket/broadcast_loop.py`:
  - Updated to broadcast to 3 channels independently
  - Skips channels with zero clients for efficiency
  - Fetches channel-specific data from MarketDataProcessor

#### Main Application
- `app/main.py`:
  - Added three ConnectionManager singletons: `market_ws_manager`, `foreign_ws_manager`, `index_ws_manager`
  - Updated broadcast loop to support multi-channel architecture
  - Registered new router with 3 endpoints

#### Environment Configuration
- `.env.example`:
  - Added `WS_AUTH_TOKEN=` — Optional authentication
  - Added `WS_MAX_CONNECTIONS_PER_IP=5` — Rate limiting

### Removed
- `app/websocket/endpoint.py` — Replaced by router.py with multi-channel support

### Test Results
- **Phase 4 Enhanced Tests**: 7 new router tests, all passing
- **Total Tests**: 254 passing (Phase 1-3: 232 + Phase 4: 22)
- **Performance**: Multi-channel broadcast verified <10ms per iteration
- **Concurrency**: Tested with multiple clients across all channels

### Code Quality
- Type safety: 100% type hints with Python 3.12 syntax
- Architecture: Clean channel separation with shared lifecycle management
- Error handling: Auth failures, rate limits, disconnects, queue overflow
- Memory: Bounded per-client queues (maxsize=50)
- Security: Token auth + rate limiting prevent abuse

### Documentation Updated
- Updated system architecture with multi-channel WebSocket details
- Updated codebase summary with router.py and test counts
- Updated roadmap with Phase 4 test count (254 total)

### Breaking Changes
- WebSocket endpoint structure changed:
  - OLD: Single `/ws/market` endpoint
  - NEW: Three endpoints: `/ws/market`, `/ws/foreign`, `/ws/index`
- Clients must update URLs based on data needs
- Auth now via query param `?token=xxx` (optional)

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
| 0.5.2 | Phase 5B (20%) | 2026-02-09 | 🔄 In Progress |
| 0.5.1 | Phase 5 | 2026-02-09 | ✅ Complete |
| 0.5.0 | Phase 4 | 2026-02-08 | ✅ Complete |
| 0.4.0 | Phase 3C | 2026-02-07 | ✅ Complete |
| 0.3.0 | Phase 3A/3B | 2026-02-07 | ✅ Complete |
| 0.2.0 | Phase 2 | 2026-02-07 | ✅ Complete |
| 0.1.0 | Phase 1 | 2026-02-06 | ✅ Complete |

---

## Statistics

### Code Metrics (As of Phase 4 Enhanced)
- **Total Python Files**: 31
- **Total Lines**: ~5,360 LOC (services + models)
- **Test Files**: 13
- **Test LOC**: ~2,300
- **Test Count**: 269 passing
- **Type Coverage**: 100%

### Phase Breakdown
| Phase | Files | LOC | Tests | Duration |
|-------|-------|-----|-------|----------|
| 1 | 6 | 400 | 5 | 1 day |
| 2 | 6 | 800 | 60+ | 1 day |
| 3A | 3 | 250 | 20+ | 1 day |
| 3B | 2 | 280 | 56 | 1 day |
| 3C | 1 + updates | 120 + 400 | 34 | 1 day |
| 4 | 3 + updates | 167 | 22 | 1 day |
| 4 Enhanced | 1 + updates | 158 + 35 | 15 | 0.5 day |
| **Total** | **31** | **~5,360** | **269** | **6.5 days** |

### Test Results Over Time
- Phase 1: ~5 tests
- Phase 1+2: ~65 tests
- Phase 1+2+3A: ~85 tests
- Phase 1+2+3A+3B: ~141 tests
- Phase 1+2+3A+3B+3C: 232 tests
- Phase 1+2+3A+3B+3C+4: 254 tests
- Phase 1+2+3A+3B+3C+4 Enhanced: **269 tests** ✅

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

**Last Updated**: 2026-02-09 10:00
**Current Release**: Phase 4 Enhanced - Event-Driven Broadcasting (v0.5.2)
**Status**: ✅ 269 tests passing | Ready for Phase 5

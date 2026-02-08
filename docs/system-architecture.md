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
    ┌─────────┐      ┌──────────────┐    ┌───────────┐
    │ Market  │      │ Market Data  │    │ Database  │
    │ Data    │      │ Processor    │    │ Layer     │
    │ Services│      │              │    │ (asyncpg) │
    └─────────┘      └──────────────┘    └───────────┘
        │                   │
        │                   ├── QuoteCache
        │                   ├── TradeClassifier
        │                   ├── SessionAggregator
        │                   ├── ForeignInvestorTracker
        │                   ├── IndexTracker
        │                   └── DerivativesTracker
        │
        ▼
    ┌──────────────┐
    │ REST API     │
    │ (market.py)  │
    └──────────────┘
            │
    ┌──────────────┐
    │ WebSocket    │
    │ Broadcast    │
    │ /ws/market   │
    └──────────────┘
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
  - Mark ATO/ATC as NEUTRAL (batch auctions)
- **Input**: X-TRADE:ALL messages
- **Output**: ClassifiedTrade with trade_type, volume, value
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
- **Purpose**: Accumulate active buy/sell totals per symbol per session
- **Data**: Mua/ban volumes, values, neutral volume
- **Input**: ClassifiedTrade from TradeClassifier
- **Output**: SessionStats with aggregate totals
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

SessionStats
├── symbol
├── mua_chu_dong_volume, mua_chu_dong_value
├── ban_chu_dong_volume, ban_chu_dong_value
├── neutral_volume, total_volume
└── last_updated

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
├── indices: dict[index_id → IndexData]
├── foreign: ForeignSummary
└── derivatives: DerivativesData
```

## Message Flow

### Trade Processing Flow

```
SSI X-TRADE Message
    ↓
MarketDataProcessor.handle_trade()
    ↓
Is VN30F*?
    ├─ YES → DerivativesTracker.update_futures_trade()
    └─ NO → TradeClassifier.classify()
            Compare last_price vs cached bid/ask
            ↓
            SessionAggregator.add_trade()
            Accumulate mua/ban/neutral totals
            ↓
            Emit ClassifiedTrade + SessionStats
```

### Quote Processing Flow

```
SSI X-Quote Message
    ↓
MarketDataProcessor.handle_quote()
    ↓
QuoteCache.update(symbol)
Store bid_price_1, ask_price_1, ceiling, floor, ref_price
    ↓
Ready for next TradeClassifier lookup
```

### Foreign Processing Flow

```
SSI R:ALL Message (cumulative FBuyVol, FSellVol)
    ↓
MarketDataProcessor.handle_foreign()
    ↓
ForeignInvestorTracker.update(msg)
    Compute delta from previous cumulative
    ↓
    Add to rolling 10-min history
    ↓
    Calculate speed (vol/min over 5-min window)
    Calculate acceleration (speed change)
    ↓
    Emit ForeignInvestorData
```

### Index Processing Flow

```
SSI MI:VN30 or MI:VNINDEX Message
    ↓
MarketDataProcessor.handle_index()
    ↓
IndexTracker.update(msg)
    Store index value, change, advances, declines
    ↓
    Compute advance_ratio
    ↓
    Append to intraday sparkline (maxlen=1440)
    ↓
    Emit IndexData
```

### Basis Computation Flow

```
SSI X-TRADE for VN30F* + IndexTracker has VN30 value
    ↓
DerivativesTracker._compute_basis()
    basis = futures_price - IndexTracker.get_vn30_value()
    basis_pct = basis / spot_value * 100
    is_premium = basis > 0
    ↓
    Append to basis history (maxlen=3600)
    ↓
    Emit BasisPoint
```

## Daily Reset Cycle

All services implement `reset()` method called daily at 15:00 VN:

```
15:00 VN → daily_reset_loop()
    ├─ SessionAggregator.reset() → clear all session stats
    ├─ ForeignInvestorTracker.reset() → clear accumulated data, history
    ├─ IndexTracker.reset() → keep values, clear intraday points
    └─ DerivativesTracker.reset() → keep basis history for analysis

Next market day:
    New SessionStats, ForeignInvestorData, IndexData intraday
```

## Performance Characteristics

| Operation | Latency | Scale |
|-----------|---------|-------|
| Quote update | <0.5ms | 500+ symbols |
| Trade classification | <1ms | 3000+ TPS |
| Foreign delta calc | <0.5ms | 500+ symbols |
| Index update | <0.1ms | 2 indices |
| Basis calculation | <0.5ms | 5-10 futures contracts |
| Aggregation (all ops) | <5ms | Full market |

## Memory Management

| Component | Memory | Cap | Bounded By |
|-----------|--------|-----|-----------|
| QuoteCache | ~500 symbols × 100B | 50KB | quote count |
| SessionStats | ~500 symbols × 200B | 100KB | symbol count |
| ForeignTracker history | 600 deltas × 50B | 30KB | time window (10 min) |
| IndexTracker intraday | 1440 points × 80B | 115KB | day (1-min points) |
| DerivativesTracker basis | 3600 points × 100B | 360KB | time window (~1h) |
| **Total** | **~655KB** | **~655KB** | **All capped** |

## State Persistence

### In-Memory (Volatile)
- QuoteCache, SessionAggregator, ForeignInvestorTracker, IndexTracker, DerivativesTracker
- Reset daily at 15:00 VN

### Database (Phase 7)
- Trade history (for analytics)
- Foreign investor snapshots
- Index historical values
- Basis history for backtesting

## Error Handling

- **WebSocket disconnect**: Auto-reconnect with exponential backoff
- **Missing Quote**: Trade classified as NEUTRAL until Quote arrives
- **Zero price**: Basis calculation returns None (skipped)
- **Sparse updates**: Speed calculation adapts to actual interval via timestamps
- **Division by zero**: Guarded in basis_pct computation

## Configuration

Environment variables:

```
# Market Data
CHANNEL_R_INTERVAL_MS=1000        # Foreign investor update frequency
FUTURES_OVERRIDE=VN30F2603        # Override active futures contracts

# Quotas
QUOTE_CACHE_CLEANUP_INTERVAL=3600 # seconds
FOREIGN_HISTORY_WINDOW_MINUTES=10
INDEX_INTRADAY_MAXLEN=1440
BASIS_HISTORY_MAXLEN=3600
```

## Testing Strategy

- **Unit tests**: Each service isolated (247 tests)
  - Phase 4: 11 ConnectionManager + 4 endpoint tests
- **Integration tests**: Multi-channel message flow with 100+ ticks
- **Performance tests**: Verify <5ms aggregation latency
- **Edge cases**: Missing quotes, zero prices, sparse updates, client disconnects

### 4. WebSocket Broadcast (Phase 4 - COMPLETE)

**ConnectionManager** (`connection_manager.py`)
- Per-client asyncio queues for message distribution
- Connection lifecycle management (connect/disconnect)
- Broadcast to all connected clients
- Queue overflow protection (maxsize=100)

**WebSocket Endpoint** (`endpoint.py`)
- Route: `GET /ws/market`
- Accepts WebSocket connections
- Implements application-level heartbeat (30s ping, 10s timeout)
- Handles client disconnect and cleanup

**Broadcast Loop** (`broadcast_loop.py`)
- Background task running in lifespan context
- Fetches `MarketSnapshot` from `MarketDataProcessor`
- Broadcasts JSON to all clients every 1s
- Configurable via `WS_BROADCAST_INTERVAL`

**Configuration** (`config.py`):
```python
ws_broadcast_interval: float = 1.0
ws_heartbeat_interval: float = 30.0
ws_heartbeat_timeout: float = 10.0
ws_max_queue_size: int = 100
```

**Integration** (`main.py`):
- `ws_manager` singleton initialized at app startup
- Broadcast loop starts in lifespan context
- WebSocket router registered to FastAPI app

## Next Phases

- **Phase 5**: React dashboard with real-time chart updates
- **Phase 6**: Analytics engine (alerts, correlation, signals)
- **Phase 7**: Database layer for historical persistence
- **Phase 8**: Deployment and load testing

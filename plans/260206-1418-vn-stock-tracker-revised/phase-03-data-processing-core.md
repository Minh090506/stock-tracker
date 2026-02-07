# Phase 03: Data Processing Core

## Context Links
- [Plan Overview](./plan.md)
- [SSI WS Data Format](../reports/researcher-260206-1423-ssi-fastconnect-websocket-data-format.md)
- [Phase 02: SSI Integration](./phase-02-ssi-integration-stream-demux.md)
- [Old plan Phase 03 (FLAWED)](../260206-1341-stock-tracker-system/phase-03-backend-data-processing.md)

## Overview
- **Priority:** P0
- **Status:** complete (3A+3B+3C all implemented and tested)
- **Effort:** 8h (6h spent on 3A+3B+3C completed, 2h for daily reset deferred)
- **MOST CRITICAL PHASE** - Build QuoteCache, TradeClassifier (CORRECTED), ForeignInvestorTracker (REWRITTEN), IndexTracker, DerivativesTracker, SessionAggregator.

## Phase 3B Completion (2026-02-07)
- ✓ ForeignInvestorTracker: delta, speed, acceleration, reconnect handling, top movers, VN30 aggregate
- ✓ IndexTracker: breadth ratio, intraday sparkline, multi-index support
- ✓ Tests: 56 new tests (29 foreign + 27 index), all passing
- ✓ Integration: wired into MarketDataProcessor and main.py callbacks
- 📊 Code review: APPROVED (see reports/code-reviewer-260207-1149-phase-3b-implementation-review.md)

## Phase 3C Completion (2026-02-07)
- ✓ DerivativesTracker: basis calculation (futures - VN30 spot), premium/discount detection, basis_pct
- ✓ Multi-contract support: volume-based active contract selection for VN30F rollover
- ✓ Unified API: MarketSnapshot model aggregates quotes + indices + foreign + derivatives
- ✓ Tests: 34 new tests (17 derivatives + 14 processor updates + 3 integration), all passing
- ✓ Integration: 100+ tick simulation validates end-to-end data flow across all channels
- 📊 Code review: APPROVED (see reports/code-reviewer-260207-1504-phase-3c-derivatives-tracker-review.md)

## Critical Corrections from Old Plan

| Component | Old Plan (WRONG) | New Plan (CORRECT) |
|-----------|-----------------|-------------------|
| TradeClassifier volume | `quote.total_volume` (cumulative) | `trade.last_vol` (per-trade) |
| TradeClassifier bid/ask | From same quote snapshot | From cached Quote messages via QuoteCache |
| ForeignInvestorService | vnstock polling 30s | SSI Channel R native (delta computation) |
| QuoteCache | Did not exist | NEW: caches latest bid/ask per symbol |
| IndexTracker | Did not exist | NEW: VN30/VNINDEX from Channel MI |
| DerivativesTracker | Did not exist | NEW: VN30F price + basis calculation |

## Requirements

### Functional
- Cache latest bid/ask per symbol from Quote messages
- Classify each trade as mua_chu_dong / ban_chu_dong / neutral using LastVol + cached bid/ask
- Accumulate per-symbol session totals (volume + value per type)
- Track foreign investor deltas from cumulative Channel R data
- Compute foreign buying/selling speed (volume per minute, rolling 5 min)
- Track VN30/VNINDEX index values in real-time
- Compute basis = VN30F_price - VN30_index_value
- Daily auto-reset at 15:00 VN time

### Non-Functional
- Classification latency <5ms per trade
- Memory: support 500+ symbols (~few MB)
- All operations async-safe
- MVP: process HOSE/VN30 stocks only. Schema `exchange` field preserved for future expansion.

## Architecture
```
SSI Quote Message (RType="Quote")
    │
    ▼
QuoteCache.update(symbol, bid_price_1, ask_price_1, ceiling, floor, ref_price)
    │  Stores latest quote per symbol
    │
SSI Trade Message (RType="Trade")
    │
    ▼
TradeClassifier.classify(trade_msg)
    │  Uses trade.last_vol (PER-TRADE) + QuoteCache.get_bid_ask(symbol)
    │  Returns: ClassifiedTrade with trade_type + volume
    ▼
SessionAggregator.add_trade(classified_trade)
    │  Accumulates mua/ban/neutral totals
    ▼
Ready for broadcast (Phase 04)

SSI Foreign Message (RType="R")
    │
    ▼
ForeignInvestorTracker.update(msg)
    │  Computes delta from previous cumulative
    │  Tracks speed (vol/min over rolling window)
    ▼
Ready for broadcast (Phase 04)

SSI Index Message (RType="MI")
    │
    ▼
IndexTracker.update(msg)
    │  Stores latest VN30/VNINDEX values
    ▼
DerivativesTracker needs VN30 value for basis

SSI Trade Message where symbol.startswith("VN30F")
    │
    ▼
DerivativesTracker.update_futures_trade(trade_msg)
    │  basis = futures_price - IndexTracker.get_vn30_value()
    ▼
Ready for broadcast (Phase 04)
```

## Related Code Files
- `~/projects/stock-tracker/backend/app/services/quote_cache.py` - **NEW**: Cache bid/ask per symbol
- `~/projects/stock-tracker/backend/app/services/trade_classifier.py` - **REWRITTEN**: LastVol + cached bid/ask
- `~/projects/stock-tracker/backend/app/services/session_aggregator.py` - **REWRITTEN**: Central accumulator
- `~/projects/stock-tracker/backend/app/services/foreign_investor_tracker.py` - **REWRITTEN**: Channel R deltas
- `~/projects/stock-tracker/backend/app/services/index_tracker.py` - **NEW**: VN30/VNINDEX
- `~/projects/stock-tracker/backend/app/services/derivatives_tracker.py` - **NEW**: Basis calculation
- `~/projects/stock-tracker/backend/app/services/market_data_processor.py` - Orchestrates all processing

## Implementation Steps

### 1. Create QuoteCache (`services/quote_cache.py`)
```python
"""Cache latest bid/ask from SSI Quote messages for trade classification."""

class QuoteCache:
    def __init__(self):
        self._cache: dict[str, SSIQuoteMessage] = {}

    def update(self, quote: SSIQuoteMessage):
        self._cache[quote.symbol] = quote

    def get_bid_ask(self, symbol: str) -> tuple[float, float]:
        """Returns (bid_price_1, ask_price_1). (0, 0) if not yet cached."""
        q = self._cache.get(symbol)
        return (q.bid_price_1, q.ask_price_1) if q else (0.0, 0.0)

    def get_quote(self, symbol: str) -> SSIQuoteMessage | None:
        return self._cache.get(symbol)

    def get_price_refs(self, symbol: str) -> tuple[float, float, float]:
        """Returns (ref_price, ceiling, floor). For color coding."""
        q = self._cache.get(symbol)
        return (q.ref_price, q.ceiling, q.floor) if q else (0.0, 0.0, 0.0)
```

### 2. Create TradeClassifier (`services/trade_classifier.py`) - CORRECTED
```python
"""Classify trades using LastVol (per-trade) against cached bid/ask.

CRITICAL: Old plan used TotalVol (cumulative) - WRONG.
SSI LastVol = volume of most recent trade = per-trade volume.
"""

class TradeClassifier:
    def __init__(self, quote_cache: QuoteCache):
        self._cache = quote_cache

    def classify(self, trade: SSITradeMessage) -> ClassifiedTrade:
        bid, ask = self._cache.get_bid_ask(trade.symbol)
        volume = trade.last_vol  # PER-TRADE volume, NOT cumulative

        # Skip classification during auction sessions
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

### 3. Create SessionAggregator (`services/session_aggregator.py`)
```python
"""Accumulate active buy/sell totals per symbol. Resets daily at 15:00."""

class SessionAggregator:
    def __init__(self):
        self._stats: dict[str, SessionStats] = {}

    def add_trade(self, trade: ClassifiedTrade) -> SessionStats:
        if trade.symbol not in self._stats:
            self._stats[trade.symbol] = SessionStats(symbol=trade.symbol)
        stats = self._stats[trade.symbol]

        if trade.trade_type == TradeType.MUA_CHU_DONG:
            stats.mua_chu_dong_volume += trade.volume
            stats.mua_chu_dong_value += trade.value
        elif trade.trade_type == TradeType.BAN_CHU_DONG:
            stats.ban_chu_dong_volume += trade.volume
            stats.ban_chu_dong_value += trade.value
        else:
            stats.neutral_volume += trade.volume

        stats.total_volume += trade.volume
        stats.last_updated = trade.timestamp
        return stats

    def get_stats(self, symbol: str) -> SessionStats:
        return self._stats.get(symbol, SessionStats(symbol=symbol))

    def get_all_stats(self) -> dict[str, SessionStats]:
        return dict(self._stats)

    def reset(self):
        self._stats.clear()
```

### 4. Create ForeignInvestorTracker (`services/foreign_investor_tracker.py`) - REWRITTEN
```python
"""Track foreign investor activity via SSI Channel R cumulative deltas.

REWRITTEN: Old plan used vnstock polling (30s delay, fragile).
New: SSI Channel R sends FBuyVol/FSellVol cumulative from market open.
We compute deltas between consecutive updates and track speed.
"""
from collections import deque
from datetime import datetime, timedelta

class ForeignDelta(BaseModel):
    buy_delta: int
    sell_delta: int
    timestamp: datetime

class ForeignInvestorTracker:
    def __init__(self):
        self._prev: dict[str, SSIForeignMessage] = {}
        self._session: dict[str, ForeignInvestorData] = {}
        # Rolling window for speed calc. Interval configurable via CHANNEL_R_INTERVAL_MS env.
        self._history: dict[str, deque[ForeignDelta]] = {}  # rolling window

    def update(self, msg: SSIForeignMessage) -> ForeignInvestorData:
        symbol = msg.symbol
        prev = self._prev.get(symbol)
        now = datetime.now()

        # Compute delta
        if prev:
            delta_buy = max(0, msg.f_buy_vol - prev.f_buy_vol)
            delta_sell = max(0, msg.f_sell_vol - prev.f_sell_vol)
        else:
            delta_buy = msg.f_buy_vol
            delta_sell = msg.f_sell_vol

        self._prev[symbol] = msg

        # Store delta for speed calculation (keep last 10 min)
        if symbol not in self._history:
            self._history[symbol] = deque(maxlen=600)  # ~10 min at 1 msg/sec
        self._history[symbol].append(ForeignDelta(
            buy_delta=delta_buy, sell_delta=delta_sell, timestamp=now,
        ))

        # Compute speed (vol per minute over last 5 min)
        speed = self._compute_speed(symbol, window_minutes=5)

        # Update session data
        data = ForeignInvestorData(
            symbol=symbol,
            buy_volume=msg.f_buy_vol,
            sell_volume=msg.f_sell_vol,
            net_volume=msg.f_buy_vol - msg.f_sell_vol,
            buy_value=msg.f_buy_val,
            sell_value=msg.f_sell_val,
            net_value=msg.f_buy_val - msg.f_sell_val,
            total_room=msg.total_room,
            current_room=msg.current_room,
            buy_speed_per_min=speed[0],
            sell_speed_per_min=speed[1],
            last_updated=now,
        )
        self._session[symbol] = data
        return data

    def _compute_speed(self, symbol: str, window_minutes: int = 5) -> tuple[float, float]:
        """Returns (buy_per_min, sell_per_min) over rolling window."""
        history = self._history.get(symbol, deque())
        cutoff = datetime.now() - timedelta(minutes=window_minutes)
        recent = [d for d in history if d.timestamp >= cutoff]
        if not recent or window_minutes == 0:
            return (0.0, 0.0)
        total_buy = sum(d.buy_delta for d in recent)
        total_sell = sum(d.sell_delta for d in recent)
        return (total_buy / window_minutes, total_sell / window_minutes)

    def get(self, symbol: str) -> ForeignInvestorData:
        return self._session.get(symbol, ForeignInvestorData(symbol=symbol))

    def get_all(self) -> dict[str, ForeignInvestorData]:
        return dict(self._session)

    def reset(self):
        self._prev.clear()
        self._session.clear()
        self._history.clear()
```

### 5. Create IndexTracker (`services/index_tracker.py`) - NEW
```python
"""Track VN30 and VNINDEX real-time values from Channel MI."""

class IndexTracker:
    def __init__(self):
        self._indices: dict[str, IndexData] = {}

    def update(self, msg: SSIIndexMessage) -> IndexData:
        data = IndexData(
            index_id=msg.index_id,
            value=msg.index_value,
            prior_value=msg.prior_index_value,
            change=msg.change,
            ratio_change=msg.ratio_change,
            total_volume=msg.total_qtty,
            advances=msg.advances,
            declines=msg.declines,
            last_updated=datetime.now(),
        )
        self._indices[msg.index_id] = data
        return data

    def get(self, index_id: str) -> IndexData | None:
        return self._indices.get(index_id)

    def get_vn30_value(self) -> float:
        idx = self._indices.get("VN30")
        return idx.value if idx else 0.0

    def get_all(self) -> dict[str, IndexData]:
        return dict(self._indices)
```

### 6. Create DerivativesTracker (`services/derivatives_tracker.py`) - NEW
```python
"""Track VN30F futures price and compute basis against VN30 spot index."""
from collections import deque

class DerivativesTracker:
    def __init__(self, index_tracker: IndexTracker):
        self._index = index_tracker
        self._futures_prices: dict[str, float] = {}  # symbol -> last_price
        self._basis_history: deque[BasisPoint] = deque(maxlen=3600)  # ~1h at 1/sec
        self._current_basis: BasisPoint | None = None

    def update_futures_trade(self, trade: SSITradeMessage) -> BasisPoint | None:
        """Call when trade.symbol starts with 'VN30F'."""
        self._futures_prices[trade.symbol] = trade.last_price
        return self._compute_basis(trade.symbol)

    def _compute_basis(self, futures_symbol: str) -> BasisPoint | None:
        futures_price = self._futures_prices.get(futures_symbol, 0)
        spot_value = self._index.get_vn30_value()
        if futures_price <= 0 or spot_value <= 0:
            return None

        bp = BasisPoint(
            timestamp=datetime.now(),
            futures_symbol=futures_symbol,
            futures_price=futures_price,
            spot_value=spot_value,
            basis=futures_price - spot_value,
            is_premium=futures_price > spot_value,
        )
        self._basis_history.append(bp)
        self._current_basis = bp
        return bp

    def get_current(self) -> BasisPoint | None:
        return self._current_basis

    def get_basis_trend(self, minutes: int = 30) -> list[BasisPoint]:
        cutoff = datetime.now() - timedelta(minutes=minutes)
        return [b for b in self._basis_history if b.timestamp >= cutoff]

    def get_futures_price(self, symbol: str) -> float:
        return self._futures_prices.get(symbol, 0.0)
```

### 7. Create MarketDataProcessor (`services/market_data_processor.py`)
```python
"""Orchestrates all data processing. Wired to SSI stream callbacks."""

class MarketDataProcessor:
    def __init__(self):
        self.quote_cache = QuoteCache()
        self.classifier = TradeClassifier(self.quote_cache)
        self.aggregator = SessionAggregator()
        self.foreign_tracker = ForeignInvestorTracker()
        self.index_tracker = IndexTracker()
        self.derivatives_tracker = DerivativesTracker(self.index_tracker)

    async def handle_quote(self, msg: SSIQuoteMessage):
        self.quote_cache.update(msg)

    async def handle_trade(self, msg: SSITradeMessage):
        # Derivatives trade
        if msg.symbol.startswith("VN30F"):
            self.derivatives_tracker.update_futures_trade(msg)
            return None, None  # Don't classify derivatives as mua/ban
        # Stock trade
        classified = self.classifier.classify(msg)
        stats = self.aggregator.add_trade(classified)
        return classified, stats

    async def handle_foreign(self, msg: SSIForeignMessage):
        return self.foreign_tracker.update(msg)

    async def handle_index(self, msg: SSIIndexMessage):
        return self.index_tracker.update(msg)
```

### 8. Wire processor into stream service (main.py)
```python
processor = MarketDataProcessor()
stream_service.on_quote(processor.handle_quote)
stream_service.on_trade(processor.handle_trade)
stream_service.on_foreign(processor.handle_foreign)
stream_service.on_index(processor.handle_index)
```

### 9. Add daily reset task
```python
async def daily_reset_loop():
    while True:
        now = datetime.now()
        target = now.replace(hour=15, minute=0, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        await asyncio.sleep((target - now).total_seconds())
        processor.aggregator.reset()
        processor.foreign_tracker.reset()
```

## Todo List
- [x] Create QuoteCache (bid/ask cache from Quote messages) — Phase 3A COMPLETE
- [x] Create TradeClassifier (CORRECTED: LastVol + cached bid/ask) — Phase 3A COMPLETE
- [x] Create SessionAggregator (mua/ban totals per symbol) — Phase 3A COMPLETE
- [x] Create ForeignInvestorTracker (REWRITTEN: Channel R deltas + speed + accel) — Phase 3B COMPLETE
- [x] Create IndexTracker (VN30/VNINDEX from Channel MI + breadth + sparkline) — Phase 3B COMPLETE
- [x] Create DerivativesTracker (basis = futures - spot) — Phase 3C COMPLETE
- [x] Create MarketDataProcessor orchestrator — Phase 3A+3B+3C COMPLETE
- [x] Wire processor callbacks into SSI stream — Phase 3B COMPLETE
- [x] Add unified API (get_market_snapshot, get_derivatives_data) — Phase 3C COMPLETE
- [ ] Add daily reset at 15:00 VN — DEFERRED to future phase (reset methods implemented)
- [x] Unit test: classify with known bid=10, ask=11, price=11 → MUA — Phase 3A COMPLETE
- [x] Unit test: classify with price=10 → BAN — Phase 3A COMPLETE
- [x] Unit test: foreign delta computation — Phase 3B COMPLETE (29 tests)
- [x] Unit test: index breadth, sparkline — Phase 3B COMPLETE (27 tests)
- [x] Unit test: basis calculation — Phase 3C COMPLETE (17 tests)
- [x] Integration test: 100+ ticks multi-channel — Phase 3C COMPLETE (3 tests)
- [x] Test ATO/ATC trades classified as NEUTRAL — Phase 3A COMPLETE
- [x] All 232 tests passing — COMPLETE (56 Phase 3A/3B + 34 Phase 3C + others)

## Success Criteria
- Trade classifier uses `last_vol` (per-trade), NOT `total_vol` (cumulative)
- Classifier uses cached bid/ask from separate Quote messages
- ATO/ATC trades → NEUTRAL (batch auctions, not individual trades)
- Foreign tracker computes delta from cumulative R channel data
- Foreign speed calculated over rolling 5-min window
- Index values updated from Channel MI
- Basis = VN30F price - VN30 index value
- All processing <5ms per trade

## Risk Assessment
- **No Quote before first Trade:** If Trade arrives before any Quote for a symbol, bid/ask cache is empty → classify as NEUTRAL. This is acceptable (data fills in within seconds of market open).
- **LastVol during ATO/ATC:** Batch auction LastVol may be the entire auction volume, not a single trade. Classifying as NEUTRAL during these sessions avoids misattribution.
- **Channel R update frequency:** Configurable via `CHANNEL_R_INTERVAL_MS` env (default 1000ms). Speed calculation uses actual observed timestamps between deltas, not assumed interval.
- **Basis accuracy:** Depends on VN30 index updating frequently. If MI updates lag, basis calculation will be slightly stale.

## Next Steps
- Phase 04: WebSocket server to broadcast processed data to React clients

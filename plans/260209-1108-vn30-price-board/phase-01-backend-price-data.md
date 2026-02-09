# Phase 1: Backend — Price Data Model + Tracking + Snapshot Enrichment

## Context Links
- [domain.py](/backend/app/models/domain.py) — current domain models (SessionStats, MarketSnapshot)
- [market_data_processor.py](/backend/app/services/market_data_processor.py) — central orchestrator
- [quote_cache.py](/backend/app/services/quote_cache.py) — bid/ask + ref/ceil/floor cache
- [ssi_messages.py](/backend/app/models/ssi_messages.py) — SSITradeMessage (has last_price, change, ratio_change)
- [schemas.py](/backend/app/models/schemas.py) — re-exports for convenience

## Overview
- **Priority**: P1 (blocks frontend phase)
- **Status**: ✅ complete
- **Description**: Add `PriceData` model to domain, cache last trade prices per symbol in `MarketDataProcessor`, merge with `QuoteCache` ref/ceiling/floor at snapshot time, expose in `MarketSnapshot.prices`.

## Key Insights
- `SSITradeMessage` already has `last_price`, `change`, `ratio_change` per trade — just not cached anywhere
- `QuoteCache` already has `ref_price`, `ceiling`, `floor` per symbol via `get_price_refs()`
- Only need a simple `dict[str, _PriceEntry]` in processor to cache latest trade prices
- `MarketSnapshot` already serializes via `model_dump_json()` in `DataPublisher._get_channel_data()` — adding `prices` field automatically flows to WS clients

## Requirements
### Functional
- `PriceData` model: `last_price`, `change`, `change_pct`, `ref_price`, `ceiling`, `floor`
- `MarketSnapshot.prices` field: `dict[str, PriceData]`
- Price cache updated on every non-futures trade in `handle_trade()`
- Snapshot merges trade cache + QuoteCache at read time
- Cache resets with `reset_session()`

### Non-Functional
- Zero allocation overhead when no clients are connected (cache is just a dict update)
- No new dependencies

## Architecture

```
SSITradeMessage (handle_trade)
  │
  ├─ last_price, change, ratio_change
  │   └──→ self._price_cache[symbol] = (last_price, change, ratio_change)
  │
  └─ existing: classify → aggregate

get_market_snapshot()
  │
  ├─ for each symbol in _price_cache:
  │     merge with QuoteCache.get_price_refs(symbol) → (ref, ceiling, floor)
  │     → PriceData(last_price, change, change_pct, ref_price, ceiling, floor)
  │
  └─ MarketSnapshot(quotes=..., prices=prices_dict, indices=..., ...)
```

## Related Code Files

### Modified Files
1. `backend/app/models/domain.py` — add `PriceData`, update `MarketSnapshot`
2. `backend/app/services/market_data_processor.py` — add price cache + build prices in snapshot
3. `backend/app/models/schemas.py` — re-export `PriceData`

## Implementation Steps

### Step 1: Add `PriceData` model to `domain.py`

Add after `SessionStats` class (line ~42):

```python
class PriceData(BaseModel):
    """Last trade price + reference levels for a single stock."""

    last_price: float = 0.0
    change: float = 0.0       # last_price - ref_price (from SSI)
    change_pct: float = 0.0   # ratio_change (from SSI, already %)
    ref_price: float = 0.0    # reference/opening price
    ceiling: float = 0.0      # price ceiling (tran)
    floor: float = 0.0        # price floor (san)
```

### Step 2: Add `prices` field to `MarketSnapshot`

Update `MarketSnapshot` class (line ~134):

```python
class MarketSnapshot(BaseModel):
    """Unified snapshot of all market data for API consumers."""

    quotes: dict[str, "SessionStats"] = {}
    prices: dict[str, "PriceData"] = {}       # <-- NEW
    indices: dict[str, IndexData] = {}
    foreign: ForeignSummary | None = None
    derivatives: DerivativesData | None = None
```

### Step 3: Add price cache to `MarketDataProcessor.__init__()`

Add a lightweight internal cache (no new class needed, YAGNI):

```python
def __init__(self):
    self.quote_cache = QuoteCache()
    self.classifier = TradeClassifier(self.quote_cache)
    self.aggregator = SessionAggregator()
    self.foreign_tracker = ForeignInvestorTracker()
    self.index_tracker = IndexTracker()
    self.derivatives_tracker = DerivativesTracker(
        self.index_tracker, self.quote_cache
    )
    self._subscribers: list[SubscriberCallback] = []
    # Price cache: symbol -> (last_price, change, ratio_change)
    self._price_cache: dict[str, tuple[float, float, float]] = {}
```

### Step 4: Cache price in `handle_trade()`

After the futures guard but before classification (around line ~63):

```python
async def handle_trade(self, msg: SSITradeMessage):
    """Classify trade and accumulate session stats."""
    if msg.symbol.startswith("VN30F"):
        self.derivatives_tracker.update_from_trade(msg)
        self._notify("market")
        return None, None

    # Cache latest price data from trade
    self._price_cache[msg.symbol] = (
        msg.last_price, msg.change, msg.ratio_change
    )

    classified = self.classifier.classify(msg)
    stats = self.aggregator.add_trade(classified)
    self._notify("market")
    return classified, stats
```

### Step 5: Build `prices` dict in `get_market_snapshot()`

```python
def get_market_snapshot(self) -> MarketSnapshot:
    """All quotes + prices + indices + foreign + derivatives."""
    prices: dict[str, PriceData] = {}
    for symbol, (last_price, change, ratio_change) in self._price_cache.items():
        ref, ceiling, floor = self.quote_cache.get_price_refs(symbol)
        prices[symbol] = PriceData(
            last_price=last_price,
            change=change,
            change_pct=ratio_change,
            ref_price=ref,
            ceiling=ceiling,
            floor=floor,
        )

    return MarketSnapshot(
        quotes=self.aggregator.get_all_stats(),
        prices=prices,
        indices=self.index_tracker.get_all(),
        foreign=self.foreign_tracker.get_summary(),
        derivatives=self.derivatives_tracker.get_data(),
    )
```

### Step 6: Clear price cache in `reset_session()`

```python
def reset_session(self):
    """Reset all session data. Called at 15:00 VN daily."""
    self.aggregator.reset()
    self.foreign_tracker.reset()
    self.index_tracker.reset()
    self.derivatives_tracker.reset()
    self._price_cache.clear()
    logger.info("Session data reset")
```

### Step 7: Re-export `PriceData` in `schemas.py`

Add `PriceData` to the domain imports:

```python
from app.models.domain import (  # noqa: F401
    BasisPoint,
    ClassifiedTrade,
    ForeignInvestorData,
    ForeignSummary,
    IndexData,
    IntradayPoint,
    PriceData,          # <-- NEW
    SessionStats,
    TradeType,
)
```

## Todo List
- [x] Add `PriceData` model to `domain.py`
- [x] Add `prices` field to `MarketSnapshot`
- [x] Add `_price_cache` dict to `MarketDataProcessor.__init__()`
- [x] Cache price in `handle_trade()`
- [x] Build prices dict in `get_market_snapshot()`
- [x] Clear cache in `reset_session()`
- [x] Re-export `PriceData` in `schemas.py`
- [x] Run `./venv/bin/python -m py_compile app/models/domain.py` to verify syntax
- [x] Run `./venv/bin/pytest -v` to verify existing tests pass

## Success Criteria
- `GET /api/market/snapshot` returns `prices` dict with per-symbol `PriceData`
- WS `/ws/market` broadcasts include `prices` field
- All existing tests pass unchanged
- No new dependencies added

## Risk Assessment
- **Low risk**: Adding a new optional field to `MarketSnapshot` is backward-compatible (default `{}`)
- **Trade volume**: `_price_cache` is a simple dict — O(1) per trade, negligible memory for ~30 symbols
- **QuoteCache miss**: If no quote received yet, `get_price_refs()` returns `(0, 0, 0)` — acceptable, will populate after first quote message

## Security Considerations
- No auth changes — prices exposed through existing authenticated WS and REST channels
- No user input — data sourced entirely from SSI stream

## Next Steps
- Phase 2 depends on this: frontend reads `snapshot.prices` for price board

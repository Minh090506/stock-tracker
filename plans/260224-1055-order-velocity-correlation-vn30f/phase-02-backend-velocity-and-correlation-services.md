# Phase 2: Backend Services — VelocityTracker & CorrelationEngine

## Context Links

- [ForeignInvestorTracker](../../backend/app/services/foreign_investor_tracker.py) — pattern template
- [DerivativesTracker](../../backend/app/services/derivatives_tracker.py) — VN30F price source
- [MarketDataProcessor](../../backend/app/services/market_data_processor.py) — integration point
- [Domain models](../../backend/app/models/domain.py) — Pydantic model patterns
- [main.py](../../backend/app/main.py) — service wiring in lifespan

## Overview

- **Priority**: P1
- **Status**: complete
- **Effort**: 5h
- **Description**: Create `VelocityTracker` (per-symbol velocity with speed/acceleration) and `CorrelationEngine` (rolling Pearson correlation between velocity and VN30F price). Integrate both into `MarketDataProcessor`.

## Key Insights

- Follow `ForeignInvestorTracker` pattern exactly: `__slots__` delta class, rolling `deque`, `_compute_speed()`, public `get()`/`get_all()`/`reset()` API
- VelocityTracker receives **every classified trade** (unlike foreign which gets Channel R updates) -- must be lightweight
- Correlation computed every minute (not per-trade) to avoid excessive CPU
- Pure Python Pearson correlation formula avoids numpy dependency
- VN30F price changes available from `DerivativesTracker._prices` dict
- VN30 basket = SUM of all non-VN30F symbols in VelocityTracker (mirrors DB view logic)

## Requirements

### Functional
- Track per-symbol per-minute: buy_vol, sell_vol, buy_count, sell_count, buy_value, sell_value
- Compute derived metrics: net_velocity, imbalance_ratio, acceleration
- Rolling Pearson correlation (configurable window, default 15 min) between net_velocity and VN30F price delta
- Expose VN30F velocity, VN30 basket velocity, and correlation coefficient

### Non-Functional
- < 1ms per `on_trade()` call (called per trade, ~100-500/sec during peak)
- Memory bounded: deque maxlen=60 (60 minutes rolling)
- No external dependencies (no numpy)

## Architecture

```
ClassifiedTrade (from TradeClassifier)
    |
    +---> VelocityTracker.on_trade(classified)
              |
              +---> _accumulate_minute_bucket(symbol, trade)
              +---> _maybe_rotate_minute()  -- on minute boundary
                        |
                        +---> CorrelationEngine.on_minute_tick()
                                  |
                                  +---> _update_correlation()
```

### VelocityTracker Internal State

```python
class _MinuteBucket:
    __slots__ = ("buy_vol", "sell_vol", "buy_count", "sell_count",
                 "buy_value", "sell_value", "timestamp")

class VelocityTracker:
    _current: dict[str, _MinuteBucket]       # accumulating current minute
    _history: dict[str, deque[_MinuteBucket]] # maxlen=60, completed minutes
    _prev_net_velocity: dict[str, float]      # for acceleration calc
```

### New Domain Models

```python
class VelocityData(BaseModel):
    """Per-symbol velocity metrics for current rolling window."""
    symbol: str
    buy_vol_per_min: float = 0.0
    sell_vol_per_min: float = 0.0
    net_vol_per_min: float = 0.0
    buy_count_per_min: float = 0.0
    sell_count_per_min: float = 0.0
    imbalance_ratio: float = 0.5   # buy/(buy+sell), 0.5 = neutral
    acceleration: float = 0.0      # net velocity change rate
    last_updated: datetime | None = None

class VelocitySnapshot(BaseModel):
    """Aggregate velocity for dashboard display."""
    vn30f: VelocityData | None = None
    basket: VelocityData | None = None
    correlation: CorrelationData | None = None

class CorrelationData(BaseModel):
    """Rolling Pearson correlation result."""
    coefficient: float = 0.0       # -1 to +1
    sample_size: int = 0
    window_minutes: int = 15
    last_updated: datetime | None = None
```

### Pearson Correlation (numpy-free)

```python
def _pearson(x: list[float], y: list[float]) -> float:
    """Pure Python Pearson correlation coefficient."""
    n = len(x)
    if n < 3:
        return 0.0
    sum_x = sum(x)
    sum_y = sum(y)
    sum_xy = sum(a * b for a, b in zip(x, y))
    sum_x2 = sum(a * a for a in x)
    sum_y2 = sum(b * b for b in y)
    num = n * sum_xy - sum_x * sum_y
    den = ((n * sum_x2 - sum_x ** 2) * (n * sum_y2 - sum_y ** 2)) ** 0.5
    return num / den if den > 0 else 0.0
```

## Related Code Files

### Files to Create
- `backend/app/services/velocity_tracker.py` (~160 LOC)
- `backend/app/services/correlation_engine.py` (~120 LOC)

### Files to Modify
- `backend/app/models/domain.py` — add VelocityData, VelocitySnapshot, CorrelationData
- `backend/app/services/market_data_processor.py` — integrate VelocityTracker + CorrelationEngine

### Files to Reference (read-only)
- `backend/app/services/foreign_investor_tracker.py` — exact pattern to follow
- `backend/app/services/derivatives_tracker.py` — VN30F price access
- `backend/app/main.py` — lifespan wiring pattern

## Implementation Steps

### Step 1: Add domain models to `backend/app/models/domain.py`

Add `VelocityData`, `VelocitySnapshot`, `CorrelationData` after `DerivativesData`. Update `MarketSnapshot`:

```python
class MarketSnapshot(BaseModel):
    quotes: dict[str, "SessionStats"] = {}
    prices: dict[str, "PriceData"] = {}
    indices: dict[str, IndexData] = {}
    foreign: ForeignSummary | None = None
    derivatives: DerivativesData | None = None
    velocity: VelocitySnapshot | None = None  # NEW
```

### Step 2: Create `backend/app/services/velocity_tracker.py`

Structure:
```python
"""Track order velocity (vol/count/value per minute) per symbol.

Receives classified trades from MarketDataProcessor.
Maintains rolling minute-by-minute history for speed/acceleration.
Provides VN30F and VN30 basket aggregate views.
"""

import logging
from collections import deque
from datetime import datetime

from app.models.domain import VelocityData

logger = logging.getLogger(__name__)

_HISTORY_MAXLEN = 60  # 60 minutes rolling
_SPEED_WINDOW_MIN = 5  # average over last 5 minutes

class _MinuteBucket:
    """Accumulator for one minute of trade data."""
    __slots__ = ("buy_vol", "sell_vol", "buy_count", "sell_count",
                 "buy_value", "sell_value", "timestamp")
    def __init__(self, timestamp: datetime): ...

class VelocityTracker:
    def __init__(self): ...
    def on_trade(self, symbol: str, volume: int, value: float,
                 is_buy: bool, timestamp: datetime) -> None: ...
    def _maybe_rotate(self, symbol: str, now: datetime) -> bool: ...
    def _compute_velocity(self, symbol: str) -> VelocityData: ...
    def get_velocity(self, symbol: str) -> VelocityData: ...
    def get_vn30f_velocity(self) -> VelocityData | None: ...
    def get_basket_velocity(self, exclude_prefix: str = "VN30F") -> VelocityData: ...
    def get_minute_rotated_symbols(self) -> set[str]: ...
    def reset(self) -> None: ...
```

Key design decisions:
- `on_trade()` takes primitives (not ClassifiedTrade) for decoupling
- Minute rotation: check `current_bucket.timestamp.minute != now.minute`
- Basket velocity: iterate `_history`, SUM all non-VN30F symbols' latest buckets
- `get_minute_rotated_symbols()` returns symbols that just completed a minute -- used by CorrelationEngine to know when to recompute

### Step 3: Create `backend/app/services/correlation_engine.py`

Structure:
```python
"""Rolling Pearson correlation between order velocity and VN30F price change.

Computes correlation every minute after velocity rotation.
No numpy dependency — uses pure Python Pearson formula.
"""

import logging
from collections import deque
from datetime import datetime

from app.models.domain import CorrelationData

logger = logging.getLogger(__name__)

_WINDOW_MIN = 15  # rolling window for correlation
_MIN_SAMPLES = 5  # minimum data points for meaningful correlation

class _CorrelationPoint:
    __slots__ = ("net_velocity", "price_delta", "timestamp")
    ...

class CorrelationEngine:
    def __init__(self, window_minutes: int = _WINDOW_MIN): ...
    def on_minute_tick(self, net_velocity: float, vn30f_price: float) -> None: ...
    def get_correlation(self) -> CorrelationData: ...
    def reset(self) -> None: ...
```

Key design decisions:
- Receives pre-computed `net_velocity` (buy_vol - sell_vol per min) and `vn30f_price`
- Stores both in `deque(maxlen=window_minutes)`
- Price delta = `current_price - previous_price` (computed internally)
- Correlation between `net_velocity` series and `price_delta` series
- Returns 0.0 coefficient if < `_MIN_SAMPLES` data points

### Step 4: Integrate into `MarketDataProcessor`

In `__init__()`:
```python
self.velocity_tracker = VelocityTracker()
self.correlation_engine = CorrelationEngine()
```

In `handle_trade()`, after classification:
```python
# Feed velocity tracker for ALL trades (stocks + VN30F)
if classified:
    is_buy = classified.trade_type == TradeType.MUA_CHU_DONG
    self.velocity_tracker.on_trade(
        classified.symbol, classified.volume, classified.value,
        is_buy, classified.timestamp
    )
    # Check if minute rotated — update correlation
    if self.velocity_tracker.get_minute_rotated_symbols():
        vn30f_vel = self.velocity_tracker.get_vn30f_velocity()
        vn30f_price = self.derivatives_tracker.get_futures_price(
            self.derivatives_tracker._active_symbol
        )
        if vn30f_vel and vn30f_price > 0:
            self.correlation_engine.on_minute_tick(
                vn30f_vel.net_vol_per_min, vn30f_price
            )
```

In `get_market_snapshot()`:
```python
velocity = VelocitySnapshot(
    vn30f=self.velocity_tracker.get_vn30f_velocity(),
    basket=self.velocity_tracker.get_basket_velocity(),
    correlation=self.correlation_engine.get_correlation(),
)
# Add velocity=velocity to MarketSnapshot constructor
```

In `reset_session()`:
```python
self.velocity_tracker.reset()
self.correlation_engine.reset()
```

### Step 5: Write unit tests

`backend/tests/test_velocity_tracker.py`:
- Test minute bucket accumulation
- Test minute rotation
- Test velocity computation
- Test basket aggregation (excludes VN30F)
- Test imbalance_ratio edge cases (0 volume)

`backend/tests/test_correlation_engine.py`:
- Test Pearson with known inputs
- Test min sample guard
- Test window expiry
- Test reset

## Todo List

- [ ] Add VelocityData, VelocitySnapshot, CorrelationData to `domain.py`
- [ ] Add `velocity` field to MarketSnapshot
- [ ] Create `velocity_tracker.py` with _MinuteBucket + VelocityTracker
- [ ] Create `correlation_engine.py` with _CorrelationPoint + CorrelationEngine
- [ ] Integrate VelocityTracker into MarketDataProcessor.__init__()
- [ ] Wire on_trade() calls in handle_trade()
- [ ] Wire correlation engine minute tick
- [ ] Add velocity to get_market_snapshot()
- [ ] Add reset() calls in reset_session()
- [ ] Write test_velocity_tracker.py
- [ ] Write test_correlation_engine.py
- [ ] Run full test suite, verify no regressions

## Success Criteria

- `VelocityTracker.on_trade()` < 1ms per call
- Velocity data appears in MarketSnapshot WS broadcast
- Correlation coefficient computes correctly for known test vectors
- All existing tests pass (no regressions)
- New test coverage >= 80%

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| on_trade() too slow at peak load | Low | High | Profiled: dict lookup + int addition = ~0.1ms |
| Minute rotation missed (clock skew) | Low | Low | Use trade timestamp, not wall clock |
| VN30F symbol mismatch (contract rollover) | Medium | Medium | Use `_active_symbol` from DerivativesTracker |
| Correlation noise with low samples | High | Low | Return 0.0 and flag `sample_size < 5` in UI |

## Security Considerations

- No external input -- data comes from internal classified trades
- No DB writes -- purely in-memory computation

## Next Steps

- Phase 3 adds REST endpoints exposing VelocityTracker + CorrelationEngine
- Phase 4 frontend consumes the `velocity` field from MarketSnapshot WS
- Phase 5 PriceTracker takes VelocityTracker reference for alert rules

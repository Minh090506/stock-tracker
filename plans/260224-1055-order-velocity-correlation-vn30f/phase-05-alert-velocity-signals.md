# Phase 5: Alert System — Velocity Divergence & Imbalance Extreme Signals

## Context Links

- [alert_models.py](../../backend/app/analytics/alert_models.py) — AlertType enum, Alert model
- [price_tracker.py](../../backend/app/analytics/price_tracker.py) — detection rule pattern
- [AlertService](../../backend/app/analytics/alert_service.py) — dedup + broadcast
- [main.py](../../backend/app/main.py) — PriceTracker constructor wiring
- [types/index.ts](../../frontend/src/types/index.ts) — frontend AlertType union

## Overview

- **Priority**: P2
- **Status**: complete
- **Effort**: 2h
- **Description**: Add two new alert types to PriceTracker: `VELOCITY_DIVERGENCE` (buy velocity surging but price flat) and `IMBALANCE_EXTREME` (buy/sell ratio > 3x or < 0.33x). Wire VelocityTracker into PriceTracker.

## Key Insights

- PriceTracker already has 4 signal types with consistent pattern: public callback -> private `_check_*` method -> `AlertService.register_alert()`
- AlertService handles dedup (60s window per type+symbol) -- no duplicate logic needed
- PriceTracker needs VelocityTracker reference (add to constructor, same as foreign_tracker)
- Velocity divergence detection: compare velocity trend with price trend over 5 minutes
- Imbalance extreme: simple threshold check on `imbalance_ratio`
- Frontend signals page already renders all alert types -- just need new type in union

## Requirements

### Functional
- `VELOCITY_DIVERGENCE`: Alert when net buy velocity increases >50% in 5 min but VN30F price change < 0.1%
- `IMBALANCE_EXTREME`: Alert when buy/sell volume ratio > 3.0 (strong buy) or < 0.33 (strong sell)
- Both alert types appear on existing Signals page
- Both broadcast via `/ws/alerts` channel

### Non-Functional
- Same dedup rules as existing alerts (60s per type+symbol)
- Minimum sample guard: only alert after 10+ minutes of data
- No false positives during ATO/ATC auction sessions

## Architecture

```
VelocityTracker (Phase 2)
    |
    +---> PriceTracker.on_velocity_update()
              |
              +---> _check_velocity_divergence()
              +---> _check_imbalance_extreme()
                        |
                        +---> AlertService.register_alert()
                                  |
                                  +---> /ws/alerts broadcast
```

## Related Code Files

### Files to Modify
- `backend/app/analytics/alert_models.py` — add 2 new AlertType values
- `backend/app/analytics/price_tracker.py` — add VelocityTracker ref + 2 detection methods + callback
- `backend/app/main.py` — pass VelocityTracker to PriceTracker constructor
- `frontend/src/types/index.ts` — extend AlertType union

### Files to Reference (read-only)
- `backend/app/services/velocity_tracker.py` (from Phase 2) — VelocityData model
- `backend/app/analytics/alert_service.py` — register_alert() API

## Implementation Steps

### Step 1: Add AlertType values to `alert_models.py`

```python
class AlertType(str, Enum):
    FOREIGN_ACCELERATION = "foreign_acceleration"
    BASIS_DIVERGENCE = "basis_divergence"
    VOLUME_SPIKE = "volume_spike"
    PRICE_BREAKOUT = "price_breakout"
    VELOCITY_DIVERGENCE = "velocity_divergence"      # NEW
    IMBALANCE_EXTREME = "imbalance_extreme"          # NEW
```

### Step 2: Extend PriceTracker constructor

Add `velocity_tracker` parameter (optional for backward compat):

```python
class PriceTracker:
    def __init__(
        self,
        alert_service: AlertService,
        quote_cache: QuoteCache,
        foreign_tracker: ForeignInvestorTracker,
        derivatives_tracker: DerivativesTracker,
        velocity_tracker=None,  # NEW — optional, set after Phase 2
    ):
        ...
        self._velocity = velocity_tracker
        # Velocity divergence history: deque of (timestamp, net_velocity, vn30f_price)
        self._velocity_history: deque[tuple[datetime, float, float]] = deque(maxlen=300)
```

### Step 3: Add `on_velocity_update()` callback

```python
def on_velocity_update(self):
    """Called after each minute velocity recalculation."""
    if not self._velocity:
        return
    self._check_velocity_divergence()
    self._check_imbalance_extreme()
```

### Step 4: Implement `_check_velocity_divergence()`

```python
# Constants
_VELOCITY_WINDOW_MIN = 5
_VELOCITY_SURGE_THRESHOLD = 0.50  # 50% increase in net velocity
_PRICE_FLAT_THRESHOLD = 0.001     # 0.1% price change

def _check_velocity_divergence(self):
    """VELOCITY_DIVERGENCE: buy velocity surging but VN30F price flat."""
    vn30f_vel = self._velocity.get_vn30f_velocity()
    if not vn30f_vel or not self._derivatives:
        return

    vn30f_price = self._derivatives.get_futures_price(
        self._derivatives._active_symbol
    )
    if vn30f_price <= 0:
        return

    now = datetime.now()
    self._velocity_history.append((now, vn30f_vel.net_vol_per_min, vn30f_price))

    # Need 5+ minutes of data
    cutoff = now - timedelta(minutes=_VELOCITY_WINDOW_MIN)
    past = [(ts, nv, p) for ts, nv, p in self._velocity_history if ts <= cutoff]
    if not past:
        return

    past_vel = past[-1][1]
    past_price = past[-1][2]
    current_vel = vn30f_vel.net_vol_per_min

    # Guard: need meaningful baseline velocity
    if abs(past_vel) < 100:
        return

    vel_change = (current_vel - past_vel) / abs(past_vel)
    price_change = abs(vn30f_price - past_price) / past_price

    if vel_change > _VELOCITY_SURGE_THRESHOLD and price_change < _PRICE_FLAT_THRESHOLD:
        direction = "mua" if current_vel > 0 else "bán"
        symbol = self._derivatives._active_symbol or "VN30F"
        self._alerts.register_alert(Alert(
            alert_type=AlertType.VELOCITY_DIVERGENCE,
            severity=AlertSeverity.WARNING,
            symbol=symbol,
            message=f"Velocity divergence: {direction} velocity +{vel_change:.0%} but price flat ({price_change:.2%})",
            data={
                "net_velocity": round(current_vel, 1),
                "prev_velocity": round(past_vel, 1),
                "vel_change_pct": round(vel_change, 3),
                "price_change_pct": round(price_change, 4),
                "vn30f_price": vn30f_price,
            },
        ))
```

### Step 5: Implement `_check_imbalance_extreme()`

```python
_IMBALANCE_HIGH = 3.0   # buy/sell ratio > 3.0 = extreme buy
_IMBALANCE_LOW = 0.33   # buy/sell ratio < 0.33 = extreme sell

def _check_imbalance_extreme(self):
    """IMBALANCE_EXTREME: buy/sell ratio extremely skewed."""
    vn30f_vel = self._velocity.get_vn30f_velocity()
    if not vn30f_vel:
        return

    ratio = vn30f_vel.imbalance_ratio
    # imbalance_ratio = buy/(buy+sell), convert to buy/sell ratio
    if ratio <= 0 or ratio >= 1:
        return  # avoid division by zero
    buy_sell_ratio = ratio / (1 - ratio)

    symbol = self._derivatives._active_symbol or "VN30F" if self._derivatives else "VN30F"

    if buy_sell_ratio > _IMBALANCE_HIGH:
        self._alerts.register_alert(Alert(
            alert_type=AlertType.IMBALANCE_EXTREME,
            severity=AlertSeverity.WARNING,
            symbol=symbol,
            message=f"Extreme buy imbalance: ratio {buy_sell_ratio:.1f}x ({ratio:.0%} buy)",
            data={"imbalance_ratio": round(ratio, 3),
                  "buy_sell_ratio": round(buy_sell_ratio, 1)},
        ))
    elif buy_sell_ratio < _IMBALANCE_LOW:
        sell_buy_ratio = 1 / buy_sell_ratio if buy_sell_ratio > 0 else 0
        self._alerts.register_alert(Alert(
            alert_type=AlertType.IMBALANCE_EXTREME,
            severity=AlertSeverity.WARNING,
            symbol=symbol,
            message=f"Extreme sell imbalance: ratio {sell_buy_ratio:.1f}x ({1-ratio:.0%} sell)",
            data={"imbalance_ratio": round(ratio, 3),
                  "buy_sell_ratio": round(buy_sell_ratio, 2)},
        ))
```

### Step 6: Wire in `main.py`

Update PriceTracker instantiation:

```python
# After velocity_tracker is created in processor (Phase 2):
price_tracker = PriceTracker(
    alert_service, processor.quote_cache,
    processor.foreign_tracker, processor.derivatives_tracker,
    velocity_tracker=processor.velocity_tracker,  # NEW
)
```

Wire the callback in `MarketDataProcessor.handle_trade()` (after velocity minute rotation):
```python
if self.price_tracker and self.velocity_tracker.get_minute_rotated_symbols():
    self.price_tracker.on_velocity_update()
```

### Step 7: Update frontend AlertType

In `frontend/src/types/index.ts`:

```typescript
export type AlertType =
  | "foreign_acceleration"
  | "basis_divergence"
  | "volume_spike"
  | "price_breakout"
  | "velocity_divergence"    // NEW
  | "imbalance_extreme";     // NEW
```

Update any alert label/icon mappings in signals page components (if hardcoded).

### Step 8: Write tests

`backend/tests/test_velocity_alerts.py`:
- Test velocity divergence triggers with mocked velocity data
- Test divergence does NOT trigger when price moves proportionally
- Test imbalance extreme triggers at ratio > 3.0
- Test imbalance extreme triggers at ratio < 0.33
- Test no alert when ratio is moderate (0.4-0.6)
- Test dedup (same alert not repeated within 60s)
- Test no alert with insufficient data (<5 minutes)

## Todo List

- [x] Add VELOCITY_DIVERGENCE, IMBALANCE_EXTREME to AlertType enum
- [x] Add velocity_tracker param to PriceTracker constructor
- [x] Add _velocity_history deque to PriceTracker
- [x] Implement on_velocity_update() callback
- [x] Implement _check_velocity_divergence()
- [x] Implement _check_imbalance_extreme()
- [x] Wire velocity_tracker in main.py PriceTracker constructor
- [x] Wire on_velocity_update() call in handle_trade()
- [x] Update frontend AlertType union
- [x] Update alert label/icon mappings if needed
- [x] Write test_velocity_alerts.py
- [x] Run full test suite

## Success Criteria

- Velocity divergence alert fires when velocity surges >50% but price flat
- Imbalance extreme alert fires when buy/sell ratio > 3x or < 0.33x
- Alerts appear on Signals page with correct type labels
- Alerts broadcast via /ws/alerts in real-time
- No false positives during ATO/ATC (velocity tracker should have low counts)
- All existing alert tests pass (no regressions)
- New alert tests have 80%+ coverage

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Too many false velocity divergence alerts | Medium | Medium | Minimum velocity baseline guard (>100 vol/min) |
| Imbalance alert noise during low-volume periods | Medium | Low | AlertService 60s dedup prevents flood |
| PriceTracker constructor change breaks existing code | Low | Medium | velocity_tracker param is optional with default=None |
| ATO/ATC auction volume spikes trigger false imbalance | Medium | Medium | Velocity tracker naturally low during auction (few classified trades) |

## Security Considerations

- No external input -- all data from internal velocity tracker
- Alert messages contain market data only (no PII)

## Next Steps

- Monitor false positive rate in production, tune thresholds if needed
- Future: weighted alert severity based on correlation strength
- Future: configurable alert thresholds via UI settings

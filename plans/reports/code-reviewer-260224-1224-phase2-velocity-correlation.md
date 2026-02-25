# Code Review: Phase 2 — Order Velocity & Correlation

**Date:** 2026-02-24
**Reviewer:** code-reviewer agent
**Scope:** velocity_tracker, correlation_engine, domain models, market_data_processor integration, test suites

---

## Code Review Summary

### Scope
- Files reviewed: 6
  - `backend/app/models/domain.py` (VelocityData, VelocitySnapshot, CorrelationData, MarketSnapshot.velocity)
  - `backend/app/services/velocity_tracker.py` (155 LOC)
  - `backend/app/services/correlation_engine.py` (101 LOC)
  - `backend/app/services/market_data_processor.py` (modified)
  - `backend/tests/test_velocity_tracker.py` (23 tests)
  - `backend/tests/test_correlation_engine.py` (16 tests)
- Lines of code analyzed: ~570
- Review focus: recent feature addition (phase 2)
- Updated plans: none (no plan file provided)

### Overall Assessment

Solid implementation. All 39 tests pass. Performance is far inside the <1ms budget (0.5µs avg per `on_trade()` at 2M trades/sec). The Pearson formula is correct and the deque bounds are safe. Two real issues found: a floating-point edge case in `_pearson()` that can produce `|r| > 1`, and NEUTRAL trades counted as sells (semantic ambiguity). One minor private-attribute access in `_feed_velocity`. Test docstring has a wrong expected value.

---

### Critical Issues

None.

---

### High Priority Findings

#### H1: `_pearson()` can return values outside `[-1.0, 1.0]`

**File:** `backend/app/services/correlation_engine.py`, line 44
**Impact:** `CorrelationData.coefficient` is documented as `-1 to +1`. Sending `coefficient=1.007` to the frontend would break any UI gauge clamped to that range.

**Cause:** The two-pass formula `(n*sum_x2 - sum_x²)` computes variance as a difference of large squares. When relative variance is extremely small (e.g., velocity barely changes over the window), floating-point cancellation causes the denominator to be slightly underestimated, so `num/den > 1.0`.

**Reproduction:**
```python
x = [1.0000001, 1.0000002, 1.0000003, 1.0000004, 1.0000005]
y = [2.0000001, 2.0000002, 2.0000003, 2.0000004, 2.0000005]
_pearson(x, y)  # → 1.007
```

**Practical risk:** Occurs only when relative variance ≈ 1e-7. In production this requires velocity to stay nearly constant for 15 minutes — uncommon but possible during slow pre-ATO periods.

**Fix:** Clamp return value.
```python
# correlation_engine.py line 45
return max(-1.0, min(1.0, num / den)) if den > 0 else 0.0
```

---

### Medium Priority Improvements

#### M1: NEUTRAL trades counted as sells in velocity tracker

**File:** `backend/app/services/market_data_processor.py`, line 143
```python
is_buy = classified.trade_type == TradeType.MUA_CHU_DONG
```
`TradeType.NEUTRAL` maps to `is_buy=False`, so neutral volume accumulates in `sell_vol` and `sell_count`. This biases `imbalance_ratio` toward 0 and inflates `sell_vol_per_min`. ATO/ATC sessions generate significant neutral volume.

**Options:**
- **A (minimal change):** Skip feeding neutral trades to velocity tracker entirely — only classified buy/sell trades carry directional signal.
- **B (explicit):** Add `is_neutral` parameter and accumulate to a separate `neutral_vol` bucket (adds complexity, YAGNI).

Option A is recommended — neutral trades have no velocity signal. The fix is one line in `_feed_velocity`:
```python
def _feed_velocity(self, classified) -> None:
    if classified.trade_type == TradeType.NEUTRAL:
        return  # no directional signal
    is_buy = classified.trade_type == TradeType.MUA_CHU_DONG
    ...
```

#### M2: `_should_rotate()` triggers on backward-time trades

**File:** `backend/app/services/velocity_tracker.py`, line 75
The check `now.minute != bucket.timestamp.minute` is true for both forward AND backward time. If SSI delivers a trade with an earlier timestamp (rare but possible), the current bucket gets spuriously rotated backward, corrupting `_history`.

**Example:**
```python
# bucket at minute 5, trade arrives with minute 4
# _should_rotate returns True → bucket at min 5 is saved to history
# new current bucket starts at min 4
# next trade at min 5 triggers ANOTHER rotation
```

**Fix:** Guard against backward time in `_should_rotate`:
```python
def _should_rotate(self, bucket: _MinuteBucket, now: datetime) -> bool:
    # Only rotate forward
    return now > bucket.timestamp and (
        now.minute != bucket.timestamp.minute
        or now.hour != bucket.timestamp.hour
    )
```

#### M3: Private attribute access `derivatives_tracker._active_symbol`

**File:** `backend/app/services/market_data_processor.py`, line 151
```python
active = self.derivatives_tracker._active_symbol
```
`_active_symbol` is a private attribute. If `DerivativesTracker` refactors it, this silently breaks. Recommend exposing a property:
```python
# In derivatives_tracker.py
@property
def active_symbol(self) -> str:
    return self._active_symbol
```
Then: `active = self.derivatives_tracker.active_symbol`

---

### Low Priority Suggestions

#### L1: Test docstring value mismatch

**File:** `backend/tests/test_correlation_engine.py`, line 37
```python
def test_known_correlation_value(self):
    # Known Pearson r ≈ 0.9856 for these data points   ← WRONG
    ...
    assert abs(r - 0.9945) < 0.01
```
Actual computed value is `r=0.9919`. The comment says `0.9856`, the assert says `0.9945` — both wrong. The assert passes because tolerance is `0.01` and `|0.9919 - 0.9945| = 0.003 < 0.01`. Fix the comment:
```python
# Known Pearson r ≈ 0.9919 for these data points
```

#### L2: `_rotated` semantics: set is valid only for the most recent `on_trade()` call

**File:** `backend/app/services/velocity_tracker.py`, line 56
`_rotated.clear()` at the top of `on_trade()` means the set only reflects the last single call. The docstring on `get_minute_rotated_symbols()` says "on the last on_trade() call" which is accurate — just ensure callers read it before the next `on_trade()`. The current `_feed_velocity()` usage is correct (check immediately after each call). No code change needed but worth documenting more prominently.

#### L3: `list(history)[-_SPEED_WINDOW_MIN:]` creates full deque copy

**File:** `backend/app/services/velocity_tracker.py`, lines 100, 159
`list(history)` copies all 60 items to slice the last 5. `itertools.islice` from the right is awkward with deques; the copy is acceptable at 30 symbols × 60 items = 1800 items. Not worth changing unless profiling shows it as hot.

#### L4: `datetime.now()` called multiple times per snapshot

`_compute_velocity()` and `get_basket_velocity()` each call `datetime.now()`. In `get_market_snapshot()` both are called, producing slightly different timestamps for `vn30f` vs `basket`. Cosmetic; no functional impact.

---

### Positive Observations

- `__slots__` on `_MinuteBucket` and `_CorrelationPoint` — excellent memory optimization for high-frequency objects
- `deque(maxlen=...)` for automatic ring-buffer behavior — correct and safe
- Pure Python Pearson without numpy — appropriate for this use case (no numpy dep, 15 samples max)
- `_feed_velocity()` check `if vn30f_price > 0` before feeding correlation — good guard
- `reset_session()` correctly resets both velocity and correlation engines
- Test suite covers edge cases well: zero volume, all-buy, all-sell, hour boundary, post-reset usage
- Performance: 0.5µs avg per `on_trade()` at 30-symbol load — **1000x within the 1ms budget**
- Model additions in `domain.py` are minimal, well-typed, and consistent with existing patterns
- `VelocitySnapshot` wraps optional fields cleanly — no breaking change to `MarketSnapshot` consumers

---

### Recommended Actions

1. **(High)** Clamp `_pearson()` return to `[-1.0, 1.0]` — one-line fix in `correlation_engine.py`
2. **(Medium)** Skip NEUTRAL trades in `_feed_velocity()` — one-line guard, improves signal quality
3. **(Medium)** Guard backward-time in `_should_rotate()` — prevents rare SSI out-of-order corruption
4. **(Medium)** Expose `active_symbol` as a public property on `DerivativesTracker`
5. **(Low)** Fix test comment: `r ≈ 0.9856` → `r ≈ 0.9919` in `test_known_correlation_value`

---

### Metrics

- Test coverage: 39/39 tests pass (100% pass rate)
- Performance: 0.5µs avg per `on_trade()` (budget: 1000µs) — **2000x headroom**
- Linting issues: 0 syntax errors, 0 import errors
- Type coverage: fully typed (Python 3.12 union syntax `X | None` used correctly)
- Deque memory: 30 symbols × 60 buckets × ~7 ints/floats ≈ ~50KB total — safe

---

### Unresolved Questions

1. Is NEUTRAL-as-sell intentional? If ATO/ATC sessions produce mostly neutral trades, the current behavior significantly inflates sell metrics. Clarify desired semantics before shipping the frontend widget.
2. Should `CorrelationEngine.on_minute_tick()` be called on VN30F rotation specifically (not basket rotation)? Currently it triggers on ANY symbol's rotation and uses the latest VN30F velocity — is this the intended sampling frequency?

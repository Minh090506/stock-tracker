# Code Review: Phase 6 — Backtest Analysis Engine

**Date**: 2026-02-24
**Reviewer**: code-reviewer agent
**Branch**: master

---

## Code Review Summary

### Scope
- Files reviewed: 6 new files
  - `backend/app/analytics/backtest_models.py` (61 LOC)
  - `backend/app/analytics/backtest_engine.py` (293 LOC)
  - `backend/app/routers/backtest_router.py` (82 LOC)
  - `backend/app/main.py` (274 LOC, wiring section only)
  - `backend/tests/test_backtest_engine.py` (250 LOC)
  - `backend/tests/test_backtest_router.py` (170 LOC)
- Lines of code analyzed: ~1,130 total
- Review focus: new phase 6 implementation

### Overall Assessment
Core analysis logic (Pearson, cross-correlation, threshold binning, pattern grouping) is sound and well-tested. SQL is correctly parameterized. Async patterns are correct. **One critical bug** found: the scheduler in `main.py` and the router create separate `BacktestEngine` instances — the pre-computed cache is never accessible via the REST API.

---

## Critical Issues

### [CRITICAL] Two BacktestEngine instances — cache never shared

**File**: `backend/app/main.py` (L195) + `backend/app/routers/backtest_router.py` (L19–22)

`main.py` creates one instance to run the daily scheduled report:
```python
# main.py lifespan — line 195
backtest_engine = BacktestEngine(db.pool)   # instance A — populates _cache
```

`backtest_router.py` lazily creates a **separate** instance on first API request:
```python
# backtest_router.py _get_engine() — line 21
_engine = BacktestEngine(db.pool)           # instance B — _cache always None
```

`GET /api/backtest/summary` always returns 404 even after the daily 15:30 run completes, because instance B's `_cache` is never written.

**Fix**: Store the engine on `app.state` in lifespan and read it back in the router:

```python
# main.py lifespan (line 194-196) — replace with:
if db_available:
    backtest_engine = BacktestEngine(db.pool)
    app.state.backtest_engine = backtest_engine   # share via app.state
    backtest_task = asyncio.create_task(_daily_backtest_loop())

# backtest_router.py _get_engine() — replace with:
def _get_engine(request: Request) -> BacktestEngine:
    if not getattr(request.app.state, "db_available", False):
        raise HTTPException(status_code=503, detail="Database unavailable")
    engine = getattr(request.app.state, "backtest_engine", None)
    if engine is None:
        raise HTTPException(status_code=503, detail="Backtest engine not initialized")
    return engine
```

This also eliminates the `assert db.pool is not None` (which would yield unhandled `AssertionError` → 500).

---

## High Priority Findings

### [HIGH] `vn30f_price` None not guarded in cross-correlation and threshold analysis

**File**: `backend/app/analytics/backtest_engine.py` L134–138 and L180–189

`imbalance_ratio` and `net_velocity` have `or 0.0` / `if imb is None` guards, but `vn30f_price` does not. If a candle row has a NULL close (e.g., data gap), arithmetic on `prices` list raises `TypeError`:

```python
# run_cross_correlation — L135
prices = [r["vn30f_price"] for r in rows]           # no None guard
price_changes = [prices[i] - prices[i - 1] ...]     # TypeError if None

# run_threshold_analysis — L180-189
prices = [r["vn30f_price"] for r in rows]           # no None guard
change = prices[i + lookahead] - prices[i]          # TypeError if None
```

**Fix**:
```python
# Filter out rows with null price at fetch time:
rows = [r for r in rows if r["vn30f_price"] is not None]
# or guard inline:
prices = [r["vn30f_price"] or 0.0 for r in rows]
```

Filtering rows entirely is cleaner to avoid misaligned index shifts.

### [HIGH] `backtest_engine.py` exceeds 200 LOC guideline

**File**: `backend/app/analytics/backtest_engine.py` — 293 lines

Exceeds the 200 LOC modularisation guideline. The file has three natural split points:
- SQL constants block (L60–96) → `backtest_queries.py`
- Pure functions `_pearson` / `_session_phase` (L31–55) → `backtest_utils.py`
- `BacktestEngine` class remains in `backtest_engine.py`

After splitting: engine ~180 LOC, queries ~40 LOC, utils ~30 LOC.

---

## Medium Priority Improvements

### [MEDIUM] `candle_symbol` assignment is a no-op

**File**: `backend/app/analytics/backtest_engine.py` L113

```python
candle_symbol = symbol if is_futures else symbol    # always `symbol`
```

Both branches assign the same value. Dead code. The variable was likely intended for a future basket→futures mapping (e.g., default to `"VN30F2603"` when basket). Remove or document intent:

```python
candle_symbol = symbol   # futures: same symbol; basket: caller passes candle symbol
```

### [MEDIUM] `assert` in router should be `HTTPException`

**File**: `backend/app/routers/backtest_router.py` L20

```python
assert db.pool is not None    # raises AssertionError → unhandled 500
```

Already made moot by the critical fix above (engine from `app.state`), but if retained, convert to:
```python
if db.pool is None:
    raise HTTPException(status_code=503, detail="Database pool unavailable")
```

### [MEDIUM] Rate limiting not implemented

**Plan** (`phase-06-backtest-analysis-engine.md`) specifies: "Rate limit backtest endpoints (heavy queries) — max 1 concurrent per IP."

On-demand endpoints (`/correlation`, `/threshold`, `/patterns`) can each trigger a full 20-day DB scan. No concurrency guard exists. This is low risk in closed environments but should be tracked.

### [MEDIUM] `run_daily_report` uses naive `datetime.now()`, inconsistent with `main.py`

**File**: `backend/app/analytics/backtest_engine.py` L275–277

```python
now = datetime.now()          # naive local time (backtest_engine.py)
# vs
now = datetime.now(_VN_TZ)   # timezone-aware VN time (main.py)
```

The `_daily_backtest_loop` in `main.py` fires at correct VN time, but `run_daily_report` itself uses local time for `date_from`. In a Docker container running UTC this drifts 7 hours. `_date_range()` in the router has the same issue.

**Fix**: Accept a `now` parameter or import and use `_VN_TZ` consistently:
```python
from datetime import timezone
import zoneinfo
_VN_TZ = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")
now = datetime.now(_VN_TZ)
```

---

## Low Priority Suggestions

### [LOW] No test covering the engine instance / cache-sharing bug

The router tests mock `_get_engine` entirely, bypassing the real singleton wiring. A smoke-test that exercises the actual lifespan path would catch the cache-sharing bug at CI time.

### [LOW] `_session_phase` has no guard for hours outside market range

If called with hour=8 or hour=15, it returns `"continuous"`. The SQL already filters `BETWEEN 9 AND 14`, so this is safe in practice, but a defensive check or docstring clarification would aid maintenance.

### [LOW] `cross_correlation` velocity alignment comment is implicit

```python
velocities = velocities[:-1] if len(velocities) > len(price_changes) else velocities
```

This slice is correct (aligning N velocities with N−1 price deltas) but the logic is subtle. A one-line comment explaining the alignment would improve readability.

### [LOW] `optimal_lag` selection picks first maximum on tie

```python
optimal = max(results, key=lambda r: abs(r.correlation)) if results else None
```

`max()` returns the first element with the maximum value on ties — i.e., prefers smaller lag when correlations are equal. This is sensible behavior but worth documenting.

---

## Positive Observations

- **Pearson implementation** is clean, numerically stable, clamps to `[-1, 1]`, and handles zero variance and insufficient data correctly.
- **SQL injection safety**: all 3 SQL statements are parameterized with `$1/$2/$3`. No string interpolation anywhere.
- **Binning logic** correctly handles the `imbalance == 1.0` edge case in the last bin.
- **Async patterns** are correct: all DB calls use `await pool.fetch/fetchval`, no blocking calls in async functions.
- **Test coverage**: 27 tests covering all three analysis types, edge cases (empty data, zero variance, session phases), and HTTP layer. All 473 total tests pass.
- **Graceful degradation**: scheduler silently skips if DB unavailable; `run_daily_report` returns `None` on insufficient data.
- **Consistent router pattern**: `_get_engine` follows the same lazy-init guard pattern as `history_router._get_svc`.
- **Model separation** in `backtest_models.py` is clean (62 LOC, no logic, pure Pydantic).

---

## Recommended Actions

1. **[CRITICAL — fix before merge]** Share `BacktestEngine` via `app.state` so the scheduler and router use the same instance. The cache-sharing fix is ~5 lines across `main.py` + `backtest_router.py`.

2. **[HIGH — fix soon]** Add None guard for `vn30f_price` in `run_cross_correlation` and `run_threshold_analysis` (filter rows with null price after fetch).

3. **[HIGH]** Split `backtest_engine.py` at the 200 LOC boundary — move SQL constants and pure functions to separate modules.

4. **[MEDIUM]** Replace `assert db.pool is not None` with `HTTPException(503)`.

5. **[MEDIUM]** Replace `datetime.now()` with `datetime.now(_VN_TZ)` in `backtest_engine.py` and `backtest_router.py` for timezone consistency.

6. **[MEDIUM]** Remove or document the no-op `candle_symbol` assignment (L113).

7. **[LOW]** Add a test that verifies `get_cached_report()` reflects a previously run `run_daily_report()` call — covering the instance-sharing contract.

---

## Metrics

- Type Coverage: 100% (all functions typed, Pydantic models fully typed)
- Test Coverage: 27/27 new tests pass; 473/473 total pass
- Compile Errors: 0
- Linting Issues: 0 syntax errors; 1 dead code (candle_symbol no-op)
- File Size Violations: 1 (`backtest_engine.py` at 293 LOC vs 200 guideline)

---

## Task Completeness

Plan file: `plans/260224-1055-order-velocity-correlation-vn30f/phase-06-backtest-analysis-engine.md`

| Task | Status |
|------|--------|
| Create `backtest_models.py` with result Pydantic models | DONE |
| Create `backtest_engine.py` with 3 analysis methods + Pearson | DONE |
| Create `backtest_router.py` with 4 REST endpoints | DONE |
| Wire backtest scheduler in `main.py` (15:30 daily) | DONE |
| Write unit tests for Pearson, cross-correlation, threshold binning | DONE |
| Validate with sample data (>5 days accumulated) | DEFERRED (requires live data; manual) |

**Overall**: Implementation is complete. One critical bug (engine instance isolation) must be fixed before `GET /api/backtest/summary` works in production.

---

## Unresolved Questions

1. **Basket symbol intent**: When `is_futures=False`, `_BASKET_VELOCITY_PRICE_SQL` joins `vn30_basket_velocity_1m` (all VN30 stocks aggregated) with `candles_1m c WHERE c.symbol = $1`. If a non-futures symbol like `VNM` is passed, this pairs aggregate basket velocity with a single stock's candle — is that the intended analysis, or should non-futures always resolve to `VN30F2603` candles?

2. **Rate limiting**: Plan specifies "max 1 concurrent per IP" for on-demand endpoints. Is this deferred to Phase 7 frontend or explicitly out of scope for Phase 6?

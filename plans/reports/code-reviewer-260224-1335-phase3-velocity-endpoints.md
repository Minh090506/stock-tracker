# Code Review: Phase 3 — Velocity REST Endpoints

**Date**: 2026-02-24
**Score**: 9/10
**Reviewer**: code-reviewer agent

---

## Scope

- Files reviewed: `backend/app/routers/market_router.py` (lines 14–24, 76–109), `backend/app/database/history_service.py` (lines 171–207)
- Lines of code analyzed: ~70 new lines
- Reference context: `history_router.py`, `alembic/versions/003_order_velocity_aggregate.py`, `app/models/domain.py`, `app/services/market_data_processor.py`, `phase-03-api-velocity-endpoints.md`

---

## Overall Assessment

Implementation is clean, correct, and consistent with the existing codebase. All three endpoints from the plan are present. SQL is fully parameterized. 503 guard works. One minor deviation from the plan spec (model_dump serialization on `/velocity` endpoint) and one negligible inconsistency with the helper name vs `history_router.py`. No critical or high-priority issues.

---

## Critical Issues

None.

---

## High Priority Findings

None.

---

## Medium Priority Improvements

### M1: `/velocity` endpoint returns empty dict `{}` instead of `null`/documented structure

**File**: `market_router.py` lines 85–87

```python
if snapshot.velocity is None:
    return {}
return snapshot.velocity.model_dump()
```

The plan spec says `return snapshot.velocity` (direct Pydantic return — FastAPI serializes it). The implementation manually calls `model_dump()` which is fine, but when velocity is `None` it returns `{}` (empty dict) instead of `null`. This creates an ambiguous response contract: consumers cannot distinguish "service started but no data yet" from "empty data structure".

**Recommendation**: Return `None` (FastAPI serializes as JSON `null`) or a consistent empty `VelocitySnapshot`:

```python
if snapshot.velocity is None:
    return None  # serializes to JSON null — clear signal to client
return snapshot.velocity.model_dump()
```

Or simpler (let FastAPI handle serialization):
```python
return snapshot.velocity  # None → null, VelocitySnapshot → full JSON
```

---

### M2: `_history_svc` in `market_router.py` is a module-level singleton shared across all requests

**File**: `market_router.py` lines 15–24

```python
_history_svc: HistoryService | None = None

def _get_history_svc(request: Request) -> HistoryService:
    global _history_svc
    ...
    if _history_svc is None:
        _history_svc = HistoryService(db)
    return _history_svc
```

This pattern is identical to `history_router.py`'s `_svc` — it is an established codebase convention and not a new problem. However, it is a module-level mutable global shared across requests (no locking). In practice asyncio is single-threaded so there is no race condition, but it is worth noting the pattern is fragile if threading is ever introduced.

**Severity**: Low concern — consistent with existing pattern, safe under asyncio.

---

## Low Priority Suggestions

### L1: Missing `ge=1` lower bound on `Query(30, ge=1, le=120)` for `basis-trend` but present on new velocity endpoints

The new velocity endpoints correctly use `Query(60, ge=1, le=480)` matching the plan's spec. The existing `basis-trend` endpoint uses `Query(30, ge=1, le=120)` also correctly. No issue — just confirming parity.

### L2: `symbol` input is `.upper()` normalized but not length-validated

**File**: `market_router.py` line 98

```python
return await svc.get_velocity_history(symbol.upper(), minutes)
```

An arbitrarily long `symbol` string is passed to a parameterized query (`$1`), so SQL injection is not possible. However, there is no max-length validation. For consistency with stock exchange symbol conventions (e.g., max 12 chars for VN30F contracts):

```python
symbol: str = Query(..., min_length=1, max_length=20, description="Symbol (e.g., VN30F2603, VPB)")
```

Low priority — parameterized query makes this a style concern rather than security issue.

### L3: `_get_history_svc` naming vs `_get_svc` in history_router

`history_router.py` uses `_get_svc`, new code uses `_get_history_svc`. The longer name is actually more descriptive given that `market_router.py` also uses in-memory services. No change required — this is better.

### L4: Plan TODO item "Update README API table" not verifiable in this review

The plan's todo list includes updating `README.md` with the three new endpoints. This was not part of the files scoped for review. Recommend confirming it was completed.

---

## Positive Observations

1. **SQL injection safety**: Both query methods use asyncpg parameterized queries (`$1`, `$2`) with typed Python values — no string interpolation anywhere.

2. **`make_interval(mins => $2)` pattern**: Correct and safe way to pass integer minutes to a PostgreSQL interval. Avoids the string-cast trick used in `get_foreign_flow_daily_summary` (`($2 || ' days')::INTERVAL`), which is the more idiomatic asyncpg approach.

3. **503 guard is clean**: `_get_history_svc()` checks `request.app.state.db_available` before constructing service — consistent with `history_router.py`. The `/velocity` endpoint correctly bypasses DB check (in-memory only).

4. **Column selection is explicit**: Both query methods select named columns (not `SELECT *`), which is resilient to schema changes adding new columns.

5. **Exact match to plan spec**: Implementation matches the plan's code examples almost verbatim — evidence of disciplined implementation.

6. **Consistent file organization**: Velocity methods placed under a `# -- Velocity --` section comment in `history_service.py`, matching the existing `# -- Candles --`, `# -- Foreign flow --` section pattern.

7. **`symbol.upper()` normalization**: Applied in both endpoints consistently, matching `history_router.py`.

---

## Recommended Actions

1. **[Medium]** Fix `/velocity` endpoint to return `None` (JSON `null`) when no velocity data, rather than `{}`.
2. **[Low]** Add `max_length=20` to `symbol` Query param for defensive validation.
3. **[Low]** Confirm README was updated with new endpoint table (plan TODO item L4).

---

## Metrics

- Type Coverage: N/A (Python, no mypy run in scope)
- Test Coverage: Existing `test_velocity_tracker.py` covers service layer; no new endpoint-level tests were scoped for Phase 3
- Linting Issues: 0 identified
- SQL Injection: 0 risks (parameterized throughout)
- Plan TODO Completion: 8/9 items verifiable in reviewed files (README update unconfirmed)

---

## Phase 3 Plan TODO Status

| Task | Status |
|------|--------|
| Add `get_velocity_history()` to HistoryService | DONE |
| Add `get_basket_velocity_history()` to HistoryService | DONE |
| Add `GET /api/market/velocity` to market_router | DONE |
| Add `GET /api/market/velocity/history` to market_router | DONE |
| Add `GET /api/market/velocity/basket-history` to market_router | DONE |
| Add `_get_history_svc()` helper to market_router | DONE |
| Update README API table | UNCONFIRMED |
| Test endpoints with curl / httpie | UNCONFIRMED (out of scope) |
| Verify WS market channel includes velocity data | UNCONFIRMED (out of scope) |

---

## Unresolved Questions

1. Was the README updated with the three new endpoints? (Plan TODO Step 3 not verified.)
2. Is `vn30_basket_velocity_1m` a plain `VIEW` — does it re-aggregate from `order_velocity_1m` at query time? If yes, a query with `minutes=480` on a busy day could be slow since the view has no TimescaleDB materialization. Consider benchmarking or adding a `LIMIT` safety valve.

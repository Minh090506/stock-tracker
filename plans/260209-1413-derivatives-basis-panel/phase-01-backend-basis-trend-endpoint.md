# Phase 1: Backend — Basis Trend REST Endpoint

## Priority: P1 | Status: pending | Effort: 20min

## Overview

Expose `DerivativesTracker.get_basis_trend()` via a new REST endpoint. The method already exists and returns `list[BasisPoint]`. Only need to wire it to a route.

## Context Links

- [DerivativesTracker](../../backend/app/services/derivatives_tracker.py) — `get_basis_trend(minutes)` at line 83
- [market_router.py](../../backend/app/routers/market_router.py) — add endpoint here
- [domain.py](../../backend/app/models/domain.py) — `BasisPoint` model at line 117
- [main.py](../../backend/app/main.py) — `processor` singleton, access via `processor.derivatives_tracker`

## Key Insights

- `get_basis_trend(minutes=30)` already filters by time window from in-memory deque
- `BasisPoint` is a Pydantic `BaseModel` — FastAPI serializes it automatically
- Pattern: existing endpoints import `processor` from `app.main` inside the function body (lazy import to avoid circular deps)

## Requirements

- `GET /api/market/basis-trend?minutes=30` returns `list[BasisPoint]`
- Default `minutes=30`, max `minutes=60` (deque only holds ~60min of data)
- Empty list when no data available (no error)

## Related Code Files

- **Modify**: `backend/app/routers/market_router.py`

## Implementation Steps

1. Add new endpoint to `market_router.py`:

```python
@router.get("/basis-trend")
async def get_basis_trend(minutes: int = Query(30, ge=1, le=60)):
    """Basis history points for the given time window."""
    from app.main import processor

    return processor.derivatives_tracker.get_basis_trend(minutes)
```

2. Add `Query` import from `fastapi` at top of file (already has `APIRouter`)

## Todo

- [ ] Add `Query` import to market_router.py
- [ ] Add `/basis-trend` endpoint
- [ ] Verify endpoint returns correct JSON with `curl` or browser

## Success Criteria

- `GET /api/market/basis-trend` returns `[]` when no data
- `GET /api/market/basis-trend?minutes=10` returns filtered list
- Response shape: `[{timestamp, futures_symbol, futures_price, spot_value, basis, basis_pct, is_premium}]`

## Risk Assessment

- **None** — trivial wiring of existing method to route

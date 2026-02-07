# Phase 1: Backend Market Snapshot REST API

## Context

- `MarketDataProcessor.get_market_snapshot()` exists but NOT exposed via REST
- `ForeignInvestorTracker.get_all()` returns per-symbol dict (not in snapshot)
- Need per-symbol foreign detail for heatmap + bar chart
- Existing router pattern: `backend/app/routers/history_router.py`

## Overview

- **Priority**: P1 (blocks all frontend phases)
- **Status**: pending
- **Effort**: 1h

## Requirements

1. `GET /api/market/snapshot` -- returns full `MarketSnapshot` (quotes + indices + foreign summary + derivatives)
2. `GET /api/market/foreign-detail` -- returns per-symbol `ForeignInvestorData[]` (needed for heatmap/table)
3. `GET /api/market/volume-stats` -- returns per-symbol `SessionStats[]` (needed for volume page)

## Files to Create

### `backend/app/routers/market_router.py` (~60 lines)

```python
"""REST endpoints for real-time market data snapshots."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/market", tags=["market"])

# Import processor singleton from main.py
# Use a lazy getter pattern like history_router does

@router.get("/snapshot")
async def get_snapshot():
    """Full market snapshot: quotes + indices + foreign + derivatives."""
    from app.main import processor
    return processor.get_market_snapshot()

@router.get("/foreign-detail")
async def get_foreign_detail():
    """Per-symbol foreign investor data for heatmap/table."""
    from app.main import processor
    data = processor.foreign_tracker.get_all()
    summary = processor.get_foreign_summary()
    return {"summary": summary, "stocks": list(data.values())}

@router.get("/volume-stats")
async def get_volume_stats():
    """Per-symbol active buy/sell session stats."""
    from app.main import processor
    stats = processor.aggregator.get_all_stats()
    return {"stats": list(stats.values())}
```

### Modify: `backend/app/main.py`

Add 2 lines:
```python
from app.routers.market_router import router as market_router
# ...
app.include_router(market_router)  # after history_router
```

## Implementation Steps

1. Create `backend/app/routers/market_router.py` with 3 endpoints
2. Register router in `backend/app/main.py`
3. Test manually: `curl http://localhost:8000/api/market/snapshot`
4. Verify JSON serialization of Pydantic models (datetime -> ISO string)

## Todo

- [ ] Create `market_router.py` with `/snapshot`, `/foreign-detail`, `/volume-stats`
- [ ] Register in `main.py`
- [ ] Verify all 3 endpoints return valid JSON

## Success Criteria

- `GET /api/market/snapshot` returns `MarketSnapshot` JSON (even if empty when no stream connected)
- `GET /api/market/foreign-detail` returns `{ summary: {...}, stocks: [...] }`
- `GET /api/market/volume-stats` returns `{ stats: [...] }`
- Response time <50ms (all in-memory lookups)

## Risk

- Circular import: `market_router` imports `processor` from `main.py`. Mitigated by lazy import inside function body (same pattern as `history_router` with `_get_svc()`).

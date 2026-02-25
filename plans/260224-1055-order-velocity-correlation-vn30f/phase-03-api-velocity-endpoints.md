# Phase 3: API Layer — Velocity REST Endpoints & WS Integration

## Context Links

- [market_router.py](../../backend/app/routers/market_router.py) — existing REST pattern
- [history_router.py](../../backend/app/routers/history_router.py) — DB query pattern
- [history_service.py](../../backend/app/database/history_service.py) — asyncpg query pattern
- [data_publisher.py](../../backend/app/websocket/data_publisher.py) — WS broadcast pattern
- [MarketSnapshot model](../../backend/app/models/domain.py) — unified snapshot

## Overview

- **Priority**: P1
- **Status**: complete
- **Effort**: 2h
- **Description**: Add REST endpoints for current velocity data and historical velocity from the continuous aggregate. WebSocket delivery handled automatically via MarketSnapshot extension from Phase 2.

## Key Insights

- Real-time velocity already flows through `MarketSnapshot.velocity` via WS (Phase 2 adds the field)
- Only need REST for: (a) direct polling fallback, (b) historical data from `order_velocity_1m` aggregate
- History endpoint queries `order_velocity_1m` continuous aggregate -- same pattern as `get_candles()`
- No new WS channel needed -- existing `/ws/market` channel carries velocity in MarketSnapshot

## Requirements

### Functional
- `GET /api/market/velocity` -- current real-time VelocitySnapshot (VN30F + basket + correlation)
- `GET /api/market/velocity/history` -- historical velocity from DB aggregate, with `symbol`, `minutes` params
- `GET /api/market/velocity/basket-history` -- historical basket velocity from `vn30_basket_velocity_1m`

### Non-Functional
- Consistent with existing endpoint patterns (market_router.py)
- History queries bounded by `minutes` param (max 480 = full trading day)
- JSON serialization via Pydantic model_dump

## Architecture

```
Frontend
    |
    +---> /ws/market -----> MarketSnapshot { velocity: VelocitySnapshot }  (real-time)
    |
    +---> GET /api/market/velocity              (polling fallback)
    +---> GET /api/market/velocity/history      (per-symbol historical)
    +---> GET /api/market/velocity/basket-history (VN30 basket historical)
              |
              +---> HistoryService.get_velocity_history()
              +---> HistoryService.get_basket_velocity_history()
                        |
                        +---> order_velocity_1m (continuous aggregate)
                        +---> vn30_basket_velocity_1m (view)
```

## Related Code Files

### Files to Modify
- `backend/app/routers/market_router.py` — add 3 new endpoints
- `backend/app/database/history_service.py` — add velocity query methods

### Files to Reference (read-only)
- `backend/app/main.py` — `processor` singleton import pattern
- `backend/app/models/domain.py` — VelocitySnapshot model (from Phase 2)

## Implementation Steps

### Step 1: Add velocity history queries to `history_service.py`

```python
async def get_velocity_history(
    self, symbol: str, minutes: int = 60
) -> list[dict]:
    """Per-symbol velocity from order_velocity_1m aggregate."""
    rows = await self._pool.fetch(
        """
        SELECT timestamp, symbol,
               buy_vol, sell_vol, buy_count, sell_count,
               buy_value, sell_value
        FROM order_velocity_1m
        WHERE symbol = $1
          AND timestamp >= NOW() - make_interval(mins => $2)
        ORDER BY timestamp
        """,
        symbol, minutes,
    )
    return [dict(r) for r in rows]

async def get_basket_velocity_history(
    self, minutes: int = 60
) -> list[dict]:
    """VN30 basket velocity from vn30_basket_velocity_1m view."""
    rows = await self._pool.fetch(
        """
        SELECT timestamp,
               buy_vol, sell_vol, buy_count, sell_count,
               buy_value, sell_value
        FROM vn30_basket_velocity_1m
        WHERE timestamp >= NOW() - make_interval(mins => $1)
        ORDER BY timestamp
        """,
        minutes,
    )
    return [dict(r) for r in rows]
```

### Step 2: Add REST endpoints to `market_router.py`

```python
@router.get("/velocity")
async def get_velocity():
    """Current real-time velocity snapshot (VN30F + basket + correlation)."""
    from app.main import processor
    snapshot = processor.get_market_snapshot()
    return snapshot.velocity

@router.get("/velocity/history")
async def get_velocity_history(
    request: Request,
    symbol: str = Query(..., description="Symbol (e.g., VN30F2603, VPB)"),
    minutes: int = Query(60, ge=1, le=480),
):
    """Per-symbol historical velocity from order_velocity_1m aggregate."""
    from app.main import processor  # noqa: F811 -- lazy import pattern
    svc = _get_svc(request)  # reuse history_service lazy init pattern
    return await svc.get_velocity_history(symbol.upper(), minutes)

@router.get("/velocity/basket-history")
async def get_basket_velocity_history(
    request: Request,
    minutes: int = Query(60, ge=1, le=480),
):
    """VN30 basket historical velocity from vn30_basket_velocity_1m view."""
    svc = _get_svc(request)
    return await svc.get_basket_velocity_history(minutes)
```

**Note**: The `/velocity` endpoint doesn't need DB -- it reads from in-memory VelocityTracker. The history endpoints need DB and follow the `_get_svc(request)` pattern from `history_router.py`. We need to either:
- (a) Import `_get_svc` logic into market_router, or
- (b) Add these history endpoints to `history_router.py` instead

**Decision**: Add a `_get_history_svc(request)` helper directly in `market_router.py` (same pattern, 5 lines). Keeps velocity endpoints together.

### Step 3: Update README API table

Add new endpoints to the API table in `README.md`:

```markdown
| GET | `/api/market/velocity` | Current velocity snapshot |
| GET | `/api/market/velocity/history` | Per-symbol velocity history |
| GET | `/api/market/velocity/basket-history` | VN30 basket velocity history |
```

## Todo List

- [x] Add `get_velocity_history()` to HistoryService
- [x] Add `get_basket_velocity_history()` to HistoryService
- [x] Add `GET /api/market/velocity` to market_router
- [x] Add `GET /api/market/velocity/history` to market_router
- [x] Add `GET /api/market/velocity/basket-history` to market_router
- [x] Add `_get_history_svc()` helper to market_router
- [x] Update README API table
- [x] Test endpoints with curl / httpie
- [x] Verify WS market channel includes velocity data

## Success Criteria

- `GET /api/market/velocity` returns VelocitySnapshot JSON
- `GET /api/market/velocity/history?symbol=VN30F2603&minutes=60` returns array of velocity rows
- `GET /api/market/velocity/basket-history?minutes=60` returns basket aggregation
- WS `/ws/market` messages include `velocity` field
- All existing endpoints unaffected

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| History query slow on large tick_data | Low | Medium | Continuous aggregate pre-computes; query hits materialized view |
| DB unavailable | Medium | Low | `/velocity` endpoint works without DB (in-memory); history returns 503 |
| MarketSnapshot payload size increase | Low | Low | VelocitySnapshot adds ~200 bytes — negligible |

## Security Considerations

- `symbol` param sanitized via `.upper()` + parameterized query ($1)
- `minutes` param bounded by `Query(ge=1, le=480)` — no unbounded queries

## Next Steps

- Phase 4 frontend consumes these endpoints
- `useVelocityData()` hook will poll history + extract real-time from WS

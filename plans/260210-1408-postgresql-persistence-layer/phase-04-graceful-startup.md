# Phase 4: Graceful Startup (DB Optional)

## Overview
- **Priority:** P1
- **Status:** complete
- **Est:** 30 min
- **Depends on:** Phase 1 (pool.py rename + `health_check()`)

App currently crashes if DB is unavailable at startup (`await db.connect()` throws). This phase makes DB connection optional -- real-time streaming works without persistence.

## Key Insights
- `main.py` lifespan calls `db.connect()` without try/except -- `asyncpg.InvalidCatalogNameError` or `ConnectionRefusedError` kills the app
- `batch_writer.start()` creates flush loop that crashes on `self._db.pool.acquire()` if pool is None
- History router asserts `self._db.pool is not None` -- will raise on queries
- Goal: stream data in-memory even without DB; history endpoints return 503

## Related Code Files

**Modify:**
- `backend/app/main.py` — wrap DB connect in try/except, track `db_available` state, update health endpoint
- `backend/app/routers/history_router.py` — guard endpoints when DB unavailable

## Implementation Steps

### Step 1: Update lifespan in main.py
Replace the current DB connect block (lines 78-82):

```python
# 1. Try connecting database pool
db_available = False
try:
    await db.connect()
    db_available = True
    logger.info("Database connected")
except Exception:
    logger.warning("Database unavailable — running without persistence", exc_info=True)

app.state.db_available = db_available

# 2. Start batch writer only if DB is available
if db_available:
    await batch_writer.start()
```

### Step 2: Update shutdown in main.py
Replace shutdown section (after `yield`). Guard DB-dependent cleanup:

```python
# Shutdown (reverse order)
reset_task.cancel()
alert_service.unsubscribe(_on_new_alert)
processor.unsubscribe(publisher.notify)
publisher.stop()
await market_ws_manager.disconnect_all()
await foreign_ws_manager.disconnect_all()
await index_ws_manager.disconnect_all()
await alerts_ws_manager.disconnect_all()
await stream_service.disconnect()
if app.state.db_available:
    await batch_writer.stop()
    await db.disconnect()
```

### Step 3: Update health endpoint
Replace current `/health` endpoint:

```python
@app.get("/health")
async def health():
    db_ok = False
    if getattr(app.state, "db_available", False):
        db_ok = await db.health_check()
    return {
        "status": "ok",
        "database": "connected" if db_ok else "unavailable",
    }
```

Note: Always returns 200 (app is running). `database` field lets monitoring distinguish full vs degraded mode.

### Step 4: Guard history router
Add DB availability check to `_get_svc()` in `backend/app/routers/history_router.py`:

```python
from fastapi import APIRouter, HTTPException, Query, Request

# ... existing code ...

def _get_svc(request: Request) -> HistoryService:
    global _svc
    if not getattr(request.app.state, "db_available", False):
        raise HTTPException(status_code=503, detail="Database unavailable")
    if _svc is None:
        _svc = HistoryService(db)
    return _svc
```

Update all endpoint functions to accept `request: Request` parameter and pass to `_get_svc(request)`:

```python
@router.get("/{symbol}/candles")
async def get_candles(
    request: Request,
    symbol: str,
    start: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end: date = Query(..., description="End date (YYYY-MM-DD)"),
):
    return await _get_svc(request).get_candles(symbol.upper(), start, end)
```

Repeat for all 6 endpoints in history_router.py.

### Step 5: Update .env.example
Append comment:

```
# Database pool (app starts without DB if connection fails)
DB_POOL_MIN=2
DB_POOL_MAX=10
```

(If already added in Phase 1, just add the comment about optional DB.)

## Todo List
- [ ] Wrap `db.connect()` in try/except in lifespan
- [ ] Track `app.state.db_available` flag
- [ ] Conditionally start/stop batch_writer
- [ ] Update `/health` endpoint to report DB status
- [ ] Guard history router with 503 when DB unavailable
- [ ] Add `Request` parameter to all history endpoints
- [ ] Test: app starts without TimescaleDB running
- [ ] Test: `/health` returns `"database": "unavailable"` without DB
- [ ] Test: history endpoints return 503 without DB
- [ ] Test: full flow works when DB is available

## Success Criteria
- App starts and serves real-time WebSocket data even if DB is down
- `/health` returns 200 with `database: "connected"` or `"unavailable"`
- History endpoints return 503 with clear message when DB unavailable
- Batch writer only runs when DB is connected
- Zero data loss for in-memory real-time features when DB is down

## Risk Assessment
- **Batch writer enqueue without flush** — when DB unavailable, `enqueue_*` calls still happen from processor. Queues fill up and drop data silently. Acceptable: data persistence is best-effort when DB is down.
- **DB reconnection** — NOT in scope. If DB comes back after startup, app must restart. Future enhancement: add reconnect loop (YAGNI for now).
- **Health check false positive** — Docker healthcheck hits `/health` which returns 200 even without DB. This is correct: the app IS healthy, just in degraded mode. If strict DB requirement is needed, check `database` field in monitoring.

## Security
- No new credentials or secrets introduced
- 503 response does not leak internal DB connection details

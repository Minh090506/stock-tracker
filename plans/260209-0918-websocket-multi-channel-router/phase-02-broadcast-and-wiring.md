# Phase 2: Broadcast and Wiring

**Priority:** P1
**Status:** Pending
**Effort:** 1h

## Context Links
- Plan: [plan.md](./plan.md)
- Phase 1: [phase-01-router-and-auth.md](./phase-01-router-and-auth.md)
- Broadcast loop: `backend/app/websocket/broadcast_loop.py`
- Main app: `backend/app/main.py`

## Overview
Update broadcast loop to feed 3 ConnectionManagers, wire router to main.py, and delete old endpoint.py.

## Key Insights
- Broadcast loop already optimized for zero-cost idle (skips when no clients)
- Need 3 ConnectionManager instances (one per channel)
- Each channel broadcasts different data type
- Lifespan creates managers and starts single broadcast task

## Requirements

### Functional
- Market channel broadcasts MarketSnapshot
- Foreign channel broadcasts ForeignSummary
- Index channel broadcasts dict[str, IndexData]
- Broadcast loop serializes 3 data types per iteration
- Skip serialization when all channels have zero clients

### Non-Functional
- broadcast_loop.py stays under 200 LOC
- main.py stays under 200 LOC
- No code duplication

## Architecture

### 3 ConnectionManagers
```python
# In app.main
market_ws_manager = ConnectionManager()   # /ws/market
foreign_ws_manager = ConnectionManager()  # /ws/foreign
index_ws_manager = ConnectionManager()    # /ws/index
```

### Updated Broadcast Loop
```python
async def broadcast_loop(processor, market_mgr, foreign_mgr, index_mgr):
    while True:
        await sleep(interval)
        total_clients = market_mgr.client_count + foreign_mgr.client_count + index_mgr.client_count
        if total_clients == 0:
            continue

        # Serialize and broadcast each channel
        if market_mgr.client_count > 0:
            snapshot = processor.get_market_snapshot()
            market_mgr.broadcast(snapshot.model_dump_json())

        if foreign_mgr.client_count > 0:
            foreign = processor.get_foreign_summary()
            foreign_mgr.broadcast(foreign.model_dump_json())

        if index_mgr.client_count > 0:
            indices = processor.index_tracker.get_all()
            index_mgr.broadcast(json.dumps({k: v.model_dump() for k, v in indices.items()}))
```

## Related Code Files

### To Modify
- `backend/app/websocket/broadcast_loop.py` — accept 3 managers, broadcast 3 channels
- `backend/app/main.py` — create 3 managers, register router, start broadcast with 3 managers

### To Delete
- `backend/app/websocket/endpoint.py` — replaced by router.py

### To Keep (no changes)
- `backend/app/websocket/router.py` (created in Phase 1)
- `backend/app/websocket/connection_manager.py`

## Implementation Steps

### 1. Update Broadcast Loop Signature
**File:** `backend/app/websocket/broadcast_loop.py`

**Replace lines 11-31:**
```python
async def broadcast_loop(
    processor,
    market_ws_manager,
    foreign_ws_manager,
    index_ws_manager,
) -> None:
    """Broadcast to 3 WebSocket channels: market, foreign, index.

    Skips serialization for channels with zero clients (zero-cost idle).
    """
    import json

    interval = settings.ws_broadcast_interval
    logger.info("Broadcast loop started (interval=%.1fs)", interval)
    try:
        while True:
            await asyncio.sleep(interval)
            total_clients = (
                market_ws_manager.client_count
                + foreign_ws_manager.client_count
                + index_ws_manager.client_count
            )
            if total_clients == 0:
                continue

            try:
                # Market channel: full MarketSnapshot
                if market_ws_manager.client_count > 0:
                    snapshot = processor.get_market_snapshot()
                    data = snapshot.model_dump_json()
                    market_ws_manager.broadcast(data)

                # Foreign channel: ForeignSummary only
                if foreign_ws_manager.client_count > 0:
                    foreign = processor.get_foreign_summary()
                    data = foreign.model_dump_json()
                    foreign_ws_manager.broadcast(data)

                # Index channel: VN30 + VNINDEX dict
                if index_ws_manager.client_count > 0:
                    indices = processor.index_tracker.get_all()
                    # Serialize dict of IndexData objects
                    data = json.dumps({k: v.model_dump() for k, v in indices.items()})
                    index_ws_manager.broadcast(data)

            except Exception:
                logger.exception("Error in broadcast loop iteration")
    except asyncio.CancelledError:
        logger.info("Broadcast loop stopped")
```

### 2. Create 3 ConnectionManagers in main.py
**File:** `backend/app/main.py`

**Replace line 33:**
```python
# OLD:
ws_manager = ConnectionManager()

# NEW:
market_ws_manager = ConnectionManager()
foreign_ws_manager = ConnectionManager()
index_ws_manager = ConnectionManager()
```

### 3. Update Broadcast Task in Lifespan
**File:** `backend/app/main.py`

**Replace line 76:**
```python
# OLD:
broadcast_task = asyncio.create_task(broadcast_loop(processor, ws_manager))

# NEW:
broadcast_task = asyncio.create_task(
    broadcast_loop(processor, market_ws_manager, foreign_ws_manager, index_ws_manager)
)
```

### 4. Update Shutdown in Lifespan
**File:** `backend/app/main.py`

**Replace lines 82-87:**
```python
# OLD:
broadcast_task.cancel()
try:
    await broadcast_task
except asyncio.CancelledError:
    pass
await ws_manager.disconnect_all()

# NEW:
broadcast_task.cancel()
try:
    await broadcast_task
except asyncio.CancelledError:
    pass
await market_ws_manager.disconnect_all()
await foreign_ws_manager.disconnect_all()
await index_ws_manager.disconnect_all()
```

### 5. Replace Router Import
**File:** `backend/app/main.py`

**Replace line 23:**
```python
# OLD:
from app.websocket.endpoint import router as ws_router

# NEW:
from app.websocket.router import router as ws_router
```

### 6. Delete Old Endpoint
**File:** `backend/app/websocket/endpoint.py`

```bash
rm backend/app/websocket/endpoint.py
```

## Todo List
- [ ] Update broadcast_loop.py signature to accept 3 managers
- [ ] Add market channel broadcast (MarketSnapshot)
- [ ] Add foreign channel broadcast (ForeignSummary)
- [ ] Add index channel broadcast (dict[str, IndexData])
- [ ] Create 3 ConnectionManagers in main.py
- [ ] Update broadcast_loop call in lifespan
- [ ] Update disconnect_all calls in shutdown
- [ ] Replace endpoint import with router import
- [ ] Delete backend/app/websocket/endpoint.py
- [ ] Verify main.py still under 200 LOC
- [ ] Verify broadcast_loop.py still under 200 LOC
- [ ] Run linter

## Success Criteria
- Broadcast loop feeds 3 managers with correct data types
- Router registered in main app
- Old endpoint.py deleted
- All imports resolve correctly
- No syntax errors

## Risk Assessment
**Risk:** Typo in manager variable names causes runtime error
**Mitigation:** Use consistent naming (market_ws_manager, foreign_ws_manager, index_ws_manager)

**Risk:** Forgot to import json module in broadcast_loop
**Mitigation:** Add `import json` at top of function

**Risk:** Index serialization fails if IndexData has non-serializable fields
**Mitigation:** Use Pydantic's model_dump() which handles datetime, etc.

## Security Considerations
None (broadcast loop is internal, no user input)

## Next Steps
Phase 3: Update tests for 3-channel router

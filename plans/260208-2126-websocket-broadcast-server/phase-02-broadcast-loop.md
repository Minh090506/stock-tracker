# Phase 2: Broadcast Loop + Lifespan Integration

## Context Links

- [Phase 1 — ConnectionManager](phase-01-connection-manager.md)
- [main.py](../../backend/app/main.py) — lifespan events, service singletons
- [MarketDataProcessor](../../backend/app/services/market_data_processor.py) — `get_market_snapshot()`
- [MarketSnapshot](../../backend/app/models/domain.py) — Pydantic v2, `.model_dump_json()` for serialization

## Overview

- **Priority:** P1
- **Status:** complete
- **Description:** Background task that calls `processor.get_market_snapshot()` every 1s, serializes to JSON, and calls `ws_manager.broadcast()`. Wire into FastAPI lifespan.

## Key Insights

- `MarketSnapshot.model_dump_json()` returns a JSON string — no intermediate dict needed
- Broadcast loop runs as `asyncio.Task` created in lifespan startup, cancelled in shutdown
- Loop skips broadcast when `ws_manager.client_count == 0` (no wasted serialization)
- The processor singleton and ws_manager singleton both live in `main.py` — broadcast loop just references them
- Broadcast function is sync (pushes to queues) — no await needed, keeps loop tight

## Requirements

### Functional
- Background task runs every `settings.ws_broadcast_interval` seconds (default 1s)
- Each cycle: get snapshot, serialize to JSON, broadcast to all connected clients
- Skip serialization + broadcast when no clients connected
- Start on app startup, stop on app shutdown
- Graceful cancellation — no errors logged on shutdown

### Non-Functional
- Broadcast loop must not block the event loop (all operations are non-blocking)
- Serialization cost: `model_dump_json()` on MarketSnapshot is ~1-2ms for 30 stocks — acceptable at 1Hz

## Architecture

```
lifespan startup
    ├── ... existing services ...
    ├── create ws_manager (ConnectionManager)
    └── start _broadcast_loop task

_broadcast_loop (asyncio.Task)
    └── every 1s:
        ├── if client_count == 0 → skip
        ├── snapshot = processor.get_market_snapshot()
        ├── json_str = snapshot.model_dump_json()
        └── ws_manager.broadcast(json_str)

lifespan shutdown
    ├── cancel broadcast_loop task
    ├── ws_manager.disconnect_all()
    └── ... existing shutdown ...
```

## Related Code Files

### Files to Create
- `backend/app/websocket/broadcast_loop.py` — broadcast coroutine (~40 lines)

### Files to Modify
- `backend/app/main.py` — add `ws_manager` singleton, start/stop broadcast loop, register WS router

## Implementation Steps

### Step 1: Create broadcast loop module

Create `backend/app/websocket/broadcast_loop.py`:

```python
"""Background task that broadcasts MarketSnapshot to all WebSocket clients."""

import asyncio
import logging

from app.config import settings

logger = logging.getLogger(__name__)


async def broadcast_loop(processor, ws_manager) -> None:
    """Periodically serialize snapshot and push to all WS clients.

    Args:
        processor: MarketDataProcessor instance
        ws_manager: ConnectionManager instance
    """
    interval = settings.ws_broadcast_interval
    logger.info("Broadcast loop started (interval=%.1fs)", interval)
    try:
        while True:
            await asyncio.sleep(interval)
            if ws_manager.client_count == 0:
                continue
            try:
                snapshot = processor.get_market_snapshot()
                data = snapshot.model_dump_json()
                ws_manager.broadcast(data)
            except Exception:
                logger.exception("Error in broadcast loop iteration")
    except asyncio.CancelledError:
        logger.info("Broadcast loop stopped")
```

### Step 2: Modify main.py — add ws_manager + broadcast integration

Changes to `backend/app/main.py`:

**A. Add imports (top of file):**

```python
from app.websocket import ConnectionManager
from app.websocket.broadcast_loop import broadcast_loop
from app.websocket.endpoint import router as ws_router
```

**B. Add ws_manager singleton (after existing singletons, line ~28):**

```python
ws_manager = ConnectionManager()
```

**C. Modify lifespan — start broadcast after stream connects (after line 68):**

```python
    # 7. Start WebSocket broadcast loop
    broadcast_task = asyncio.create_task(broadcast_loop(processor, ws_manager))
    logger.info("WebSocket broadcast loop started")

    yield

    # Shutdown (reverse order)
    broadcast_task.cancel()
    try:
        await broadcast_task
    except asyncio.CancelledError:
        pass
    await ws_manager.disconnect_all()
```

**D. Register WS router (after existing router registrations, line ~92):**

```python
app.include_router(ws_router)
```

### Step 3: Full main.py after changes (for reference)

The resulting `main.py` should look like this (key sections):

```python
import asyncio  # ADD
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

from app.database.connection import db
from app.database.batch_writer import BatchWriter
from app.routers.history_router import router as history_router
from app.routers.market_router import router as market_router
from app.services.futures_resolver import get_futures_symbols
from app.services.ssi_auth_service import SSIAuthService
from app.services.ssi_market_service import SSIMarketService
from app.services.market_data_processor import MarketDataProcessor
from app.services.ssi_stream_service import SSIStreamService
from app.websocket import ConnectionManager                  # ADD
from app.websocket.broadcast_loop import broadcast_loop      # ADD
from app.websocket.endpoint import router as ws_router       # ADD

logger = logging.getLogger(__name__)

# Service singletons
auth_service = SSIAuthService()
market_service = SSIMarketService(auth_service)
stream_service = SSIStreamService(auth_service, market_service)
processor = MarketDataProcessor()
batch_writer = BatchWriter(db)
ws_manager = ConnectionManager()  # ADD

vn30_symbols: list[str] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    global vn30_symbols

    # 1-6. ... existing startup unchanged ...

    # 7. Start WebSocket broadcast loop
    broadcast_task = asyncio.create_task(broadcast_loop(processor, ws_manager))
    logger.info("WebSocket broadcast loop started")

    yield

    # Shutdown (reverse order)
    broadcast_task.cancel()
    try:
        await broadcast_task
    except asyncio.CancelledError:
        pass
    await ws_manager.disconnect_all()
    await stream_service.disconnect()
    await batch_writer.stop()
    await db.disconnect()


# ... app creation unchanged ...

app.include_router(history_router)
app.include_router(market_router)
app.include_router(ws_router)  # ADD

# ... health + vn30 endpoints unchanged ...
```

## Todo List

- [ ] Create `backend/app/websocket/broadcast_loop.py`
- [ ] Add `import asyncio` to `main.py` (if not already present)
- [ ] Add `ws_manager = ConnectionManager()` singleton to `main.py`
- [ ] Add `broadcast_loop` start in lifespan startup
- [ ] Add `broadcast_task.cancel()` + `ws_manager.disconnect_all()` in lifespan shutdown
- [ ] Register `ws_router` in app
- [ ] Verify startup — `./venv/bin/python -c "from app.websocket.broadcast_loop import broadcast_loop"`

## Success Criteria

1. Broadcast loop starts on app startup, logs interval
2. Loop skips when no clients connected (verified via log or debug)
3. Connected WS clients receive JSON-serialized `MarketSnapshot` every ~1s
4. Loop stops cleanly on shutdown — no error logs
5. `disconnect_all()` called before DB/stream shutdown
6. `broadcast_loop.py` under 40 lines, `main.py` stays under 120 lines

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Broadcast loop exception kills the task | Inner try/except per iteration; only `CancelledError` exits |
| `model_dump_json()` slow for large snapshot | ~1-2ms for 30 stocks at 1Hz is fine; monitor if VN30 expands |
| Shutdown order: clients receive errors | Cancel broadcast first, then disconnect clients, then stop services |
| Memory: large JSON string held briefly | GC collects after broadcast; one string shared across all queue puts (Python refcount) |

## Security Considerations

- No new attack surface beyond Phase 1 endpoint
- Broadcast loop only reads from processor (no write ops)

## Next Steps

- Phase 3: Write tests for ConnectionManager and WebSocket endpoint

# Phase 1: ConnectionManager + WebSocket Endpoint

## Context Links

- [MarketDataProcessor](../../backend/app/services/market_data_processor.py) — `get_market_snapshot()` returns `MarketSnapshot`
- [Domain models](../../backend/app/models/domain.py) — `MarketSnapshot`, all Pydantic v2, `.model_dump_json()` ready
- [Existing WS package](../../backend/app/websocket/__init__.py) — empty, ready for code
- [main.py](../../backend/app/main.py) — lifespan + route registration
- [config.py](../../backend/app/config.py) — Settings class for new config fields

## Overview

- **Priority:** P1
- **Status:** complete
- **Description:** Implement `ConnectionManager` class for WebSocket client lifecycle and a `/ws/market` FastAPI endpoint.

## Key Insights

- `MarketSnapshot.model_dump_json()` produces JSON string directly — no need for manual serialization
- FastAPI WebSocket accepts via `websocket.accept()`, then we add client to manager
- Per-client `asyncio.Queue(maxsize=50)` decouples broadcast from per-client send speed
- When queue is full, drop oldest message (call `queue.get_nowait()` before `put_nowait()`)
- Heartbeat: server sends `ping` frame every 30s; if no `pong` within 10s, disconnect

## Requirements

### Functional
- Accept WebSocket connections at `/ws/market`
- Maintain set of active connections with per-client queues
- Provide `broadcast(data: str)` method to push JSON to all client queues
- Send queued messages to each client via dedicated sender task
- App-level ping/pong heartbeat (30s interval, 10s timeout)
- Graceful disconnect on client close, error, or pong timeout

### Non-Functional
- Thread-safe for asyncio (single event loop, no threading concerns)
- O(1) connect/disconnect via dict keyed by WebSocket instance
- Zero impact on broadcast loop if one client is slow (queue overflow drops oldest)

## Architecture

```
ConnectionManager
├── _clients: dict[WebSocket, asyncio.Queue[str]]
├── connect(ws) → adds client + starts sender task
├── disconnect(ws) → removes client, cancels sender task
├── broadcast(data: str) → pushes to all queues
└── _sender(ws, queue) → loop: get from queue, send to ws

WebSocket Endpoint /ws/market
├── accept connection
├── manager.connect(ws)
├── receive loop (reads pong frames, detects disconnect)
└── finally: manager.disconnect(ws)
```

## Related Code Files

### Files to Create
- `backend/app/websocket/connection_manager.py` — ConnectionManager class (~80 lines)
- `backend/app/websocket/endpoint.py` — WebSocket route + endpoint function (~50 lines)

### Files to Modify
- `backend/app/websocket/__init__.py` — export ConnectionManager
- `backend/app/config.py` — add `ws_broadcast_interval`, `ws_heartbeat_interval`, `ws_heartbeat_timeout`, `ws_queue_size` settings

## Implementation Steps

### Step 1: Add WebSocket config to Settings

In `backend/app/config.py`, add these fields to the `Settings` class:

```python
# WebSocket
ws_broadcast_interval: float = 1.0    # seconds between broadcasts
ws_heartbeat_interval: float = 30.0   # seconds between ping frames
ws_heartbeat_timeout: float = 10.0    # seconds to wait for pong
ws_queue_size: int = 50               # per-client queue maxsize
```

### Step 2: Create ConnectionManager

Create `backend/app/websocket/connection_manager.py`:

```python
"""Manages WebSocket clients with per-client async queues."""

import asyncio
import logging
import time

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.config import settings

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket client connections and message broadcasting."""

    def __init__(self):
        # WebSocket → (queue, sender_task)
        self._clients: dict[WebSocket, tuple[asyncio.Queue[str], asyncio.Task]] = {}

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def connect(self, ws: WebSocket):
        """Accept WS connection, create queue + sender task."""
        await ws.accept()
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=settings.ws_queue_size)
        task = asyncio.create_task(self._sender(ws, queue))
        self._clients[ws] = (queue, task)
        logger.info("WS client connected (%d total)", self.client_count)

    async def disconnect(self, ws: WebSocket):
        """Remove client, cancel sender task, close socket."""
        entry = self._clients.pop(ws, None)
        if entry is None:
            return
        _, task = entry
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        if ws.client_state == WebSocketState.CONNECTED:
            try:
                await ws.close()
            except Exception:
                pass
        logger.info("WS client disconnected (%d remaining)", self.client_count)

    def broadcast(self, data: str):
        """Push JSON string to all client queues. Drop oldest on overflow."""
        for ws, (queue, _) in self._clients.items():
            if queue.full():
                try:
                    queue.get_nowait()  # drop oldest
                except asyncio.QueueEmpty:
                    pass
            try:
                queue.put_nowait(data)
            except asyncio.QueueFull:
                pass  # safety fallback

    async def disconnect_all(self):
        """Disconnect all clients. Called on shutdown."""
        clients = list(self._clients.keys())
        for ws in clients:
            await self.disconnect(ws)

    async def _sender(self, ws: WebSocket, queue: asyncio.Queue[str]):
        """Per-client loop: pull from queue, send over WS."""
        try:
            while True:
                data = await queue.get()
                await ws.send_text(data)
        except (WebSocketDisconnect, RuntimeError, asyncio.CancelledError):
            pass
        except Exception:
            logger.exception("Unexpected error in WS sender")
```

### Step 3: Create WebSocket Endpoint

Create `backend/app/websocket/endpoint.py`:

```python
"""WebSocket endpoint for real-time market data broadcast."""

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


async def _heartbeat(ws: WebSocket):
    """Send ping frames at interval. Disconnect on pong timeout."""
    try:
        while True:
            await asyncio.sleep(settings.ws_heartbeat_interval)
            try:
                await asyncio.wait_for(
                    ws.send_bytes(b"ping"),
                    timeout=settings.ws_heartbeat_timeout,
                )
            except (asyncio.TimeoutError, Exception):
                logger.info("Heartbeat timeout, closing WS")
                return
    except asyncio.CancelledError:
        pass


@router.websocket("/ws/market")
async def market_websocket(ws: WebSocket):
    """Accept WS connection and keep alive until client disconnects."""
    from app.main import ws_manager

    await ws_manager.connect(ws)
    heartbeat_task = asyncio.create_task(_heartbeat(ws))
    try:
        while True:
            # Read loop — keeps connection alive, detects client disconnect
            await ws.receive_text()
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        await ws_manager.disconnect(ws)
```

### Step 4: Update `__init__.py`

Update `backend/app/websocket/__init__.py`:

```python
from app.websocket.connection_manager import ConnectionManager

__all__ = ["ConnectionManager"]
```

## Todo List

- [ ] Add WS config fields to `backend/app/config.py`
- [ ] Create `backend/app/websocket/connection_manager.py`
- [ ] Create `backend/app/websocket/endpoint.py`
- [ ] Update `backend/app/websocket/__init__.py` with exports
- [ ] Verify syntax — run `./venv/bin/python -c "from app.websocket import ConnectionManager"`

## Success Criteria

1. `ConnectionManager` can be imported with no errors
2. `connect()` accepts a WebSocket and creates queue + sender task
3. `broadcast()` pushes to all client queues; drops oldest when full
4. `disconnect()` cleans up client, cancels task, closes socket
5. `/ws/market` endpoint registered and accessible
6. Heartbeat pings sent at configured interval
7. All files under 200 lines

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Sender task exception leaks | Wrapped in try/except, logs unexpected errors |
| Queue overflow on slow client | `get_nowait()` drops oldest before `put_nowait()` |
| WebSocket close race condition | Check `client_state` before closing; catch exceptions |
| Circular import (endpoint imports from main) | Use lazy import pattern (same as `market_router.py`) |

## Security Considerations

- No authentication on `/ws/market` yet — acceptable for Phase 4 MVP, add auth in future phase
- CORS handled at HTTP middleware level; WebSocket origin not checked (browser enforces same-origin)
- Queue maxsize bounds memory per client (50 messages * ~50KB each = ~2.5MB max per client)

## Next Steps

- Phase 2: broadcast loop background task + lifespan integration in `main.py`

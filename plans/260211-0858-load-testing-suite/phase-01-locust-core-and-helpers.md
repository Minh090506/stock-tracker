# Phase 1: Locust Core + Helpers

## Context Links

- [System Architecture](/Users/minh/Projects/stock-tracker/docs/system-architecture.md)
- [WebSocket Router](/Users/minh/Projects/stock-tracker/backend/app/websocket/router.py) — rate limiter, auth
- [Config](/Users/minh/Projects/stock-tracker/backend/app/config.py) — `WS_MAX_CONNECTIONS_PER_IP=5`
- [ConnectionManager](/Users/minh/Projects/stock-tracker/backend/app/websocket/connection_manager.py) — per-client queues

## Overview

- **Priority**: P1
- **Status**: pending
- **Effort**: 1.5h

Set up Locust framework, WebSocket client helper, and the main locustfile that composes all scenarios.

## Key Insights

1. **Rate limit bypass**: Set env `WS_MAX_CONNECTIONS_PER_IP=0` (disable) or a high value (e.g., 10000) when running load tests. The `RateLimiter` in `router.py` checks `settings.ws_max_connections_per_ip` — set via env var.
2. **WS auth**: If `WS_AUTH_TOKEN` is set, all WS clients must include `?token=xxx`. For load tests, either disable auth (empty token) or pass a shared token.
3. **Single worker**: FastAPI runs single-process with in-memory state. No need for distributed locking.
4. **Locust WS support**: Locust has no native WebSocket user. We need a custom `WebSocketUser` base class using the `websockets` library (already a dependency).

## Requirements

### Functional
- WebSocket user base class with connect/receive/disconnect lifecycle
- Latency measurement for each WS message received
- REST user using Locust's built-in `HttpUser`
- Configurable target host, WS token, concurrency via env vars

### Non-functional
- All files < 200 LOC
- Python snake_case naming
- Compatible with Locust 2.x headless and web UI modes

## Architecture

```
backend/tests/load/
├── __init__.py
├── locustfile.py                    # Main entry: imports + composes users
├── websocket_user.py                # WebSocket base class (connect, receive, measure)
├── rest_user.py                     # REST scenario user
└── scenarios/
    ├── __init__.py
    ├── market_stream.py             # WS /ws/market subscribe + measure msg/sec
    ├── foreign_flow.py              # REST polling /api/market/foreign-detail
    ├── burst_test.py                # Market-open spike simulation
    └── reconnect_storm.py           # Disconnect/reconnect stress test
```

## Related Code Files

### Files to Create

| File | Purpose | LOC est. |
|------|---------|----------|
| `backend/tests/load/__init__.py` | Package marker | 1 |
| `backend/tests/load/websocket_user.py` | WS base class with latency tracking | ~90 |
| `backend/tests/load/rest_user.py` | REST scenario HttpUser | ~60 |
| `backend/tests/load/locustfile.py` | Main entry combining all users | ~50 |
| `backend/tests/load/scenarios/__init__.py` | Package marker | 1 |

### Files to Modify

| File | Change |
|------|--------|
| `backend/requirements-dev.txt` | Add `locust>=2.32`, `websockets>=14.0` |

## Implementation Steps

### Step 1: Add locust dependency

In `backend/requirements-dev.txt`, append:
```
locust>=2.32
```

(`websockets` already in `requirements.txt`)

### Step 2: Create `backend/tests/load/__init__.py`

Empty file.

### Step 3: Create `backend/tests/load/websocket_user.py`

Custom Locust User base class:

```python
"""Base Locust user for WebSocket load testing.

Connects to a FastAPI WS endpoint, receives JSON messages,
and reports latency/throughput to Locust's event system.
"""

import asyncio
import json
import os
import time
import logging
from contextlib import suppress

import websockets
from locust import User, events

logger = logging.getLogger(__name__)

WS_TOKEN = os.getenv("WS_AUTH_TOKEN", "")


class WebSocketUser(User):
    """Base class for WebSocket load test users.

    Subclasses set `ws_path` (e.g., "/ws/market") and override
    `on_message(data: dict)` for custom assertions.
    """
    abstract = True
    ws_path: str = "/ws/market"

    def __init__(self, environment):
        super().__init__(environment)
        self._ws = None
        self._loop = None
        self._task = None

    def on_start(self):
        self._loop = asyncio.new_event_loop()
        self._loop.run_until_complete(self._connect())

    def on_stop(self):
        if self._ws:
            self._loop.run_until_complete(self._disconnect())
        if self._loop:
            self._loop.close()

    async def _connect(self):
        host = self.environment.host.replace("http://", "ws://").replace("https://", "wss://")
        url = f"{host}{self.ws_path}"
        if WS_TOKEN:
            url += f"?token={WS_TOKEN}"

        start = time.monotonic()
        try:
            self._ws = await websockets.connect(url)
            elapsed_ms = (time.monotonic() - start) * 1000
            events.request.fire(
                request_type="WS",
                name=f"connect {self.ws_path}",
                response_time=elapsed_ms,
                response_length=0,
                exception=None,
                context={},
            )
        except Exception as e:
            elapsed_ms = (time.monotonic() - start) * 1000
            events.request.fire(
                request_type="WS",
                name=f"connect {self.ws_path}",
                response_time=elapsed_ms,
                response_length=0,
                exception=e,
                context={},
            )

    async def _disconnect(self):
        with suppress(Exception):
            await self._ws.close()

    async def receive_one(self) -> dict | None:
        """Receive one WS message, report latency to Locust."""
        start = time.monotonic()
        try:
            raw = await asyncio.wait_for(self._ws.recv(), timeout=10.0)
            elapsed_ms = (time.monotonic() - start) * 1000
            data = json.loads(raw) if isinstance(raw, str) else {}
            events.request.fire(
                request_type="WS",
                name=f"recv {self.ws_path}",
                response_time=elapsed_ms,
                response_length=len(raw),
                exception=None,
                context={},
            )
            return data
        except Exception as e:
            elapsed_ms = (time.monotonic() - start) * 1000
            events.request.fire(
                request_type="WS",
                name=f"recv {self.ws_path}",
                response_time=elapsed_ms,
                response_length=0,
                exception=e,
                context={},
            )
            return None

    def on_message(self, data: dict):
        """Override in subclass for custom validation."""
        pass
```

### Step 4: Create `backend/tests/load/rest_user.py`

```python
"""REST load test user — hits market endpoints with configurable weights."""

from locust import HttpUser, task, between


class RestUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task(5)
    def snapshot(self):
        self.client.get("/api/market/snapshot", name="/api/market/snapshot")

    @task(3)
    def foreign_detail(self):
        self.client.get("/api/market/foreign-detail", name="/api/market/foreign-detail")

    @task(2)
    def vn30_components(self):
        self.client.get("/api/vn30-components", name="/api/vn30-components")

    @task(1)
    def alerts(self):
        self.client.get("/api/market/alerts?limit=50", name="/api/market/alerts")
```

### Step 5: Create `backend/tests/load/locustfile.py`

```python
"""Main locustfile — imports all users for Locust discovery.

Run: locust -f backend/tests/load/locustfile.py --host http://localhost:8000
"""

# Locust auto-discovers User subclasses from imports
from backend.tests.load.rest_user import RestUser  # noqa: F401
from backend.tests.load.scenarios.market_stream import MarketStreamUser  # noqa: F401
from backend.tests.load.scenarios.foreign_flow import ForeignFlowUser  # noqa: F401
from backend.tests.load.scenarios.burst_test import BurstUser  # noqa: F401
from backend.tests.load.scenarios.reconnect_storm import ReconnectUser  # noqa: F401
```

**Note**: For headless run, select specific user classes via `--class-picker` or `-u`.

## Todo List

- [ ] Add `locust>=2.32` to `backend/requirements-dev.txt`
- [ ] Create `backend/tests/load/__init__.py`
- [ ] Create `backend/tests/load/websocket_user.py` (~90 LOC)
- [ ] Create `backend/tests/load/rest_user.py` (~30 LOC)
- [ ] Create `backend/tests/load/locustfile.py` (~15 LOC)
- [ ] Create `backend/tests/load/scenarios/__init__.py`
- [ ] Verify `locust --help` works after install

## Success Criteria

- `locust -f backend/tests/load/locustfile.py --host http://localhost:8000 --headless -u 10 -r 2 -t 30s` runs without import errors
- WS connect/receive events appear in Locust stats
- REST endpoints show response times in stats

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| WS library version mismatch | Medium | Pin `websockets>=14.0` (already in requirements.txt) |
| Locust event API changes | Low | Locust 2.x event API stable since 2.0 |
| asyncio loop in Locust thread | Medium | Each user creates own loop in `on_start` |

## Security Considerations

- Load test token passed via env var, never hardcoded
- Rate limit must be explicitly raised (env var) for load tests

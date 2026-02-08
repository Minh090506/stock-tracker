# Phase 3: Tests

## Context Links

- [Phase 1 — ConnectionManager + Endpoint](phase-01-connection-manager.md)
- [Phase 2 — Broadcast Loop](phase-02-broadcast-loop.md)
- [Existing test patterns](../../backend/tests/test_market_data_processor.py) — pytest + pytest-asyncio, class-grouped, fixtures
- [Domain models](../../backend/app/models/domain.py) — `MarketSnapshot` for test data

## Overview

- **Priority:** P1
- **Status:** complete
- **Description:** Unit tests for ConnectionManager and integration test for the `/ws/market` WebSocket endpoint using FastAPI TestClient.

## Key Insights

- FastAPI's `TestClient` supports WebSocket testing via `with client.websocket_connect("/ws/market"):`
- ConnectionManager can be tested in isolation with mock WebSocket objects
- Broadcast loop can be tested by running a few iterations then cancelling
- Existing tests use `pytest.mark.asyncio` — follow same pattern
- No conftest.py exists yet; may need one for shared fixtures if test files share setup

## Requirements

### Test Coverage Targets
- ConnectionManager: connect, disconnect, broadcast, queue overflow, disconnect_all
- WebSocket endpoint: connect receives data, multiple clients, client disconnect cleanup
- Broadcast loop: sends snapshot at interval, skips when no clients

## Related Code Files

### Files to Create
- `backend/tests/test_connection_manager.py` — unit tests for ConnectionManager (~120 lines)
- `backend/tests/test_websocket_endpoint.py` — integration tests for `/ws/market` (~100 lines)

### Dependencies to Verify
- `pytest-asyncio` — needed for async tests (check if in requirements or dev requirements)
- `httpx` — already in requirements.txt, used by FastAPI TestClient

## Implementation Steps

### Step 1: Verify test dependencies

Check/add to a dev requirements file or run:
```bash
./venv/bin/pip install pytest pytest-asyncio
```

### Step 2: Create ConnectionManager unit tests

Create `backend/tests/test_connection_manager.py`:

```python
"""Tests for WebSocket ConnectionManager."""

import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from starlette.websockets import WebSocketState

from app.websocket.connection_manager import ConnectionManager


@pytest.fixture
def manager():
    return ConnectionManager()


def _mock_ws():
    """Create a mock WebSocket with accept/send/close/receive."""
    ws = AsyncMock()
    ws.client_state = WebSocketState.CONNECTED
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    ws.close = AsyncMock()
    return ws


class TestConnect:
    @pytest.mark.asyncio
    async def test_connect_accepts_and_tracks(self, manager):
        ws = _mock_ws()
        await manager.connect(ws)
        assert manager.client_count == 1
        ws.accept.assert_awaited_once()
        # Cleanup
        await manager.disconnect_all()

    @pytest.mark.asyncio
    async def test_multiple_connects(self, manager):
        ws1, ws2 = _mock_ws(), _mock_ws()
        await manager.connect(ws1)
        await manager.connect(ws2)
        assert manager.client_count == 2
        await manager.disconnect_all()


class TestDisconnect:
    @pytest.mark.asyncio
    async def test_disconnect_removes_client(self, manager):
        ws = _mock_ws()
        await manager.connect(ws)
        await manager.disconnect(ws)
        assert manager.client_count == 0

    @pytest.mark.asyncio
    async def test_disconnect_idempotent(self, manager):
        ws = _mock_ws()
        await manager.connect(ws)
        await manager.disconnect(ws)
        await manager.disconnect(ws)  # no error
        assert manager.client_count == 0

    @pytest.mark.asyncio
    async def test_disconnect_closes_socket(self, manager):
        ws = _mock_ws()
        await manager.connect(ws)
        await manager.disconnect(ws)
        ws.close.assert_awaited_once()


class TestBroadcast:
    @pytest.mark.asyncio
    async def test_broadcast_queues_data(self, manager):
        ws = _mock_ws()
        await manager.connect(ws)
        manager.broadcast('{"test": true}')
        # Give sender task time to process
        await asyncio.sleep(0.05)
        ws.send_text.assert_awaited_with('{"test": true}')
        await manager.disconnect_all()

    @pytest.mark.asyncio
    async def test_broadcast_multiple_clients(self, manager):
        ws1, ws2 = _mock_ws(), _mock_ws()
        await manager.connect(ws1)
        await manager.connect(ws2)
        manager.broadcast('{"data": 1}')
        await asyncio.sleep(0.05)
        ws1.send_text.assert_awaited()
        ws2.send_text.assert_awaited()
        await manager.disconnect_all()

    @pytest.mark.asyncio
    async def test_broadcast_drops_oldest_on_full_queue(self, manager):
        """When queue is full, oldest message is dropped."""
        with patch("app.websocket.connection_manager.settings") as mock_settings:
            mock_settings.ws_queue_size = 2
            mock_settings.ws_heartbeat_interval = 30.0
            mock_settings.ws_heartbeat_timeout = 10.0

            ws = _mock_ws()
            # Make send_text block so queue fills up
            ws.send_text = AsyncMock(side_effect=asyncio.Event().wait)
            mgr = ConnectionManager()
            await mgr.connect(ws)

            # Fill queue beyond capacity
            mgr.broadcast("msg1")
            mgr.broadcast("msg2")
            mgr.broadcast("msg3")  # should drop msg1

            # Verify no exception raised
            assert mgr.client_count == 1
            await mgr.disconnect_all()


class TestDisconnectAll:
    @pytest.mark.asyncio
    async def test_disconnect_all_clears(self, manager):
        for _ in range(5):
            await manager.connect(_mock_ws())
        assert manager.client_count == 5
        await manager.disconnect_all()
        assert manager.client_count == 0
```

### Step 3: Create WebSocket endpoint integration tests

Create `backend/tests/test_websocket_endpoint.py`:

```python
"""Integration tests for /ws/market WebSocket endpoint."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.models.domain import MarketSnapshot
from app.websocket.connection_manager import ConnectionManager


@pytest.fixture
def test_app():
    """Create a minimal FastAPI app with WS endpoint for testing."""
    from fastapi import FastAPI
    from app.websocket.endpoint import router

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def ws_manager():
    return ConnectionManager()


@pytest.fixture
def mock_snapshot():
    """Minimal MarketSnapshot for testing."""
    return MarketSnapshot(quotes={}, indices={}, foreign=None, derivatives=None)


class TestWebSocketEndpoint:
    def test_connect_and_receive(self, test_app, ws_manager, mock_snapshot):
        """Client connects and receives broadcast data."""
        with patch("app.websocket.endpoint.ws_manager", ws_manager, create=True):
            # Patch the lazy import in endpoint
            with patch("app.main.ws_manager", ws_manager, create=True):
                client = TestClient(test_app)
                with client.websocket_connect("/ws/market") as ws:
                    # Simulate broadcast
                    data = mock_snapshot.model_dump_json()
                    ws_manager.broadcast(data)
                    msg = ws.receive_text()
                    parsed = json.loads(msg)
                    assert "quotes" in parsed
                    assert "indices" in parsed

    def test_multiple_clients(self, test_app, ws_manager, mock_snapshot):
        """Multiple clients all receive the same broadcast."""
        with patch("app.main.ws_manager", ws_manager, create=True):
            client = TestClient(test_app)
            # TestClient is synchronous, so test sequentially
            with client.websocket_connect("/ws/market") as ws1:
                data = mock_snapshot.model_dump_json()
                ws_manager.broadcast(data)
                msg = ws1.receive_text()
                assert json.loads(msg)["quotes"] == {}


class TestBroadcastLoop:
    @pytest.mark.asyncio
    async def test_loop_sends_snapshot(self, ws_manager, mock_snapshot):
        """Broadcast loop calls get_market_snapshot and broadcasts."""
        from app.websocket.broadcast_loop import broadcast_loop

        mock_processor = MagicMock()
        mock_processor.get_market_snapshot.return_value = mock_snapshot

        # Simulate 1 connected client
        ws = MagicMock()
        queue = asyncio.Queue(maxsize=50)
        task = asyncio.create_task(asyncio.sleep(999))  # dummy sender
        ws_manager._clients[ws] = (queue, task)

        with patch("app.websocket.broadcast_loop.settings") as mock_settings:
            mock_settings.ws_broadcast_interval = 0.05  # fast for test

            loop_task = asyncio.create_task(
                broadcast_loop(mock_processor, ws_manager)
            )
            await asyncio.sleep(0.15)  # ~3 iterations
            loop_task.cancel()
            try:
                await loop_task
            except asyncio.CancelledError:
                pass

        assert mock_processor.get_market_snapshot.call_count >= 2
        assert not queue.empty()
        task.cancel()

    @pytest.mark.asyncio
    async def test_loop_skips_when_no_clients(self):
        """No serialization when client_count == 0."""
        from app.websocket.broadcast_loop import broadcast_loop

        mock_processor = MagicMock()
        mgr = ConnectionManager()

        with patch("app.websocket.broadcast_loop.settings") as mock_settings:
            mock_settings.ws_broadcast_interval = 0.05

            loop_task = asyncio.create_task(
                broadcast_loop(mock_processor, mgr)
            )
            await asyncio.sleep(0.15)
            loop_task.cancel()
            try:
                await loop_task
            except asyncio.CancelledError:
                pass

        mock_processor.get_market_snapshot.assert_not_called()
```

## Todo List

- [ ] Verify `pytest-asyncio` installed in backend venv
- [ ] Create `backend/tests/test_connection_manager.py`
- [ ] Create `backend/tests/test_websocket_endpoint.py`
- [ ] Run tests: `./venv/bin/pytest tests/test_connection_manager.py tests/test_websocket_endpoint.py -v`
- [ ] Verify all tests pass
- [ ] Run full test suite to ensure no regressions: `./venv/bin/pytest -v`

## Success Criteria

1. All ConnectionManager unit tests pass (connect, disconnect, broadcast, overflow, disconnect_all)
2. WebSocket endpoint integration tests pass (connect + receive, multiple clients)
3. Broadcast loop tests pass (sends data, skips when no clients)
4. Full test suite still passes (no regressions)
5. Test files under 200 lines each

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| TestClient WS behavior differs from real | Keep integration tests simple; supplement with manual testing |
| Mock WebSocket may not match real Starlette WS | Use `starlette.websockets.WebSocketState` enum for accuracy |
| Async test timing flakiness | Use generous sleep margins in CI; keep intervals short in tests |
| Patching lazy imports tricky | Match exact import path used in endpoint.py (`from app.main import ws_manager`) |

## Security Considerations

- Tests use mock data only — no real SSI credentials or market data
- No network calls in tests

## Next Steps

- After all 3 phases complete: manual integration test with running backend + frontend
- Future: add auth to WebSocket endpoint, add reconnection logic on frontend

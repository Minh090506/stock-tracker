"""Tests for WebSocket ConnectionManager."""

import asyncio

import pytest
from unittest.mock import AsyncMock, patch
from starlette.websockets import WebSocketState

from app.websocket.connection_manager import ConnectionManager


@pytest.fixture
def manager():
    return ConnectionManager()


def _mock_ws():
    """Create a mock WebSocket with accept/send/close."""
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

    @pytest.mark.asyncio
    async def test_disconnect_skips_close_if_already_disconnected(self, manager):
        ws = _mock_ws()
        ws.client_state = WebSocketState.DISCONNECTED
        await manager.connect(ws)
        await manager.disconnect(ws)
        ws.close.assert_not_awaited()


class TestBroadcast:
    @pytest.mark.asyncio
    async def test_broadcast_queues_data(self, manager):
        ws = _mock_ws()
        await manager.connect(ws)
        manager.broadcast('{"test": true}')
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
    async def test_broadcast_no_clients_no_error(self, manager):
        """Broadcasting with no clients should not raise."""
        manager.broadcast('{"data": 1}')

    @pytest.mark.asyncio
    async def test_broadcast_drops_oldest_on_full_queue(self):
        """When queue is full, oldest message is dropped."""
        with patch("app.websocket.connection_manager.settings") as mock_settings:
            mock_settings.ws_queue_size = 2
            mgr = ConnectionManager()
            ws = _mock_ws()
            # Block sender so queue fills up
            ws.send_text = AsyncMock(side_effect=asyncio.Event().wait)
            await mgr.connect(ws)

            mgr.broadcast("msg1")
            mgr.broadcast("msg2")
            mgr.broadcast("msg3")  # should drop msg1

            # No exception, client still tracked
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

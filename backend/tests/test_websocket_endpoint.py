"""Integration tests for /ws/market WebSocket endpoint and broadcast loop."""

import asyncio

import pytest
from unittest.mock import MagicMock, patch

from app.models.domain import MarketSnapshot
from app.websocket.connection_manager import ConnectionManager


@pytest.fixture
def ws_manager():
    return ConnectionManager()


@pytest.fixture
def mock_snapshot():
    """Minimal MarketSnapshot for testing."""
    return MarketSnapshot(quotes={}, indices={}, foreign=None, derivatives=None)


class TestBroadcastLoop:
    @pytest.mark.asyncio
    async def test_loop_sends_snapshot(self, ws_manager, mock_snapshot):
        """Broadcast loop calls get_market_snapshot and broadcasts."""
        from app.websocket.broadcast_loop import broadcast_loop

        mock_processor = MagicMock()
        mock_processor.get_market_snapshot.return_value = mock_snapshot

        # Simulate 1 connected client via internal queue
        ws = MagicMock()
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=50)
        task = asyncio.create_task(asyncio.sleep(999))  # dummy sender
        ws_manager._clients[ws] = (queue, task)

        with patch("app.websocket.broadcast_loop.settings") as mock_settings:
            mock_settings.ws_broadcast_interval = 0.05  # fast for test

            loop_task = asyncio.create_task(
                broadcast_loop(mock_processor, ws_manager)
            )
            await asyncio.sleep(0.2)  # ~4 iterations
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
            await asyncio.sleep(0.2)
            loop_task.cancel()
            try:
                await loop_task
            except asyncio.CancelledError:
                pass

        mock_processor.get_market_snapshot.assert_not_called()

    @pytest.mark.asyncio
    async def test_loop_handles_snapshot_error(self, ws_manager):
        """Broadcast loop survives exceptions in get_market_snapshot."""
        from app.websocket.broadcast_loop import broadcast_loop

        mock_processor = MagicMock()
        mock_processor.get_market_snapshot.side_effect = RuntimeError("boom")

        # Add a fake client so the loop doesn't skip
        ws = MagicMock()
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=50)
        task = asyncio.create_task(asyncio.sleep(999))
        ws_manager._clients[ws] = (queue, task)

        with patch("app.websocket.broadcast_loop.settings") as mock_settings:
            mock_settings.ws_broadcast_interval = 0.05

            loop_task = asyncio.create_task(
                broadcast_loop(mock_processor, ws_manager)
            )
            await asyncio.sleep(0.2)
            loop_task.cancel()
            try:
                await loop_task
            except asyncio.CancelledError:
                pass

        # Loop survived the error and kept running
        assert mock_processor.get_market_snapshot.call_count >= 2
        task.cancel()

    @pytest.mark.asyncio
    async def test_loop_serializes_snapshot_as_json(self, ws_manager, mock_snapshot):
        """Verify broadcast data is valid JSON from model_dump_json."""
        import json
        from app.websocket.broadcast_loop import broadcast_loop

        mock_processor = MagicMock()
        mock_processor.get_market_snapshot.return_value = mock_snapshot

        ws = MagicMock()
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=50)
        task = asyncio.create_task(asyncio.sleep(999))
        ws_manager._clients[ws] = (queue, task)

        with patch("app.websocket.broadcast_loop.settings") as mock_settings:
            mock_settings.ws_broadcast_interval = 0.05

            loop_task = asyncio.create_task(
                broadcast_loop(mock_processor, ws_manager)
            )
            await asyncio.sleep(0.15)
            loop_task.cancel()
            try:
                await loop_task
            except asyncio.CancelledError:
                pass

        data = queue.get_nowait()
        parsed = json.loads(data)
        assert "quotes" in parsed
        assert "indices" in parsed
        task.cancel()

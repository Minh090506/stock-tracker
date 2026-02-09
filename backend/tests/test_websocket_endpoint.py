"""Tests for multi-channel WebSocket router, broadcast loop, auth, and rate limiting."""

import asyncio
import json

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.models.domain import MarketSnapshot, ForeignSummary, IndexData
from app.websocket.connection_manager import ConnectionManager


@pytest.fixture
def market_ws_manager():
    return ConnectionManager()


@pytest.fixture
def foreign_ws_manager():
    return ConnectionManager()


@pytest.fixture
def index_ws_manager():
    return ConnectionManager()


@pytest.fixture
def mock_snapshot():
    return MarketSnapshot(quotes={}, indices={}, foreign=None, derivatives=None)


@pytest.fixture
def mock_foreign_summary():
    return ForeignSummary()


@pytest.fixture
def mock_indices():
    return {
        "VN30": IndexData(index_id="VN30", value=1200.0),
        "VNINDEX": IndexData(index_id="VNINDEX", value=1100.0),
    }


def _add_fake_client(manager):
    """Add a fake client to a ConnectionManager. Returns (queue, task)."""
    ws = MagicMock()
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=50)
    task = asyncio.create_task(asyncio.sleep(999))
    manager._clients[ws] = (queue, task)
    return queue, task


class TestBroadcastLoop:
    @pytest.mark.asyncio
    async def test_sends_to_three_channels(
        self, market_ws_manager, foreign_ws_manager, index_ws_manager,
        mock_snapshot, mock_foreign_summary, mock_indices,
    ):
        """Broadcast loop feeds all 3 channels with correct data."""
        from app.websocket.broadcast_loop import broadcast_loop

        mock_processor = MagicMock()
        mock_processor.get_market_snapshot.return_value = mock_snapshot
        mock_processor.get_foreign_summary.return_value = mock_foreign_summary
        mock_processor.index_tracker.get_all.return_value = mock_indices

        mq, mt = _add_fake_client(market_ws_manager)
        fq, ft = _add_fake_client(foreign_ws_manager)
        iq, it = _add_fake_client(index_ws_manager)

        with patch("app.websocket.broadcast_loop.settings") as s:
            s.ws_broadcast_interval = 0.05
            loop_task = asyncio.create_task(
                broadcast_loop(mock_processor, market_ws_manager, foreign_ws_manager, index_ws_manager)
            )
            await asyncio.sleep(0.2)
            loop_task.cancel()
            try:
                await loop_task
            except asyncio.CancelledError:
                pass

        assert mock_processor.get_market_snapshot.call_count >= 2
        assert mock_processor.get_foreign_summary.call_count >= 2
        assert mock_processor.index_tracker.get_all.call_count >= 2
        assert not mq.empty()
        assert not fq.empty()
        assert not iq.empty()
        for t in (mt, ft, it):
            t.cancel()

    @pytest.mark.asyncio
    async def test_skips_when_no_clients(self):
        """No serialization when all channels have zero clients."""
        from app.websocket.broadcast_loop import broadcast_loop

        mock_processor = MagicMock()

        with patch("app.websocket.broadcast_loop.settings") as s:
            s.ws_broadcast_interval = 0.05
            loop_task = asyncio.create_task(
                broadcast_loop(mock_processor, ConnectionManager(), ConnectionManager(), ConnectionManager())
            )
            await asyncio.sleep(0.2)
            loop_task.cancel()
            try:
                await loop_task
            except asyncio.CancelledError:
                pass

        mock_processor.get_market_snapshot.assert_not_called()
        mock_processor.get_foreign_summary.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_snapshot_error(self, market_ws_manager):
        """Broadcast loop survives exceptions in data fetching."""
        from app.websocket.broadcast_loop import broadcast_loop

        mock_processor = MagicMock()
        mock_processor.get_market_snapshot.side_effect = RuntimeError("boom")

        _, task = _add_fake_client(market_ws_manager)

        with patch("app.websocket.broadcast_loop.settings") as s:
            s.ws_broadcast_interval = 0.05
            loop_task = asyncio.create_task(
                broadcast_loop(mock_processor, market_ws_manager, ConnectionManager(), ConnectionManager())
            )
            await asyncio.sleep(0.2)
            loop_task.cancel()
            try:
                await loop_task
            except asyncio.CancelledError:
                pass

        assert mock_processor.get_market_snapshot.call_count >= 2
        task.cancel()

    @pytest.mark.asyncio
    async def test_serializes_correctly(
        self, market_ws_manager, foreign_ws_manager, index_ws_manager,
        mock_snapshot, mock_foreign_summary, mock_indices,
    ):
        """Each channel receives valid JSON with expected keys."""
        from app.websocket.broadcast_loop import broadcast_loop

        mock_processor = MagicMock()
        mock_processor.get_market_snapshot.return_value = mock_snapshot
        mock_processor.get_foreign_summary.return_value = mock_foreign_summary
        mock_processor.index_tracker.get_all.return_value = mock_indices

        mq, mt = _add_fake_client(market_ws_manager)
        fq, ft = _add_fake_client(foreign_ws_manager)
        iq, it = _add_fake_client(index_ws_manager)

        with patch("app.websocket.broadcast_loop.settings") as s:
            s.ws_broadcast_interval = 0.05
            loop_task = asyncio.create_task(
                broadcast_loop(mock_processor, market_ws_manager, foreign_ws_manager, index_ws_manager)
            )
            await asyncio.sleep(0.15)
            loop_task.cancel()
            try:
                await loop_task
            except asyncio.CancelledError:
                pass

        market_data = json.loads(mq.get_nowait())
        assert "quotes" in market_data
        assert "indices" in market_data

        foreign_data = json.loads(fq.get_nowait())
        assert "total_buy_value" in foreign_data

        index_data = json.loads(iq.get_nowait())
        assert "VN30" in index_data
        assert "VNINDEX" in index_data

        for t in (mt, ft, it):
            t.cancel()

    @pytest.mark.asyncio
    async def test_skips_channel_with_no_clients(
        self, market_ws_manager, mock_snapshot,
    ):
        """Only channels with clients get data fetched."""
        from app.websocket.broadcast_loop import broadcast_loop

        mock_processor = MagicMock()
        mock_processor.get_market_snapshot.return_value = mock_snapshot

        _, task = _add_fake_client(market_ws_manager)

        with patch("app.websocket.broadcast_loop.settings") as s:
            s.ws_broadcast_interval = 0.05
            loop_task = asyncio.create_task(
                broadcast_loop(mock_processor, market_ws_manager, ConnectionManager(), ConnectionManager())
            )
            await asyncio.sleep(0.2)
            loop_task.cancel()
            try:
                await loop_task
            except asyncio.CancelledError:
                pass

        assert mock_processor.get_market_snapshot.call_count >= 2
        mock_processor.get_foreign_summary.assert_not_called()
        task.cancel()


class TestAuthentication:
    @pytest.mark.asyncio
    async def test_success_with_valid_token(self):
        from app.websocket.router import _authenticate

        ws = MagicMock()
        ws.query_params = {"token": "secret123"}
        ws.close = AsyncMock()

        with patch("app.websocket.router.settings") as s:
            s.ws_auth_token = "secret123"
            result = await _authenticate(ws)

        assert result is True
        ws.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_failure_with_invalid_token(self):
        from app.websocket.router import _authenticate
        from fastapi import status

        ws = MagicMock()
        ws.query_params = {"token": "wrong"}
        ws.close = AsyncMock()
        ws.client = MagicMock()
        ws.client.host = "127.0.0.1"

        with patch("app.websocket.router.settings") as s:
            s.ws_auth_token = "secret123"
            result = await _authenticate(ws)

        assert result is False
        ws.close.assert_called_once_with(code=status.WS_1008_POLICY_VIOLATION)

    @pytest.mark.asyncio
    async def test_disabled_when_token_empty(self):
        from app.websocket.router import _authenticate

        ws = MagicMock()
        ws.query_params = {}
        ws.close = AsyncMock()

        with patch("app.websocket.router.settings") as s:
            s.ws_auth_token = ""
            result = await _authenticate(ws)

        assert result is True
        ws.close.assert_not_called()


class TestRateLimiting:
    @pytest.mark.asyncio
    async def test_allows_under_threshold(self):
        from app.websocket.router import _check_rate_limit, _rate_limiter

        _rate_limiter._connections.clear()
        _rate_limiter._connections["10.0.0.1"] = 3

        ws = MagicMock()
        ws.client = MagicMock()
        ws.client.host = "10.0.0.1"
        ws.close = AsyncMock()

        with patch("app.websocket.router.settings") as s:
            s.ws_max_connections_per_ip = 5
            result = await _check_rate_limit(ws)

        assert result is True
        ws.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_rejects_over_threshold(self):
        from app.websocket.router import _check_rate_limit, _rate_limiter
        from fastapi import status

        _rate_limiter._connections.clear()
        _rate_limiter._connections["10.0.0.1"] = 5

        ws = MagicMock()
        ws.client = MagicMock()
        ws.client.host = "10.0.0.1"
        ws.close = AsyncMock()

        with patch("app.websocket.router.settings") as s:
            s.ws_max_connections_per_ip = 5
            result = await _check_rate_limit(ws)

        assert result is False
        ws.close.assert_called_once_with(code=status.WS_1008_POLICY_VIOLATION)

    def test_decrement_does_not_go_negative(self):
        from app.websocket.router import _rate_limiter

        _rate_limiter._connections.clear()
        _rate_limiter._connections["10.0.0.1"] = 2

        _rate_limiter.decrement("10.0.0.1")
        assert _rate_limiter._connections["10.0.0.1"] == 1

        _rate_limiter.decrement("10.0.0.1")
        _rate_limiter.decrement("10.0.0.1")
        assert _rate_limiter._connections["10.0.0.1"] == 0

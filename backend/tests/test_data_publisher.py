"""Tests for WebSocket DataPublisher — event-driven throttle broadcasting."""

import asyncio
import json
import time

import pytest
import pytest_asyncio
from unittest.mock import MagicMock, patch

from app.websocket.data_publisher import DataPublisher, CH_MARKET, CH_FOREIGN, CH_INDEX


def _mock_manager(client_count=1):
    """Create mock ConnectionManager with given client count."""
    mgr = MagicMock()
    mgr.client_count = client_count
    mgr.broadcast = MagicMock()
    return mgr


def _mock_processor():
    """Create mock MarketDataProcessor with serializable returns."""
    proc = MagicMock()
    snapshot = MagicMock()
    snapshot.model_dump_json.return_value = '{"quotes":{}}'
    proc.get_market_snapshot.return_value = snapshot

    summary = MagicMock()
    summary.model_dump_json.return_value = '{"total_net_value":0}'
    proc.get_foreign_summary.return_value = summary

    index_data = MagicMock()
    index_data.model_dump.return_value = {"value": 1200}
    proc.index_tracker.get_all.return_value = {"VN30": index_data}
    return proc


@pytest_asyncio.fixture
async def publisher():
    proc = _mock_processor()
    market = _mock_manager()
    foreign = _mock_manager()
    index = _mock_manager()
    pub = DataPublisher(proc, market, foreign, index)
    pub.start()
    yield pub
    pub.stop()


@pytest_asyncio.fixture
async def parts(publisher):
    """Return publisher + its internal mocks for assertions."""
    return {
        "pub": publisher,
        "proc": publisher._processor,
        "market": publisher._managers[CH_MARKET],
        "foreign": publisher._managers[CH_FOREIGN],
        "index": publisher._managers[CH_INDEX],
    }


class TestImmediateBroadcast:
    @pytest.mark.asyncio
    async def test_first_notify_broadcasts_immediately(self, parts):
        """First notification on a channel should broadcast without delay."""
        parts["pub"].notify(CH_MARKET)
        parts["market"].broadcast.assert_called_once()
        parts["proc"].get_market_snapshot.assert_called_once()

    @pytest.mark.asyncio
    async def test_foreign_channel_broadcasts(self, parts):
        parts["pub"].notify(CH_FOREIGN)
        parts["foreign"].broadcast.assert_called_once()
        parts["proc"].get_foreign_summary.assert_called_once()

    @pytest.mark.asyncio
    async def test_index_channel_broadcasts(self, parts):
        parts["pub"].notify(CH_INDEX)
        parts["index"].broadcast.assert_called_once()
        parts["proc"].index_tracker.get_all.assert_called_once()


class TestThrottle:
    @pytest.mark.asyncio
    async def test_second_notify_within_window_is_deferred(self, parts):
        """Second notification within throttle window should NOT broadcast immediately."""
        parts["pub"].notify(CH_MARKET)
        assert parts["market"].broadcast.call_count == 1

        # Second notify within 500ms — should defer, not broadcast now
        parts["pub"].notify(CH_MARKET)
        assert parts["market"].broadcast.call_count == 1

    @pytest.mark.asyncio
    async def test_deferred_broadcast_fires_after_window(self, parts):
        """Deferred broadcast should fire after throttle window expires."""
        # Use short throttle for test speed
        parts["pub"]._throttle_s = 0.05

        parts["pub"].notify(CH_MARKET)
        assert parts["market"].broadcast.call_count == 1

        parts["pub"].notify(CH_MARKET)
        assert parts["market"].broadcast.call_count == 1

        # Wait for trailing edge to fire
        await asyncio.sleep(0.1)
        assert parts["market"].broadcast.call_count == 2

    @pytest.mark.asyncio
    async def test_rapid_notifies_coalesce(self, parts):
        """Many rapid notifications should coalesce into at most 2 broadcasts."""
        parts["pub"]._throttle_s = 0.05

        # First fires immediately
        parts["pub"].notify(CH_MARKET)
        # These should all coalesce into one deferred
        for _ in range(10):
            parts["pub"].notify(CH_MARKET)

        await asyncio.sleep(0.1)
        # 1 immediate + 1 deferred = 2 total
        assert parts["market"].broadcast.call_count == 2

    @pytest.mark.asyncio
    async def test_notify_after_window_expires_broadcasts_immediately(self, parts):
        """Notify after throttle window passes should broadcast immediately."""
        parts["pub"]._throttle_s = 0.05

        parts["pub"].notify(CH_MARKET)
        assert parts["market"].broadcast.call_count == 1

        await asyncio.sleep(0.1)  # wait for window to expire

        parts["pub"].notify(CH_MARKET)
        assert parts["market"].broadcast.call_count == 2


class TestChannelIsolation:
    @pytest.mark.asyncio
    async def test_channels_throttle_independently(self, parts):
        """Each channel has its own throttle timer."""
        parts["pub"].notify(CH_MARKET)
        parts["pub"].notify(CH_FOREIGN)
        parts["pub"].notify(CH_INDEX)

        # All three should broadcast (first notify per channel)
        assert parts["market"].broadcast.call_count == 1
        assert parts["foreign"].broadcast.call_count == 1
        assert parts["index"].broadcast.call_count == 1


class TestNoClients:
    @pytest.mark.asyncio
    async def test_skip_channel_with_no_clients(self):
        """Should not broadcast to channels with 0 clients."""
        proc = _mock_processor()
        market = _mock_manager(client_count=0)
        foreign = _mock_manager(client_count=1)
        index = _mock_manager(client_count=0)
        pub = DataPublisher(proc, market, foreign, index)
        pub.start()

        pub.notify(CH_MARKET)
        pub.notify(CH_FOREIGN)
        pub.notify(CH_INDEX)

        market.broadcast.assert_not_called()
        foreign.broadcast.assert_called_once()
        index.broadcast.assert_not_called()
        pub.stop()


class TestSSIStatus:
    @pytest.mark.asyncio
    async def test_on_ssi_disconnect_notifies_clients(self, parts):
        parts["pub"].on_ssi_disconnect()
        expected = json.dumps({"type": "status", "connected": False})
        parts["market"].broadcast.assert_called_with(expected)
        parts["foreign"].broadcast.assert_called_with(expected)
        parts["index"].broadcast.assert_called_with(expected)

    @pytest.mark.asyncio
    async def test_on_ssi_reconnect_notifies_clients(self, parts):
        parts["pub"].on_ssi_reconnect()
        expected = json.dumps({"type": "status", "connected": True})
        parts["market"].broadcast.assert_called_with(expected)

    @pytest.mark.asyncio
    async def test_disconnect_skips_empty_channels(self):
        proc = _mock_processor()
        market = _mock_manager(client_count=0)
        foreign = _mock_manager(client_count=1)
        index = _mock_manager(client_count=0)
        pub = DataPublisher(proc, market, foreign, index)
        pub.start()

        pub.on_ssi_disconnect()
        market.broadcast.assert_not_called()
        foreign.broadcast.assert_called_once()
        index.broadcast.assert_not_called()
        pub.stop()


class TestLifecycle:
    @pytest.mark.asyncio
    async def test_stop_cancels_pending_timers(self, parts):
        parts["pub"]._throttle_s = 10  # long throttle
        parts["pub"].notify(CH_MARKET)
        parts["pub"].notify(CH_MARKET)  # creates pending timer

        assert CH_MARKET in parts["pub"]._pending
        parts["pub"].stop()
        assert len(parts["pub"]._pending) == 0

    @pytest.mark.asyncio
    async def test_notify_after_stop_is_noop(self, parts):
        parts["pub"].stop()
        parts["pub"].notify(CH_MARKET)
        parts["market"].broadcast.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_channel_is_ignored(self, parts):
        """Notify with unknown channel should not raise."""
        parts["pub"].notify("unknown_channel")
        # No broadcast, no error

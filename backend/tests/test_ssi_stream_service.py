"""Tests for SSI stream service — demux routing and callback dispatch."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.ssi_messages import (
    SSIForeignMessage,
    SSIIndexMessage,
    SSIQuoteMessage,
    SSITradeMessage,
)
from app.services.ssi_stream_service import SSIStreamService


@pytest.fixture
def stream_service():
    """Create stream service with mocked auth and market services."""
    auth = MagicMock()
    auth.config = {
        "auth_type": "Bearer",
        "consumerID": "test",
        "consumerSecret": "test",
        "url": "https://fc-data.ssi.com.vn/",
        "stream_url": "https://fc-data.ssi.com.vn/",
    }
    market = MagicMock()
    svc = SSIStreamService(auth, market)
    # Set the event loop so _schedule_callback works
    svc._loop = asyncio.new_event_loop()
    return svc


class TestCallbackRegistration:
    def test_register_trade_callback(self, stream_service):
        cb = AsyncMock()
        stream_service.on_trade(cb)
        assert cb in stream_service._callbacks["Trade"]

    def test_register_quote_callback(self, stream_service):
        cb = AsyncMock()
        stream_service.on_quote(cb)
        assert cb in stream_service._callbacks["Quote"]

    def test_register_foreign_callback(self, stream_service):
        cb = AsyncMock()
        stream_service.on_foreign(cb)
        assert cb in stream_service._callbacks["R"]

    def test_register_index_callback(self, stream_service):
        cb = AsyncMock()
        stream_service.on_index(cb)
        assert cb in stream_service._callbacks["MI"]

    def test_register_bar_callback(self, stream_service):
        cb = AsyncMock()
        stream_service.on_bar(cb)
        assert cb in stream_service._callbacks["B"]

    def test_multiple_callbacks_per_type(self, stream_service):
        cb1 = AsyncMock()
        cb2 = AsyncMock()
        stream_service.on_trade(cb1)
        stream_service.on_trade(cb2)
        assert len(stream_service._callbacks["Trade"]) == 2


class TestHandleMessage:
    def test_demux_trade(self, stream_service):
        cb = AsyncMock()
        stream_service.on_trade(cb)
        raw = {"Content": {
            "RType": "Trade", "Symbol": "VNM",
            "LastPrice": 85000, "LastVol": 100,
        }}
        stream_service._handle_message(raw)
        # Callback scheduled via run_coroutine_threadsafe — give event loop a tick
        stream_service._loop.run_until_complete(asyncio.sleep(0.05))
        cb.assert_called_once()
        msg = cb.call_args[0][0]
        assert isinstance(msg, SSITradeMessage)
        assert msg.symbol == "VNM"

    def test_demux_quote(self, stream_service):
        cb = AsyncMock()
        stream_service.on_quote(cb)
        raw = {"Content": {
            "RType": "Quote", "Symbol": "HPG",
            "BidPrice1": 25400, "AskPrice1": 25500,
        }}
        stream_service._handle_message(raw)
        stream_service._loop.run_until_complete(asyncio.sleep(0.05))
        cb.assert_called_once()
        msg = cb.call_args[0][0]
        assert isinstance(msg, SSIQuoteMessage)

    def test_demux_foreign(self, stream_service):
        cb = AsyncMock()
        stream_service.on_foreign(cb)
        raw = {"Content": {
            "RType": "R", "Symbol": "VCB",
            "FBuyVol": 500, "FSellVol": 300,
        }}
        stream_service._handle_message(raw)
        stream_service._loop.run_until_complete(asyncio.sleep(0.05))
        cb.assert_called_once()
        msg = cb.call_args[0][0]
        assert isinstance(msg, SSIForeignMessage)
        assert msg.f_buy_vol == 500

    def test_demux_index(self, stream_service):
        cb = AsyncMock()
        stream_service.on_index(cb)
        raw = {"Content": {
            "RType": "MI", "IndexId": "VN30", "IndexValue": 1234.56,
        }}
        stream_service._handle_message(raw)
        stream_service._loop.run_until_complete(asyncio.sleep(0.05))
        cb.assert_called_once()
        msg = cb.call_args[0][0]
        assert isinstance(msg, SSIIndexMessage)
        assert msg.index_id == "VN30"

    def test_unknown_rtype_no_callback(self, stream_service):
        cb = AsyncMock()
        stream_service.on_trade(cb)
        raw = {"Content": {"RType": "Unknown", "Symbol": "VNM"}}
        stream_service._handle_message(raw)
        stream_service._loop.run_until_complete(asyncio.sleep(0.05))
        cb.assert_not_called()

    def test_invalid_message_no_crash(self, stream_service):
        """Non-dict/non-JSON input should not raise."""
        stream_service._handle_message(None)
        stream_service._handle_message(42)
        stream_service._handle_message("not json {{{")

    def test_json_string_input(self, stream_service):
        """Handle raw JSON string from SSI."""
        cb = AsyncMock()
        stream_service.on_trade(cb)
        import json
        raw = json.dumps({"Content": {
            "RType": "Trade", "Symbol": "FPT", "LastPrice": 90000,
        }})
        stream_service._handle_message(raw)
        stream_service._loop.run_until_complete(asyncio.sleep(0.05))
        cb.assert_called_once()

    def test_multiple_callbacks_all_invoked(self, stream_service):
        cb1 = AsyncMock()
        cb2 = AsyncMock()
        stream_service.on_trade(cb1)
        stream_service.on_trade(cb2)
        raw = {"Content": {"RType": "Trade", "Symbol": "VNM"}}
        stream_service._handle_message(raw)
        stream_service._loop.run_until_complete(asyncio.sleep(0.05))
        cb1.assert_called_once()
        cb2.assert_called_once()


class TestCallbackErrorIsolation:
    def test_failing_callback_does_not_crash(self, stream_service):
        """A callback that raises should not crash the service."""
        failing_cb = AsyncMock(side_effect=ValueError("test error"))
        stream_service.on_trade(failing_cb)
        raw = {"Content": {"RType": "Trade", "Symbol": "VNM"}}
        stream_service._handle_message(raw)
        stream_service._loop.run_until_complete(asyncio.sleep(0.05))
        failing_cb.assert_called_once()

    def test_failing_callback_doesnt_block_others(self, stream_service):
        """Other callbacks should still execute if one fails."""
        failing_cb = AsyncMock(side_effect=ValueError("boom"))
        good_cb = AsyncMock()
        stream_service.on_trade(failing_cb)
        stream_service.on_trade(good_cb)
        raw = {"Content": {"RType": "Trade", "Symbol": "VNM"}}
        stream_service._handle_message(raw)
        stream_service._loop.run_until_complete(asyncio.sleep(0.05))
        good_cb.assert_called_once()


class TestNoLoopDropsCallback:
    def test_no_loop_logs_warning(self):
        """Without event loop set, callbacks should be dropped gracefully."""
        auth = MagicMock()
        auth.config = {"consumerID": "t", "consumerSecret": "t", "url": "x", "stream_url": "x", "auth_type": "Bearer"}
        market = MagicMock()
        svc = SSIStreamService(auth, market)
        # _loop is None by default
        cb = AsyncMock()
        svc.on_trade(cb)
        raw = {"Content": {"RType": "Trade", "Symbol": "VNM"}}
        svc._handle_message(raw)
        # Should not raise, callback not called
        cb.assert_not_called()

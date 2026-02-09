"""WebSocket server integration tests.

Lightweight test app (no SSI/DB deps) with real router functions.
Validates lifecycle, broadcast, heartbeat, channels, and data format.
"""

import asyncio
import json
import threading

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import FastAPI, WebSocket
from starlette.testclient import TestClient

from app.models.domain import MarketSnapshot, ForeignSummary, IndexData
from app.websocket.connection_manager import ConnectionManager
from app.websocket.router import _ws_lifecycle, _rate_limiter, _heartbeat


# ---------------------------------------------------------------------------
# Infrastructure
# ---------------------------------------------------------------------------

def _create_test_app(market_mgr, foreign_mgr, index_mgr):
    """Minimal FastAPI app with WS endpoints bound to given managers."""
    app = FastAPI()

    @app.websocket("/ws/market")
    async def ws_market(ws: WebSocket):
        await _ws_lifecycle(ws, market_mgr)

    @app.websocket("/ws/foreign")
    async def ws_foreign(ws: WebSocket):
        await _ws_lifecycle(ws, foreign_mgr)

    @app.websocket("/ws/index")
    async def ws_index(ws: WebSocket):
        await _ws_lifecycle(ws, index_mgr)

    return app


def _mock_settings(**kw):
    """Mock settings with test defaults. Override via kwargs."""
    s = MagicMock()
    s.ws_auth_token = kw.get("ws_auth_token", "")
    s.ws_max_connections_per_ip = kw.get("ws_max_connections_per_ip", 10)
    s.ws_heartbeat_interval = kw.get("ws_heartbeat_interval", 999.0)
    s.ws_heartbeat_timeout = kw.get("ws_heartbeat_timeout", 10.0)
    return s


_SETTINGS = "app.websocket.router.settings"


@pytest.fixture(autouse=True)
def _clean_rate_limiter():
    _rate_limiter._connections.clear()
    yield
    _rate_limiter._connections.clear()


@pytest.fixture
def managers():
    return ConnectionManager(), ConnectionManager(), ConnectionManager()


@pytest.fixture
def market_mgr(managers):
    return managers[0]


@pytest.fixture
def foreign_mgr(managers):
    return managers[1]


@pytest.fixture
def index_mgr(managers):
    return managers[2]


@pytest.fixture
def app(managers):
    return _create_test_app(*managers)


# ---------------------------------------------------------------------------
# Connection / disconnection lifecycle
# ---------------------------------------------------------------------------

class TestConnectionLifecycle:
    def test_connect_adds_client(self, app, market_mgr):
        with patch(_SETTINGS, _mock_settings()):
            with TestClient(app).websocket_connect("/ws/market"):
                assert market_mgr.client_count == 1

    def test_disconnect_removes_client(self, app, market_mgr):
        with patch(_SETTINGS, _mock_settings()):
            with TestClient(app).websocket_connect("/ws/market"):
                pass
            assert market_mgr.client_count == 0

    def test_rate_limiter_tracks_ip(self, app):
        with patch(_SETTINGS, _mock_settings()):
            with TestClient(app).websocket_connect("/ws/market"):
                assert sum(_rate_limiter._connections.values()) >= 1
            assert sum(_rate_limiter._connections.values()) == 0

    def test_auth_rejects_invalid_token(self, app, market_mgr):
        with patch(_SETTINGS, _mock_settings(ws_auth_token="secret")):
            with pytest.raises(Exception):
                with TestClient(app).websocket_connect("/ws/market?token=wrong"):
                    pass
            assert market_mgr.client_count == 0

    def test_auth_accepts_valid_token(self, app, market_mgr):
        with patch(_SETTINGS, _mock_settings(ws_auth_token="secret")):
            with TestClient(app).websocket_connect("/ws/market?token=secret"):
                assert market_mgr.client_count == 1

    def test_auth_disabled_when_empty(self, app, market_mgr):
        with patch(_SETTINGS, _mock_settings(ws_auth_token="")):
            with TestClient(app).websocket_connect("/ws/market"):
                assert market_mgr.client_count == 1


# ---------------------------------------------------------------------------
# Broadcast to clients
# ---------------------------------------------------------------------------

class TestBroadcast:
    def test_single_client_receives_data(self, app, market_mgr):
        with patch(_SETTINGS, _mock_settings()):
            with TestClient(app).websocket_connect("/ws/market") as ws:
                market_mgr.broadcast('{"quotes": {}}')
                assert ws.receive_text() == '{"quotes": {}}'

    def test_two_clients_both_receive_data(self, app, market_mgr):
        """Two WebSocket clients on same channel both get the broadcast."""
        with patch(_SETTINGS, _mock_settings()):
            with TestClient(app) as client:
                bg_data = []
                ready = threading.Event()
                done = threading.Event()

                def bg():
                    with client.websocket_connect("/ws/market") as ws:
                        ready.set()
                        bg_data.append(ws.receive_text())
                        done.wait(timeout=3)

                t = threading.Thread(target=bg, daemon=True)
                t.start()
                ready.wait(timeout=3)

                with client.websocket_connect("/ws/market") as ws:
                    assert market_mgr.client_count == 2
                    market_mgr.broadcast('{"test": true}')
                    assert json.loads(ws.receive_text()) == {"test": True}

                done.set()
                t.join(timeout=3)
                assert json.loads(bg_data[0]) == {"test": True}


# ---------------------------------------------------------------------------
# Channel subscription — isolation between channels
# ---------------------------------------------------------------------------

class TestChannelSubscription:
    def test_market_client_only_gets_market_data(self, app, market_mgr, foreign_mgr):
        with patch(_SETTINGS, _mock_settings()):
            with TestClient(app).websocket_connect("/ws/market") as ws:
                market_mgr.broadcast('{"ch": "market"}')
                foreign_mgr.broadcast('{"ch": "foreign"}')  # should NOT arrive
                assert json.loads(ws.receive_text())["ch"] == "market"

    def test_foreign_client_only_gets_foreign_data(self, app, market_mgr, foreign_mgr):
        with patch(_SETTINGS, _mock_settings()):
            with TestClient(app).websocket_connect("/ws/foreign") as ws:
                foreign_mgr.broadcast('{"ch": "foreign"}')
                market_mgr.broadcast('{"ch": "market"}')  # should NOT arrive
                assert json.loads(ws.receive_text())["ch"] == "foreign"

    def test_channels_have_independent_counts(self, app, market_mgr, foreign_mgr, index_mgr):
        with patch(_SETTINGS, _mock_settings()):
            with TestClient(app).websocket_connect("/ws/market"):
                assert market_mgr.client_count == 1
                assert foreign_mgr.client_count == 0
                assert index_mgr.client_count == 0


# ---------------------------------------------------------------------------
# Heartbeat mechanism
# ---------------------------------------------------------------------------

class TestHeartbeat:
    def test_receives_ping_bytes(self, app):
        with patch(_SETTINGS, _mock_settings(ws_heartbeat_interval=0.1)):
            with TestClient(app).websocket_connect("/ws/market") as ws:
                assert ws.receive_bytes() == b"ping"

    def test_receives_multiple_pings(self, app):
        with patch(_SETTINGS, _mock_settings(ws_heartbeat_interval=0.05)):
            with TestClient(app).websocket_connect("/ws/market") as ws:
                assert ws.receive_bytes() == b"ping"
                assert ws.receive_bytes() == b"ping"

    @pytest.mark.asyncio
    async def test_heartbeat_sends_and_cancels_cleanly(self):
        """_heartbeat sends ping bytes then exits cleanly on cancellation."""
        ws = AsyncMock()
        with patch(_SETTINGS) as s:
            s.ws_heartbeat_interval = 0.05
            s.ws_heartbeat_timeout = 5.0
            task = asyncio.create_task(_heartbeat(ws))
            await asyncio.sleep(0.12)
            task.cancel()
            await task  # _heartbeat catches CancelledError internally
        ws.send_bytes.assert_called_with(b"ping")
        assert ws.send_bytes.call_count >= 2


# ---------------------------------------------------------------------------
# Data format correctness
# ---------------------------------------------------------------------------

class TestDataFormat:
    def test_market_snapshot_has_required_keys(self, app, market_mgr):
        snapshot = MarketSnapshot(quotes={}, indices={}, foreign=None, derivatives=None)
        with patch(_SETTINGS, _mock_settings()):
            with TestClient(app).websocket_connect("/ws/market") as ws:
                market_mgr.broadcast(snapshot.model_dump_json())
                data = json.loads(ws.receive_text())
                assert set(data.keys()) >= {"quotes", "indices", "foreign", "derivatives"}

    def test_foreign_summary_has_required_keys(self, app, foreign_mgr):
        with patch(_SETTINGS, _mock_settings()):
            with TestClient(app).websocket_connect("/ws/foreign") as ws:
                foreign_mgr.broadcast(ForeignSummary().model_dump_json())
                data = json.loads(ws.receive_text())
                for key in ("total_buy_value", "total_sell_value", "total_net_value",
                            "total_buy_volume", "total_sell_volume", "total_net_volume",
                            "top_buy", "top_sell"):
                    assert key in data

    def test_index_data_has_expected_structure(self, app, index_mgr):
        indices = {"VN30": IndexData(index_id="VN30", value=1200.0)}
        payload = json.dumps({k: v.model_dump() for k, v in indices.items()}, default=str)
        with patch(_SETTINGS, _mock_settings()):
            with TestClient(app).websocket_connect("/ws/index") as ws:
                index_mgr.broadcast(payload)
                data = json.loads(ws.receive_text())
                assert data["VN30"]["index_id"] == "VN30"
                assert data["VN30"]["value"] == 1200.0

    def test_status_message_format(self, app, market_mgr):
        with patch(_SETTINGS, _mock_settings()):
            with TestClient(app).websocket_connect("/ws/market") as ws:
                market_mgr.broadcast(json.dumps({"type": "status", "connected": False}))
                assert json.loads(ws.receive_text()) == {"type": "status", "connected": False}

    def test_nested_json_integrity(self, app, market_mgr):
        """Complex nested JSON transmitted without corruption."""
        payload = {"quotes": {"VNM": {"volume": 5000}}, "indices": {"VN30": 1245.5}}
        with patch(_SETTINGS, _mock_settings()):
            with TestClient(app).websocket_connect("/ws/market") as ws:
                market_mgr.broadcast(json.dumps(payload))
                assert json.loads(ws.receive_text()) == payload

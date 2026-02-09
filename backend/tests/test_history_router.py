"""Tests for history REST endpoints — candles, ticks, foreign, index, derivatives."""

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI

from app.routers.history_router import router


# Isolated test app — no production lifespan/db/ssi
_app = FastAPI()
_app.include_router(router)


@pytest.fixture
def mock_svc():
    return AsyncMock()


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# GET /api/history/{symbol}/candles
# ---------------------------------------------------------------------------
class TestGetCandles:
    @pytest.mark.asyncio
    async def test_returns_candle_rows(self, client, mock_svc):
        mock_svc.get_candles.return_value = [
            {"symbol": "VNM", "timestamp": "2026-02-07T10:00:00", "open": 80,
             "high": 81, "low": 79, "close": 80.5, "volume": 1000,
             "active_buy_vol": 600, "active_sell_vol": 400},
        ]
        with patch("app.routers.history_router._get_svc", return_value=mock_svc):
            resp = await client.get(
                "/api/history/VNM/candles",
                params={"start": "2026-02-01", "end": "2026-02-07"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["symbol"] == "VNM"

    @pytest.mark.asyncio
    async def test_symbol_uppercased(self, client, mock_svc):
        mock_svc.get_candles.return_value = []
        with patch("app.routers.history_router._get_svc", return_value=mock_svc):
            await client.get(
                "/api/history/vnm/candles",
                params={"start": "2026-02-01", "end": "2026-02-07"},
            )
        mock_svc.get_candles.assert_called_once()
        assert mock_svc.get_candles.call_args[0][0] == "VNM"

    @pytest.mark.asyncio
    async def test_empty_result(self, client, mock_svc):
        mock_svc.get_candles.return_value = []
        with patch("app.routers.history_router._get_svc", return_value=mock_svc):
            resp = await client.get(
                "/api/history/XYZ/candles",
                params={"start": "2026-01-01", "end": "2026-01-31"},
            )
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_missing_start_param(self, client):
        resp = await client.get(
            "/api/history/VNM/candles", params={"end": "2026-02-07"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_end_param(self, client):
        resp = await client.get(
            "/api/history/VNM/candles", params={"start": "2026-02-01"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_date_format(self, client):
        resp = await client.get(
            "/api/history/VNM/candles",
            params={"start": "not-a-date", "end": "2026-02-07"},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/history/{symbol}/ticks
# ---------------------------------------------------------------------------
class TestGetTicks:
    @pytest.mark.asyncio
    async def test_returns_tick_rows(self, client, mock_svc):
        mock_svc.get_ticks.return_value = [
            {"symbol": "VNM", "timestamp": "2026-02-07T10:00:01",
             "price": 80.5, "volume": 100, "side": "mua_chu_dong",
             "bid": 80.0, "ask": 80.5},
        ]
        with patch("app.routers.history_router._get_svc", return_value=mock_svc):
            resp = await client.get(
                "/api/history/VNM/ticks",
                params={"start": "2026-02-07", "end": "2026-02-07"},
            )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    @pytest.mark.asyncio
    async def test_custom_limit(self, client, mock_svc):
        mock_svc.get_ticks.return_value = []
        with patch("app.routers.history_router._get_svc", return_value=mock_svc):
            await client.get(
                "/api/history/VNM/ticks",
                params={"start": "2026-02-07", "end": "2026-02-07", "limit": 500},
            )
        assert mock_svc.get_ticks.call_args[0][3] == 500

    @pytest.mark.asyncio
    async def test_limit_exceeds_max_rejected(self, client):
        resp = await client.get(
            "/api/history/VNM/ticks",
            params={"start": "2026-02-07", "end": "2026-02-07", "limit": 50001},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_symbol_uppercased(self, client, mock_svc):
        mock_svc.get_ticks.return_value = []
        with patch("app.routers.history_router._get_svc", return_value=mock_svc):
            await client.get(
                "/api/history/fpt/ticks",
                params={"start": "2026-02-07", "end": "2026-02-07"},
            )
        assert mock_svc.get_ticks.call_args[0][0] == "FPT"


# ---------------------------------------------------------------------------
# GET /api/history/{symbol}/foreign
# ---------------------------------------------------------------------------
class TestGetForeignFlow:
    @pytest.mark.asyncio
    async def test_returns_foreign_rows(self, client, mock_svc):
        mock_svc.get_foreign_flow.return_value = [
            {"symbol": "VNM", "timestamp": "2026-02-07T10:00:00",
             "buy_vol": 1000, "sell_vol": 500, "net_vol": 500,
             "buy_value": 80000, "sell_value": 40000},
        ]
        with patch("app.routers.history_router._get_svc", return_value=mock_svc):
            resp = await client.get(
                "/api/history/VNM/foreign",
                params={"start": "2026-02-01", "end": "2026-02-07"},
            )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    @pytest.mark.asyncio
    async def test_empty_result(self, client, mock_svc):
        mock_svc.get_foreign_flow.return_value = []
        with patch("app.routers.history_router._get_svc", return_value=mock_svc):
            resp = await client.get(
                "/api/history/XYZ/foreign",
                params={"start": "2026-01-01", "end": "2026-01-31"},
            )
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_missing_params(self, client):
        resp = await client.get("/api/history/VNM/foreign")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/history/{symbol}/foreign/daily
# ---------------------------------------------------------------------------
class TestGetForeignDaily:
    @pytest.mark.asyncio
    async def test_returns_daily_summary(self, client, mock_svc):
        mock_svc.get_foreign_flow_daily_summary.return_value = [
            {"day": "2026-02-06", "buy_vol": 5000, "sell_vol": 3000,
             "net_vol": 2000, "buy_value": 400000, "sell_value": 240000},
        ]
        with patch("app.routers.history_router._get_svc", return_value=mock_svc):
            resp = await client.get("/api/history/VNM/foreign/daily")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["net_vol"] == 2000

    @pytest.mark.asyncio
    async def test_default_days(self, client, mock_svc):
        mock_svc.get_foreign_flow_daily_summary.return_value = []
        with patch("app.routers.history_router._get_svc", return_value=mock_svc):
            await client.get("/api/history/VNM/foreign/daily")
        mock_svc.get_foreign_flow_daily_summary.assert_called_once_with("VNM", 30)

    @pytest.mark.asyncio
    async def test_custom_days(self, client, mock_svc):
        mock_svc.get_foreign_flow_daily_summary.return_value = []
        with patch("app.routers.history_router._get_svc", return_value=mock_svc):
            await client.get("/api/history/VNM/foreign/daily", params={"days": 60})
        mock_svc.get_foreign_flow_daily_summary.assert_called_once_with("VNM", 60)

    @pytest.mark.asyncio
    async def test_days_exceeds_max_rejected(self, client):
        resp = await client.get(
            "/api/history/VNM/foreign/daily", params={"days": 366},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_symbol_uppercased(self, client, mock_svc):
        mock_svc.get_foreign_flow_daily_summary.return_value = []
        with patch("app.routers.history_router._get_svc", return_value=mock_svc):
            await client.get("/api/history/vnm/foreign/daily")
        assert mock_svc.get_foreign_flow_daily_summary.call_args[0][0] == "VNM"


# ---------------------------------------------------------------------------
# GET /api/history/index/{index_name}
# ---------------------------------------------------------------------------
class TestGetIndexHistory:
    @pytest.mark.asyncio
    async def test_returns_index_rows(self, client, mock_svc):
        mock_svc.get_index_history.return_value = [
            {"index_name": "VN30", "timestamp": "2026-02-07T10:00:00",
             "value": 1250.0, "change_pct": 0.5, "volume": 150000000},
        ]
        with patch("app.routers.history_router._get_svc", return_value=mock_svc):
            resp = await client.get(
                "/api/history/index/VN30",
                params={"start": "2026-02-01", "end": "2026-02-07"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["index_name"] == "VN30"

    @pytest.mark.asyncio
    async def test_empty_result(self, client, mock_svc):
        mock_svc.get_index_history.return_value = []
        with patch("app.routers.history_router._get_svc", return_value=mock_svc):
            resp = await client.get(
                "/api/history/index/VNINDEX",
                params={"start": "2026-02-01", "end": "2026-02-07"},
            )
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_index_name_uppercased(self, client, mock_svc):
        mock_svc.get_index_history.return_value = []
        with patch("app.routers.history_router._get_svc", return_value=mock_svc):
            await client.get(
                "/api/history/index/vn30",
                params={"start": "2026-02-01", "end": "2026-02-07"},
            )
        assert mock_svc.get_index_history.call_args[0][0] == "VN30"

    @pytest.mark.asyncio
    async def test_missing_params(self, client):
        resp = await client.get("/api/history/index/VN30")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/history/derivatives/{contract}
# ---------------------------------------------------------------------------
class TestGetDerivativesHistory:
    @pytest.mark.asyncio
    async def test_returns_derivatives_rows(self, client, mock_svc):
        mock_svc.get_derivatives_history.return_value = [
            {"contract": "VN30F2603", "timestamp": "2026-02-07T10:00:00",
             "price": 1260.0, "basis": 10.0, "open_interest": 50000},
        ]
        with patch("app.routers.history_router._get_svc", return_value=mock_svc):
            resp = await client.get(
                "/api/history/derivatives/VN30F2603",
                params={"start": "2026-02-01", "end": "2026-02-07"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["basis"] == 10.0

    @pytest.mark.asyncio
    async def test_empty_result(self, client, mock_svc):
        mock_svc.get_derivatives_history.return_value = []
        with patch("app.routers.history_router._get_svc", return_value=mock_svc):
            resp = await client.get(
                "/api/history/derivatives/VN30F2603",
                params={"start": "2026-01-01", "end": "2026-01-31"},
            )
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_contract_uppercased(self, client, mock_svc):
        mock_svc.get_derivatives_history.return_value = []
        with patch("app.routers.history_router._get_svc", return_value=mock_svc):
            await client.get(
                "/api/history/derivatives/vn30f2603",
                params={"start": "2026-02-01", "end": "2026-02-07"},
            )
        assert mock_svc.get_derivatives_history.call_args[0][0] == "VN30F2603"

    @pytest.mark.asyncio
    async def test_missing_params(self, client):
        resp = await client.get("/api/history/derivatives/VN30F2603")
        assert resp.status_code == 422

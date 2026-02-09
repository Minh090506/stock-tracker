"""Tests for market REST endpoints — snapshot, foreign-detail, volume-stats, basis-trend."""

import sys
from datetime import datetime
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI

from app.models.domain import (
    BasisPoint,
    DerivativesData,
    ForeignInvestorData,
    ForeignSummary,
    IndexData,
    MarketSnapshot,
    PriceData,
    SessionStats,
)
from app.routers.market_router import router


# Isolated test app — no production lifespan/db/ssi
_app = FastAPI()
_app.include_router(router)


@pytest.fixture
def mock_processor():
    return MagicMock()


@pytest_asyncio.fixture
async def client(mock_processor):
    # Intercept `from app.main import processor` without importing real app.main
    # (real app.main triggers SSIAuthService which requires credentials)
    fake_main = ModuleType("app.main")
    fake_main.processor = mock_processor
    with patch.dict(sys.modules, {"app.main": fake_main}):
        transport = ASGITransport(app=_app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


# ---------------------------------------------------------------------------
# GET /api/market/snapshot
# ---------------------------------------------------------------------------
class TestGetSnapshot:
    @pytest.mark.asyncio
    async def test_returns_full_snapshot(self, client, mock_processor):
        snapshot = MarketSnapshot(
            quotes={"VNM": SessionStats(symbol="VNM", mua_chu_dong_volume=100)},
            prices={"VNM": PriceData(last_price=80.5, change=0.5, change_pct=0.63)},
            indices={"VN30": IndexData(index_id="VN30", value=1250.0)},
            foreign=ForeignSummary(total_buy_volume=5000),
            derivatives=DerivativesData(symbol="VN30F2603", last_price=1260.0, basis=10.0),
        )
        mock_processor.get_market_snapshot.return_value = snapshot
        resp = await client.get("/api/market/snapshot")

        assert resp.status_code == 200
        data = resp.json()
        assert "VNM" in data["quotes"]
        assert data["prices"]["VNM"]["last_price"] == 80.5
        assert data["indices"]["VN30"]["value"] == 1250.0
        assert data["foreign"]["total_buy_volume"] == 5000
        assert data["derivatives"]["symbol"] == "VN30F2603"

    @pytest.mark.asyncio
    async def test_empty_processor_state(self, client, mock_processor):
        mock_processor.get_market_snapshot.return_value = MarketSnapshot()
        resp = await client.get("/api/market/snapshot")

        assert resp.status_code == 200
        data = resp.json()
        assert data["quotes"] == {}
        assert data["prices"] == {}
        assert data["indices"] == {}
        assert data["foreign"] is None
        assert data["derivatives"] is None


# ---------------------------------------------------------------------------
# GET /api/market/foreign-detail
# ---------------------------------------------------------------------------
class TestGetForeignDetail:
    @pytest.mark.asyncio
    async def test_returns_summary_and_stocks(self, client, mock_processor):
        summary = ForeignSummary(total_buy_volume=5000, total_sell_volume=3000)
        stocks = {
            "VNM": ForeignInvestorData(symbol="VNM", buy_volume=2000, sell_volume=1000),
            "FPT": ForeignInvestorData(symbol="FPT", buy_volume=3000, sell_volume=2000),
        }
        mock_processor.get_foreign_summary.return_value = summary
        mock_processor.foreign_tracker.get_all.return_value = stocks
        resp = await client.get("/api/market/foreign-detail")

        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["total_buy_volume"] == 5000
        assert len(data["stocks"]) == 2

    @pytest.mark.asyncio
    async def test_no_foreign_data(self, client, mock_processor):
        mock_processor.get_foreign_summary.return_value = ForeignSummary()
        mock_processor.foreign_tracker.get_all.return_value = {}
        resp = await client.get("/api/market/foreign-detail")

        assert resp.status_code == 200
        data = resp.json()
        assert data["stocks"] == []
        assert data["summary"]["total_buy_volume"] == 0


# ---------------------------------------------------------------------------
# GET /api/market/volume-stats
# ---------------------------------------------------------------------------
class TestGetVolumeStats:
    @pytest.mark.asyncio
    async def test_returns_stats_list(self, client, mock_processor):
        stats = {
            "VNM": SessionStats(symbol="VNM", mua_chu_dong_volume=500, ban_chu_dong_volume=300),
            "FPT": SessionStats(symbol="FPT", mua_chu_dong_volume=800, ban_chu_dong_volume=200),
        }
        mock_processor.aggregator.get_all_stats.return_value = stats
        resp = await client.get("/api/market/volume-stats")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["stats"]) == 2
        symbols = {s["symbol"] for s in data["stats"]}
        assert symbols == {"VNM", "FPT"}

    @pytest.mark.asyncio
    async def test_no_trades_yet(self, client, mock_processor):
        mock_processor.aggregator.get_all_stats.return_value = {}
        resp = await client.get("/api/market/volume-stats")

        assert resp.status_code == 200
        assert resp.json()["stats"] == []


# ---------------------------------------------------------------------------
# GET /api/market/basis-trend
# ---------------------------------------------------------------------------
class TestGetBasisTrend:
    @pytest.mark.asyncio
    async def test_returns_basis_points(self, client, mock_processor):
        now = datetime(2026, 2, 9, 10, 30, 0)
        points = [
            BasisPoint(
                timestamp=now, futures_symbol="VN30F2603",
                futures_price=1260.0, spot_value=1250.0,
                basis=10.0, basis_pct=0.8, is_premium=True,
            ),
        ]
        mock_processor.derivatives_tracker.get_basis_trend.return_value = points
        resp = await client.get("/api/market/basis-trend", params={"minutes": 30})

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["basis"] == 10.0
        assert data[0]["is_premium"] is True

    @pytest.mark.asyncio
    async def test_default_minutes(self, client, mock_processor):
        mock_processor.derivatives_tracker.get_basis_trend.return_value = []
        resp = await client.get("/api/market/basis-trend")

        assert resp.status_code == 200
        mock_processor.derivatives_tracker.get_basis_trend.assert_called_once_with(30)

    @pytest.mark.asyncio
    async def test_custom_minutes(self, client, mock_processor):
        mock_processor.derivatives_tracker.get_basis_trend.return_value = []
        await client.get("/api/market/basis-trend", params={"minutes": 60})

        mock_processor.derivatives_tracker.get_basis_trend.assert_called_once_with(60)

    @pytest.mark.asyncio
    async def test_minutes_below_min_rejected(self, client):
        resp = await client.get("/api/market/basis-trend", params={"minutes": 0})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_minutes_above_max_rejected(self, client):
        resp = await client.get("/api/market/basis-trend", params={"minutes": 121})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_trend(self, client, mock_processor):
        mock_processor.derivatives_tracker.get_basis_trend.return_value = []
        resp = await client.get("/api/market/basis-trend")

        assert resp.status_code == 200
        assert resp.json() == []

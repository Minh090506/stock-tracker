"""Tests for HistoryService — query methods against mock asyncpg pool."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.database.connection import Database
from app.database.history_service import HistoryService


@pytest.fixture
def mock_db():
    db = MagicMock(spec=Database)
    db.pool = AsyncMock()
    return db


@pytest.fixture
def svc(mock_db):
    return HistoryService(mock_db)


class TestGetCandles:
    @pytest.mark.asyncio
    async def test_returns_rows_as_dicts(self, svc, mock_db):
        mock_db.pool.fetch = AsyncMock(return_value=[
            {"symbol": "VNM", "timestamp": "2026-02-07", "open": 80, "high": 81,
             "low": 79, "close": 80.5, "volume": 1000,
             "active_buy_vol": 600, "active_sell_vol": 400},
        ])
        result = await svc.get_candles("VNM", date(2026, 2, 1), date(2026, 2, 7))
        assert len(result) == 1
        assert result[0]["symbol"] == "VNM"

    @pytest.mark.asyncio
    async def test_empty_result(self, svc, mock_db):
        mock_db.pool.fetch = AsyncMock(return_value=[])
        result = await svc.get_candles("XYZ", date(2026, 1, 1), date(2026, 1, 31))
        assert result == []


class TestGetForeignFlow:
    @pytest.mark.asyncio
    async def test_returns_rows(self, svc, mock_db):
        mock_db.pool.fetch = AsyncMock(return_value=[
            {"symbol": "VNM", "timestamp": "2026-02-07", "buy_vol": 1000,
             "sell_vol": 500, "net_vol": 500, "buy_value": 80000, "sell_value": 40000},
        ])
        result = await svc.get_foreign_flow("VNM", date(2026, 2, 1), date(2026, 2, 7))
        assert len(result) == 1


class TestGetForeignFlowDailySummary:
    @pytest.mark.asyncio
    async def test_returns_aggregated(self, svc, mock_db):
        mock_db.pool.fetch = AsyncMock(return_value=[
            {"day": "2026-02-06", "buy_vol": 5000, "sell_vol": 3000,
             "net_vol": 2000, "buy_value": 400000, "sell_value": 240000},
        ])
        result = await svc.get_foreign_flow_daily_summary("VNM", days=30)
        assert len(result) == 1
        assert result[0]["net_vol"] == 2000


class TestGetTicks:
    @pytest.mark.asyncio
    async def test_returns_limited_rows(self, svc, mock_db):
        rows = [{"symbol": "VNM", "timestamp": f"t{i}", "price": 80,
                 "volume": 100, "side": "mua_chu_dong", "bid": 79.5, "ask": 80}
                for i in range(5)]
        mock_db.pool.fetch = AsyncMock(return_value=rows)
        result = await svc.get_ticks("VNM", date(2026, 2, 7), date(2026, 2, 7))
        assert len(result) == 5


class TestGetIndexHistory:
    @pytest.mark.asyncio
    async def test_returns_rows(self, svc, mock_db):
        mock_db.pool.fetch = AsyncMock(return_value=[
            {"index_name": "VN30", "timestamp": "2026-02-07",
             "value": 1200, "change_pct": 0.5, "volume": 150000000},
        ])
        result = await svc.get_index_history("VN30", date(2026, 2, 1), date(2026, 2, 7))
        assert len(result) == 1
        assert result[0]["index_name"] == "VN30"


class TestGetDerivativesHistory:
    @pytest.mark.asyncio
    async def test_returns_rows(self, svc, mock_db):
        mock_db.pool.fetch = AsyncMock(return_value=[
            {"contract": "VN30F2603", "timestamp": "2026-02-07",
             "price": 1210, "basis": 9.5, "open_interest": 50000},
        ])
        result = await svc.get_derivatives_history(
            "VN30F2603", date(2026, 2, 1), date(2026, 2, 7),
        )
        assert len(result) == 1
        assert result[0]["basis"] == 9.5


class TestPoolNotConnected:
    def test_raises_when_pool_is_none(self):
        db = MagicMock(spec=Database)
        db.pool = None
        svc = HistoryService(db)
        with pytest.raises(AssertionError, match="Database not connected"):
            _ = svc._pool

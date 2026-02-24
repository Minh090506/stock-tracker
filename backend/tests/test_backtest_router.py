"""Tests for backtest REST endpoints."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.analytics.backtest_models import (
    BacktestSummary,
    CrossCorrelationReport,
    CrossCorrelationResult,
    PatternReport,
    ThresholdBin,
    ThresholdReport,
    TimePatternEntry,
)
from app.routers.backtest_router import router

_app = FastAPI()
_app.include_router(router)
_app.state.db_available = True


@pytest.fixture
def mock_engine():
    # MagicMock base so sync methods (get_cached_report) work correctly.
    # Async methods are set explicitly.
    engine = MagicMock()
    engine.run_cross_correlation = AsyncMock()
    engine.run_threshold_analysis = AsyncMock()
    engine.run_pattern_analysis = AsyncMock()
    return engine


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _sample_correlation_report() -> CrossCorrelationReport:
    return CrossCorrelationReport(
        symbol="VN30F2603",
        date_from=datetime(2026, 2, 1),
        date_to=datetime(2026, 2, 20),
        results=[
            CrossCorrelationResult(lag_minutes=0, correlation=0.75, sample_size=100),
            CrossCorrelationResult(lag_minutes=1, correlation=0.68, sample_size=99),
        ],
        optimal_lag=0,
        optimal_correlation=0.75,
    )


def _sample_threshold_report() -> ThresholdReport:
    return ThresholdReport(
        symbol="VN30F2603",
        lookahead_minutes=5,
        date_from=datetime(2026, 2, 1),
        date_to=datetime(2026, 2, 20),
        bins=[
            ThresholdBin(
                imbalance_min=0.0, imbalance_max=0.2, sample_count=50,
                price_up_probability=0.3, avg_price_change=-0.5, avg_magnitude=0.5,
            ),
        ],
    )


def _sample_pattern_report() -> PatternReport:
    return PatternReport(
        symbol="VN30F2603",
        date_from=datetime(2026, 2, 1),
        date_to=datetime(2026, 2, 20),
        patterns=[
            TimePatternEntry(
                hour=10, session_phase="continuous",
                avg_correlation=0.65, avg_imbalance=0.52, sample_count=200,
            ),
        ],
    )


def _sample_summary() -> BacktestSummary:
    return BacktestSummary(
        computed_at=datetime(2026, 2, 24, 15, 30),
        data_days=20,
        cross_correlation=_sample_correlation_report(),
        threshold=_sample_threshold_report(),
        patterns=_sample_pattern_report(),
    )


class TestGetSummary:
    @pytest.mark.asyncio
    async def test_returns_cached_report(self, client, mock_engine):
        mock_engine.get_cached_report.return_value = _sample_summary()
        with patch("app.routers.backtest_router._get_engine", return_value=mock_engine):
            resp = await client.get("/api/backtest/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data_days"] == 20
        assert "cross_correlation" in data

    @pytest.mark.asyncio
    async def test_404_when_no_cache(self, client, mock_engine):
        mock_engine.get_cached_report.return_value = None
        with patch("app.routers.backtest_router._get_engine", return_value=mock_engine):
            resp = await client.get("/api/backtest/summary")
        assert resp.status_code == 404


class TestGetCorrelation:
    @pytest.mark.asyncio
    async def test_returns_correlation(self, client, mock_engine):
        mock_engine.run_cross_correlation.return_value = _sample_correlation_report()
        with patch("app.routers.backtest_router._get_engine", return_value=mock_engine):
            resp = await client.get("/api/backtest/correlation", params={
                "symbol": "VN30F2603", "days": 20, "max_lag": 10,
            })
        assert resp.status_code == 200
        assert resp.json()["optimal_lag"] == 0

    @pytest.mark.asyncio
    async def test_symbol_uppercased(self, client, mock_engine):
        mock_engine.run_cross_correlation.return_value = _sample_correlation_report()
        with patch("app.routers.backtest_router._get_engine", return_value=mock_engine):
            await client.get("/api/backtest/correlation", params={"symbol": "vn30f2603"})
        call_args = mock_engine.run_cross_correlation.call_args
        assert call_args[0][0] == "VN30F2603"


class TestGetThreshold:
    @pytest.mark.asyncio
    async def test_returns_threshold(self, client, mock_engine):
        mock_engine.run_threshold_analysis.return_value = _sample_threshold_report()
        with patch("app.routers.backtest_router._get_engine", return_value=mock_engine):
            resp = await client.get("/api/backtest/threshold", params={
                "symbol": "VN30F2603", "days": 20,
            })
        assert resp.status_code == 200
        assert resp.json()["lookahead_minutes"] == 5


class TestGetPatterns:
    @pytest.mark.asyncio
    async def test_returns_patterns(self, client, mock_engine):
        mock_engine.run_pattern_analysis.return_value = _sample_pattern_report()
        with patch("app.routers.backtest_router._get_engine", return_value=mock_engine):
            resp = await client.get("/api/backtest/patterns", params={
                "symbol": "VN30F2603", "days": 20,
            })
        assert resp.status_code == 200
        assert len(resp.json()["patterns"]) == 1


class TestDbUnavailable:
    @pytest.mark.asyncio
    async def test_503_when_db_unavailable(self):
        no_db_app = FastAPI()
        no_db_app.include_router(router)
        no_db_app.state.db_available = False
        transport = ASGITransport(app=no_db_app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/api/backtest/summary")
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_503_when_engine_not_initialized(self):
        no_engine_app = FastAPI()
        no_engine_app.include_router(router)
        no_engine_app.state.db_available = True
        # backtest_engine not set on app.state
        transport = ASGITransport(app=no_engine_app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/api/backtest/summary")
        assert resp.status_code == 503

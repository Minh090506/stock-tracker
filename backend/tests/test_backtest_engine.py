"""Tests for BacktestEngine — Pearson, cross-correlation, threshold, patterns."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.analytics.backtest_engine import BacktestEngine
from app.analytics.backtest_utils import pearson, session_phase


# -- Helpers -------------------------------------------------------------------

def _ts(hour: int = 10, minute: int = 0) -> datetime:
    return datetime(2026, 2, 24, hour, minute, 0)


def _make_row(
    minute: int, net_vel: float, imb: float, price: float,
    hour: int = 10,
) -> dict:
    """Build a mock DB row matching the _fetch_data output."""
    return {
        "timestamp": _ts(hour, minute),
        "net_velocity": net_vel,
        "imbalance_ratio": imb,
        "vn30f_price": price,
        "hour_of_day": hour,
        "minute_of_hour": minute,
    }


def _make_pool(rows: list[dict], trading_days: int = 10) -> MagicMock:
    """Create a mock asyncpg pool that returns given rows.

    Uses simple dict wrappers so dict(record) works across multiple calls.
    """
    pool = MagicMock()
    pool.fetchval = AsyncMock(return_value=trading_days)
    # asyncpg Records support dict() — use actual dicts as stand-ins
    pool.fetch = AsyncMock(return_value=rows)
    return pool


# -- Pearson tests -------------------------------------------------------------

class TestPearson:
    def test_perfect_positive(self):
        assert abs(pearson([1, 2, 3, 4, 5], [2, 4, 6, 8, 10]) - 1.0) < 0.001

    def test_perfect_negative(self):
        assert abs(pearson([1, 2, 3, 4, 5], [10, 8, 6, 4, 2]) + 1.0) < 0.001

    def test_insufficient_data(self):
        assert pearson([1, 2], [3, 4]) == 0.0
        assert pearson([], []) == 0.0

    def test_zero_variance(self):
        assert pearson([1, 2, 3], [5, 5, 5]) == 0.0

    def test_clamp_to_range(self):
        """Result always in [-1, 1]."""
        r = pearson([1, 2, 3, 4, 5], [1, 2, 3, 4, 5])
        assert -1.0 <= r <= 1.0


# -- Session phase tests -------------------------------------------------------

class TestSessionPhase:
    def test_ato(self):
        assert session_phase(9, 0) == "ato"
        assert session_phase(9, 14) == "ato"

    def test_continuous(self):
        assert session_phase(9, 15) == "continuous"
        assert session_phase(10, 30) == "continuous"
        assert session_phase(13, 0) == "continuous"

    def test_atc(self):
        assert session_phase(14, 30) == "atc"
        assert session_phase(14, 45) == "atc"


# -- Cross-correlation tests ---------------------------------------------------

class TestCrossCorrelation:
    @pytest.mark.asyncio
    async def test_basic_positive_correlation(self):
        # Velocity and price accelerate together (quadratic → varying deltas)
        rows = [
            _make_row(i, net_vel=float(i * 10), imb=0.6,
                      price=1300.0 + i * i * 0.05)
            for i in range(20)
        ]
        pool = _make_pool(rows)
        engine = BacktestEngine(pool)
        result = await engine.run_cross_correlation(
            "VN30F2603", _ts(9), _ts(14), max_lag=5,
        )
        assert result.symbol == "VN30F2603"
        assert len(result.results) > 0
        # Lag 0 should show positive correlation (both accelerate)
        assert result.results[0].correlation > 0

    @pytest.mark.asyncio
    async def test_empty_data_returns_empty_results(self):
        pool = _make_pool([])
        engine = BacktestEngine(pool)
        result = await engine.run_cross_correlation(
            "VN30F2603", _ts(9), _ts(14),
        )
        assert result.results == []
        assert result.optimal_lag == 0

    @pytest.mark.asyncio
    async def test_optimal_lag_found(self):
        rows = [
            _make_row(i, net_vel=float(i * 10), imb=0.5,
                      price=1300.0 + i * i * 0.03)  # quadratic for varying deltas
            for i in range(30)
        ]
        pool = _make_pool(rows)
        engine = BacktestEngine(pool)
        result = await engine.run_cross_correlation(
            "VN30F2603", _ts(9), _ts(14), max_lag=5,
        )
        assert result.optimal_lag >= 0
        assert result.optimal_correlation != 0.0


# -- Threshold analysis tests --------------------------------------------------

class TestThresholdAnalysis:
    @pytest.mark.asyncio
    async def test_bins_created(self):
        rows = [
            _make_row(i, net_vel=10.0, imb=i / 20.0, price=1300.0 + (i % 3) * 0.1)
            for i in range(20)
        ]
        pool = _make_pool(rows)
        engine = BacktestEngine(pool)
        result = await engine.run_threshold_analysis(
            "VN30F2603", _ts(9), _ts(14), lookahead=3, num_bins=5,
        )
        assert len(result.bins) == 5
        assert result.lookahead_minutes == 3
        # Each bin has valid range
        for b in result.bins:
            assert 0.0 <= b.imbalance_min <= b.imbalance_max <= 1.0

    @pytest.mark.asyncio
    async def test_probability_range(self):
        rows = [
            _make_row(i, net_vel=10.0, imb=0.5, price=1300.0 + i * 0.1)
            for i in range(15)
        ]
        pool = _make_pool(rows)
        engine = BacktestEngine(pool)
        result = await engine.run_threshold_analysis(
            "VN30F2603", _ts(9), _ts(14), lookahead=2,
        )
        for b in result.bins:
            assert 0.0 <= b.price_up_probability <= 1.0

    @pytest.mark.asyncio
    async def test_empty_data(self):
        pool = _make_pool([])
        engine = BacktestEngine(pool)
        result = await engine.run_threshold_analysis(
            "VN30F2603", _ts(9), _ts(14),
        )
        assert all(b.sample_count == 0 for b in result.bins)


# -- Pattern analysis tests ----------------------------------------------------

class TestPatternAnalysis:
    @pytest.mark.asyncio
    async def test_groups_by_hour(self):
        rows = []
        for h in [9, 10, 11]:
            for m in range(5):
                rows.append(_make_row(m + 15, net_vel=10.0, imb=0.5,
                                       price=1300.0 + m * 0.1, hour=h))
        pool = _make_pool(rows)
        engine = BacktestEngine(pool)
        result = await engine.run_pattern_analysis(
            "VN30F2603", _ts(9), _ts(14),
        )
        hours = {p.hour for p in result.patterns}
        assert 9 in hours
        assert 10 in hours

    @pytest.mark.asyncio
    async def test_session_phase_classification(self):
        rows = [
            _make_row(5, net_vel=10.0, imb=0.5, price=1300.0, hour=9),
            _make_row(6, net_vel=20.0, imb=0.6, price=1300.1, hour=9),
            _make_row(7, net_vel=30.0, imb=0.7, price=1300.2, hour=9),
            _make_row(30, net_vel=40.0, imb=0.5, price=1300.3, hour=14),
            _make_row(31, net_vel=50.0, imb=0.6, price=1300.4, hour=14),
            _make_row(32, net_vel=60.0, imb=0.7, price=1300.5, hour=14),
        ]
        pool = _make_pool(rows)
        engine = BacktestEngine(pool)
        result = await engine.run_pattern_analysis(
            "VN30F2603", _ts(9), _ts(14),
        )
        phases = {p.session_phase for p in result.patterns}
        assert "ato" in phases
        assert "atc" in phases

    @pytest.mark.asyncio
    async def test_empty_data(self):
        pool = _make_pool([])
        engine = BacktestEngine(pool)
        result = await engine.run_pattern_analysis(
            "VN30F2603", _ts(9), _ts(14),
        )
        assert result.patterns == []


# -- Daily report tests --------------------------------------------------------

class TestDailyReport:
    @pytest.mark.asyncio
    async def test_insufficient_data_returns_none(self):
        pool = _make_pool([], trading_days=3)
        engine = BacktestEngine(pool)
        result = await engine.run_daily_report("VN30F2603")
        assert result is None

    @pytest.mark.asyncio
    async def test_caches_result(self):
        rows = [
            _make_row(i, net_vel=float(i * 10), imb=0.5,
                      price=1300.0 + i * i * 0.05)  # varying deltas
            for i in range(20)
        ]
        pool = _make_pool(rows, trading_days=10)
        engine = BacktestEngine(pool)
        result = await engine.run_daily_report("VN30F2603")
        assert result is not None
        assert engine.get_cached_report() is result
        assert result.data_days == 10

    @pytest.mark.asyncio
    async def test_cache_initially_none(self):
        pool = _make_pool([])
        engine = BacktestEngine(pool)
        assert engine.get_cached_report() is None

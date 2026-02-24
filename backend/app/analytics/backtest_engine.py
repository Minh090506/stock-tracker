"""Backtest analysis engine for velocity vs VN30F price correlation.

Runs cross-correlation (lead-lag), threshold discovery, and time-of-day
pattern analysis on historical order_velocity_1m + candles_1m data.
Pre-computed daily at 15:30 VN; on-demand via REST API.
"""

import logging
import zoneinfo
from datetime import datetime, timedelta

import asyncpg

from app.analytics.backtest_models import (
    BacktestSummary,
    CrossCorrelationReport,
    CrossCorrelationResult,
    PatternReport,
    ThresholdBin,
    ThresholdReport,
    TimePatternEntry,
)
from app.analytics.backtest_queries import (
    BASKET_VELOCITY_PRICE_SQL,
    TRADING_DAYS_SQL,
    VELOCITY_PRICE_SQL,
)
from app.analytics.backtest_utils import pearson, session_phase

logger = logging.getLogger(__name__)

_VN_TZ = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")
_DEFAULT_MAX_LAG = 10
_DEFAULT_LOOKAHEAD = 5
_DEFAULT_BINS = 5
_MIN_TRADING_DAYS = 5


class BacktestEngine:
    """Historical backtest analysis on velocity vs VN30F price data."""

    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool
        self._cache: BacktestSummary | None = None

    async def _fetch_data(
        self, symbol: str, date_from: datetime, date_to: datetime,
    ) -> list[dict]:
        """Fetch joined velocity+price rows. Uses basket view for non-futures."""
        is_futures = symbol.startswith("VN30F")
        sql = VELOCITY_PRICE_SQL if is_futures else BASKET_VELOCITY_PRICE_SQL
        rows = await self._pool.fetch(sql, symbol, date_from, date_to)
        return [dict(r) for r in rows if r["vn30f_price"] is not None]

    async def get_trading_days(self, symbol: str, lookback_days: int = 30) -> int:
        """Count distinct trading days available for symbol."""
        row = await self._pool.fetchval(TRADING_DAYS_SQL, symbol, lookback_days)
        return row or 0

    # -- Cross-correlation (lead-lag) ------------------------------------------

    async def run_cross_correlation(
        self, symbol: str, date_from: datetime, date_to: datetime,
        max_lag: int = _DEFAULT_MAX_LAG,
    ) -> CrossCorrelationReport:
        rows = await self._fetch_data(symbol, date_from, date_to)
        velocities = [r["net_velocity"] or 0.0 for r in rows]
        prices = [r["vn30f_price"] for r in rows]

        price_changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
        velocities = velocities[:-1] if len(velocities) > len(price_changes) else velocities

        results: list[CrossCorrelationResult] = []
        for lag in range(max_lag + 1):
            if lag >= len(price_changes):
                break
            v = velocities[: len(price_changes) - lag]
            p = price_changes[lag:]
            n = min(len(v), len(p))
            if n < 3:
                break
            corr = pearson(v[:n], p[:n])
            results.append(CrossCorrelationResult(
                lag_minutes=lag, correlation=round(corr, 4), sample_size=n,
            ))

        optimal = max(results, key=lambda r: abs(r.correlation)) if results else None
        return CrossCorrelationReport(
            symbol=symbol, date_from=date_from, date_to=date_to, results=results,
            optimal_lag=optimal.lag_minutes if optimal else 0,
            optimal_correlation=optimal.correlation if optimal else 0.0,
        )

    # -- Threshold discovery ---------------------------------------------------

    async def run_threshold_analysis(
        self, symbol: str, date_from: datetime, date_to: datetime,
        lookahead: int = _DEFAULT_LOOKAHEAD, num_bins: int = _DEFAULT_BINS,
    ) -> ThresholdReport:
        rows = await self._fetch_data(symbol, date_from, date_to)
        prices = [r["vn30f_price"] for r in rows]
        imbalances = [r["imbalance_ratio"] for r in rows]

        pairs: list[tuple[float, float]] = []
        for i in range(len(rows) - lookahead):
            imb = imbalances[i]
            if imb is None:
                continue
            pairs.append((imb, prices[i + lookahead] - prices[i]))

        bin_width = 1.0 / num_bins
        bins: list[ThresholdBin] = []
        for b in range(num_bins):
            lo, hi = b * bin_width, (b + 1) * bin_width
            subset = [ch for imb, ch in pairs
                      if lo <= imb < hi or (b == num_bins - 1 and imb == hi)]
            count = len(subset)
            if count == 0:
                bins.append(ThresholdBin(
                    imbalance_min=round(lo, 2), imbalance_max=round(hi, 2),
                    sample_count=0, price_up_probability=0.0,
                    avg_price_change=0.0, avg_magnitude=0.0,
                ))
                continue
            ups = sum(1 for c in subset if c > 0)
            bins.append(ThresholdBin(
                imbalance_min=round(lo, 2), imbalance_max=round(hi, 2),
                sample_count=count,
                price_up_probability=round(ups / count, 4),
                avg_price_change=round(sum(subset) / count, 4),
                avg_magnitude=round(sum(abs(c) for c in subset) / count, 4),
            ))

        return ThresholdReport(
            symbol=symbol, lookahead_minutes=lookahead,
            date_from=date_from, date_to=date_to, bins=bins,
        )

    # -- Time-of-day pattern analysis ------------------------------------------

    async def run_pattern_analysis(
        self, symbol: str, date_from: datetime, date_to: datetime,
    ) -> PatternReport:
        rows = await self._fetch_data(symbol, date_from, date_to)
        prices = [r["vn30f_price"] for r in rows]

        groups: dict[tuple[int, str], list[tuple[float, float, float]]] = {}
        for i in range(1, len(rows)):
            hour = rows[i]["hour_of_day"]
            phase = session_phase(hour, rows[i]["minute_of_hour"])
            net_vel = rows[i]["net_velocity"] or 0.0
            imb = rows[i]["imbalance_ratio"] or 0.5
            groups.setdefault((hour, phase), []).append(
                (net_vel, prices[i] - prices[i - 1], imb),
            )

        patterns: list[TimePatternEntry] = []
        for (hour, phase), points in sorted(groups.items()):
            vels, deltas, imbs = [p[0] for p in points], [p[1] for p in points], [p[2] for p in points]
            patterns.append(TimePatternEntry(
                hour=hour, session_phase=phase,
                avg_correlation=round(pearson(vels, deltas), 4),
                avg_imbalance=round(sum(imbs) / len(imbs), 4),
                sample_count=len(points),
            ))

        return PatternReport(
            symbol=symbol, date_from=date_from, date_to=date_to, patterns=patterns,
        )

    # -- Daily pre-computed report ---------------------------------------------

    async def run_daily_report(self, symbol: str = "VN30F2603") -> BacktestSummary | None:
        """Run all 3 analyses for last 20 trading days. Returns None if insufficient data."""
        days = await self.get_trading_days(symbol, lookback_days=30)
        if days < _MIN_TRADING_DAYS:
            logger.warning("Insufficient data for backtest: %d/%d days", days, _MIN_TRADING_DAYS)
            return None

        now = datetime.now(_VN_TZ)
        date_from = now - timedelta(days=30)
        cross_corr = await self.run_cross_correlation(symbol, date_from, now)
        threshold = await self.run_threshold_analysis(symbol, date_from, now)
        patterns = await self.run_pattern_analysis(symbol, date_from, now)

        self._cache = BacktestSummary(
            computed_at=now, data_days=days,
            cross_correlation=cross_corr, threshold=threshold, patterns=patterns,
        )
        logger.info("Daily backtest report generated (%d trading days)", days)
        return self._cache

    def get_cached_report(self) -> BacktestSummary | None:
        return self._cache

"""Rolling Pearson correlation between order velocity and VN30F price change.

Computes correlation every minute after velocity rotation.
No numpy dependency -- uses pure Python Pearson formula.
"""

import logging
from collections import deque
from datetime import datetime

from app.models.domain import CorrelationData

logger = logging.getLogger(__name__)

_WINDOW_MIN = 15  # rolling window for correlation
_MIN_SAMPLES = 5  # minimum data points for meaningful correlation


class _CorrelationPoint:
    """Single minute data point for correlation computation."""

    __slots__ = ("net_velocity", "price_delta", "timestamp")

    def __init__(self, net_velocity: float, price_delta: float, timestamp: datetime):
        self.net_velocity = net_velocity
        self.price_delta = price_delta
        self.timestamp = timestamp


def _pearson(x: list[float], y: list[float]) -> float:
    """Pure Python Pearson correlation coefficient.

    Returns 0.0 if insufficient data or zero variance.
    """
    n = len(x)
    if n < 3:
        return 0.0
    sum_x = sum(x)
    sum_y = sum(y)
    sum_xy = sum(a * b for a, b in zip(x, y))
    sum_x2 = sum(a * a for a in x)
    sum_y2 = sum(b * b for b in y)
    num = n * sum_xy - sum_x * sum_y
    # Variance terms are non-negative in exact arithmetic, but catastrophic
    # cancellation on large near-constant inputs can round them slightly
    # negative; clamp to 0 so the sqrt stays real instead of going complex.
    var_x = max(0.0, n * sum_x2 - sum_x ** 2)
    var_y = max(0.0, n * sum_y2 - sum_y ** 2)
    den = (var_x * var_y) ** 0.5
    return max(-1.0, min(1.0, num / den)) if den > 0 else 0.0


class CorrelationEngine:
    """Rolling Pearson correlation between net velocity and VN30F price delta."""

    def __init__(self, window_minutes: int = _WINDOW_MIN):
        self._window = window_minutes
        self._points: deque[_CorrelationPoint] = deque(maxlen=window_minutes)
        self._prev_price: float | None = None

    def on_minute_tick(self, net_velocity: float, vn30f_price: float) -> None:
        """Record one minute's velocity and price for correlation.

        Price delta is computed internally from consecutive prices.
        """
        now = datetime.now()

        if self._prev_price is None:
            # First tick: store price, no delta yet
            self._prev_price = vn30f_price
            return

        price_delta = vn30f_price - self._prev_price
        self._prev_price = vn30f_price

        self._points.append(
            _CorrelationPoint(net_velocity, price_delta, now)
        )

    def get_correlation(self) -> CorrelationData:
        """Compute current rolling Pearson correlation."""
        n = len(self._points)
        if n < _MIN_SAMPLES:
            return CorrelationData(
                coefficient=0.0,
                sample_size=n,
                window_minutes=self._window,
                last_updated=datetime.now(),
            )

        x = [p.net_velocity for p in self._points]
        y = [p.price_delta for p in self._points]
        coeff = _pearson(x, y)

        return CorrelationData(
            coefficient=round(coeff, 4),
            sample_size=n,
            window_minutes=self._window,
            last_updated=datetime.now(),
        )

    def reset(self) -> None:
        """Clear all correlation data."""
        self._points.clear()
        self._prev_price = None

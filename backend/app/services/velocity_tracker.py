"""Track order velocity (vol/count/value per minute) per symbol.

Receives classified trades from MarketDataProcessor.
Maintains rolling minute-by-minute history for speed/acceleration.
Provides VN30F and VN30 basket aggregate views.
"""

import logging
from collections import deque
from datetime import datetime

from app.models.domain import VelocityData
from app.services.futures_resolver import is_vn30f_derivative

logger = logging.getLogger(__name__)

_HISTORY_MAXLEN = 60  # 60 minutes rolling
_SPEED_WINDOW_MIN = 5  # average over last N completed minutes


class _MinuteBucket:
    """Accumulator for one minute of trade data."""

    __slots__ = (
        "buy_vol", "sell_vol", "buy_count", "sell_count",
        "buy_value", "sell_value", "timestamp",
    )

    def __init__(self, timestamp: datetime):
        self.buy_vol: int = 0
        self.sell_vol: int = 0
        self.buy_count: int = 0
        self.sell_count: int = 0
        self.buy_value: float = 0.0
        self.sell_value: float = 0.0
        self.timestamp = timestamp


class VelocityTracker:
    """Per-symbol velocity tracking with minute buckets and rolling stats."""

    def __init__(self):
        # Current (incomplete) minute bucket per symbol
        self._current: dict[str, _MinuteBucket] = {}
        # Completed minute history per symbol
        self._history: dict[str, deque[_MinuteBucket]] = {}
        # Previous net velocity for acceleration calculation
        self._prev_net_velocity: dict[str, float] = {}
        # Symbols that rotated this tick (cleared each call)
        self._rotated: set[str] = set()

    def on_trade(
        self, symbol: str, volume: int, value: float,
        is_buy: bool, timestamp: datetime,
    ) -> None:
        """Accumulate a single classified trade into the current minute bucket."""
        self._rotated.clear()

        bucket = self._current.get(symbol)
        if bucket is None:
            bucket = _MinuteBucket(timestamp)
            self._current[symbol] = bucket
        elif self._should_rotate(bucket, timestamp):
            self._rotate(symbol, timestamp)
            bucket = self._current[symbol]

        if is_buy:
            bucket.buy_vol += volume
            bucket.buy_count += 1
            bucket.buy_value += value
        else:
            bucket.sell_vol += volume
            bucket.sell_count += 1
            bucket.sell_value += value

    def _should_rotate(self, bucket: _MinuteBucket, now: datetime) -> bool:
        """Check if we've crossed a minute boundary (forward only)."""
        if now <= bucket.timestamp:
            return False  # ignore backward/same-second trades
        return (
            now.minute != bucket.timestamp.minute
            or now.hour != bucket.timestamp.hour
        )

    def _rotate(self, symbol: str, now: datetime) -> None:
        """Move current bucket to history and start a new one."""
        old = self._current[symbol]
        if symbol not in self._history:
            self._history[symbol] = deque(maxlen=_HISTORY_MAXLEN)
        self._history[symbol].append(old)
        self._current[symbol] = _MinuteBucket(now)
        self._rotated.add(symbol)

    def _compute_velocity(self, symbol: str) -> VelocityData:
        """Compute rolling velocity from completed minute history."""
        history = self._history.get(symbol)
        now = datetime.now()

        if not history:
            return VelocityData(symbol=symbol, last_updated=now)

        # Use last N completed minutes (or fewer if not enough history)
        window = list(history)[-_SPEED_WINDOW_MIN:]
        n = len(window)

        total_buy_vol = sum(b.buy_vol for b in window)
        total_sell_vol = sum(b.sell_vol for b in window)
        total_buy_count = sum(b.buy_count for b in window)
        total_sell_count = sum(b.sell_count for b in window)

        buy_vol_pm = total_buy_vol / n
        sell_vol_pm = total_sell_vol / n
        net_vol_pm = buy_vol_pm - sell_vol_pm

        total_vol = total_buy_vol + total_sell_vol
        imbalance = total_buy_vol / total_vol if total_vol > 0 else 0.5

        # Acceleration: change in net velocity from previous computation
        prev_net = self._prev_net_velocity.get(symbol, 0.0)
        accel = net_vol_pm - prev_net
        self._prev_net_velocity[symbol] = net_vol_pm

        return VelocityData(
            symbol=symbol,
            buy_vol_per_min=buy_vol_pm,
            sell_vol_per_min=sell_vol_pm,
            net_vol_per_min=net_vol_pm,
            buy_count_per_min=total_buy_count / n,
            sell_count_per_min=total_sell_count / n,
            imbalance_ratio=round(imbalance, 4),
            acceleration=accel,
            last_updated=now,
        )

    def get_velocity(self, symbol: str) -> VelocityData:
        """Get velocity metrics for a single symbol."""
        return self._compute_velocity(symbol)

    def get_vn30f_velocity(self) -> VelocityData | None:
        """Get velocity for the active VN30F contract (any VN30F* symbol)."""
        for symbol in self._history:
            if is_vn30f_derivative(symbol):
                return self._compute_velocity(symbol)
        # Check current buckets too (no history yet)
        for symbol in self._current:
            if is_vn30f_derivative(symbol):
                return VelocityData(symbol=symbol, last_updated=datetime.now())
        return None

    def get_basket_velocity(self) -> VelocityData:
        """Aggregate velocity across all non-VN30F symbols (VN30 basket)."""
        now = datetime.now()
        total_buy = 0.0
        total_sell = 0.0
        total_buy_count = 0.0
        total_sell_count = 0.0
        count = 0

        for symbol, history in self._history.items():
            if is_vn30f_derivative(symbol):
                continue
            window = list(history)[-_SPEED_WINDOW_MIN:]
            n = len(window)
            if n == 0:
                continue
            total_buy += sum(b.buy_vol for b in window) / n
            total_sell += sum(b.sell_vol for b in window) / n
            total_buy_count += sum(b.buy_count for b in window) / n
            total_sell_count += sum(b.sell_count for b in window) / n
            count += 1

        net = total_buy - total_sell
        total = total_buy + total_sell
        imbalance = total_buy / total if total > 0 else 0.5

        prev_net = self._prev_net_velocity.get("_BASKET", 0.0)
        accel = net - prev_net
        self._prev_net_velocity["_BASKET"] = net

        return VelocityData(
            symbol="VN30_BASKET",
            buy_vol_per_min=total_buy,
            sell_vol_per_min=total_sell,
            net_vol_per_min=net,
            buy_count_per_min=total_buy_count,
            sell_count_per_min=total_sell_count,
            imbalance_ratio=round(imbalance, 4),
            acceleration=accel,
            last_updated=now,
        )

    def get_minute_rotated_symbols(self) -> set[str]:
        """Return symbols that completed a minute rotation on the last on_trade() call."""
        return self._rotated

    def reset(self) -> None:
        """Clear all session data."""
        self._current.clear()
        self._history.clear()
        self._prev_net_velocity.clear()
        self._rotated.clear()

"""Track foreign investor activity via SSI Channel R cumulative deltas.

SSI Channel R sends FBuyVol/FSellVol cumulative from market open.
Computes deltas between consecutive updates, rolling speed (vol/min),
acceleration (speed change rate), VN30 aggregate, and top N movers.
"""

import logging
from collections import deque
from datetime import datetime, timedelta

from app.models.domain import ForeignInvestorData, ForeignSummary
from app.models.ssi_messages import SSIForeignMessage

logger = logging.getLogger(__name__)

# Rolling window config
_SPEED_WINDOW_MIN = 5
_HISTORY_MAXLEN = 600  # ~10 min at 1 msg/sec


class _ForeignDelta:
    """Lightweight delta record for speed/acceleration calculation."""

    __slots__ = ("buy_delta", "sell_delta", "timestamp")

    def __init__(self, buy_delta: int, sell_delta: int, timestamp: datetime):
        self.buy_delta = buy_delta
        self.sell_delta = sell_delta
        self.timestamp = timestamp


class ForeignInvestorTracker:
    """Per-symbol foreign flow tracking with delta, speed, and acceleration."""

    def __init__(self):
        self._prev: dict[str, SSIForeignMessage] = {}
        self._session: dict[str, ForeignInvestorData] = {}
        self._history: dict[str, deque[_ForeignDelta]] = {}
        # Previous speed for acceleration calculation
        self._prev_speed: dict[str, tuple[float, float]] = {}

    def update(self, msg: SSIForeignMessage) -> ForeignInvestorData:
        """Process a Channel R message and return updated foreign data."""
        symbol = msg.symbol
        prev = self._prev.get(symbol)
        now = datetime.now()

        # Compute delta from cumulative values
        if prev:
            delta_buy = msg.f_buy_vol - prev.f_buy_vol
            delta_sell = msg.f_sell_vol - prev.f_sell_vol
            # Reconnect gap: cumulative dropped — treat as fresh start
            if delta_buy < 0 or delta_sell < 0:
                logger.warning(
                    "Foreign %s: negative delta (reconnect?) — resetting. "
                    "buy: %d→%d, sell: %d→%d",
                    symbol, prev.f_buy_vol, msg.f_buy_vol,
                    prev.f_sell_vol, msg.f_sell_vol,
                )
                delta_buy = max(0, delta_buy)
                delta_sell = max(0, delta_sell)
        else:
            # First message: use absolute values as initial delta
            delta_buy = msg.f_buy_vol
            delta_sell = msg.f_sell_vol

        self._prev[symbol] = msg

        # Store delta for speed calculation
        if symbol not in self._history:
            self._history[symbol] = deque(maxlen=_HISTORY_MAXLEN)
        self._history[symbol].append(
            _ForeignDelta(buy_delta=delta_buy, sell_delta=delta_sell, timestamp=now)
        )

        # Compute speed (vol/min over rolling window)
        buy_speed, sell_speed = self._compute_speed(symbol)

        # Compute acceleration (speed change rate)
        prev_buy_speed, prev_sell_speed = self._prev_speed.get(symbol, (0.0, 0.0))
        buy_accel = buy_speed - prev_buy_speed
        sell_accel = sell_speed - prev_sell_speed
        self._prev_speed[symbol] = (buy_speed, sell_speed)

        data = ForeignInvestorData(
            symbol=symbol,
            buy_volume=msg.f_buy_vol,
            sell_volume=msg.f_sell_vol,
            net_volume=msg.f_buy_vol - msg.f_sell_vol,
            buy_value=msg.f_buy_val,
            sell_value=msg.f_sell_val,
            net_value=msg.f_buy_val - msg.f_sell_val,
            total_room=msg.total_room,
            current_room=msg.current_room,
            buy_speed_per_min=buy_speed,
            sell_speed_per_min=sell_speed,
            buy_acceleration=buy_accel,
            sell_acceleration=sell_accel,
            last_updated=now,
        )
        self._session[symbol] = data
        return data

    def _compute_speed(self, symbol: str) -> tuple[float, float]:
        """Returns (buy_per_min, sell_per_min) over rolling window."""
        history = self._history.get(symbol)
        if not history:
            return (0.0, 0.0)
        cutoff = datetime.now() - timedelta(minutes=_SPEED_WINDOW_MIN)
        recent = [d for d in history if d.timestamp >= cutoff]
        if not recent:
            return (0.0, 0.0)
        total_buy = sum(d.buy_delta for d in recent)
        total_sell = sum(d.sell_delta for d in recent)
        return (total_buy / _SPEED_WINDOW_MIN, total_sell / _SPEED_WINDOW_MIN)

    def get(self, symbol: str) -> ForeignInvestorData:
        """Get foreign data for a single symbol."""
        return self._session.get(symbol, ForeignInvestorData(symbol=symbol))

    def get_all(self) -> dict[str, ForeignInvestorData]:
        """Return all tracked symbols' foreign data."""
        return dict(self._session)

    def get_summary(self) -> ForeignSummary:
        """Aggregate foreign flow across all tracked symbols."""
        items = list(self._session.values())
        total_buy_val = sum(d.buy_value for d in items)
        total_sell_val = sum(d.sell_value for d in items)
        total_buy_vol = sum(d.buy_volume for d in items)
        total_sell_vol = sum(d.sell_volume for d in items)
        # Top movers sorted by absolute net value
        by_net = sorted(items, key=lambda d: d.net_value)
        top_sell = by_net[:5]  # most negative net = top sellers
        top_buy = by_net[-5:][::-1]  # most positive net = top buyers
        return ForeignSummary(
            total_buy_value=total_buy_val,
            total_sell_value=total_sell_val,
            total_net_value=total_buy_val - total_sell_val,
            total_buy_volume=total_buy_vol,
            total_sell_volume=total_sell_vol,
            total_net_volume=total_buy_vol - total_sell_vol,
            top_buy=top_buy,
            top_sell=top_sell,
        )

    def get_top_movers(self, n: int = 5) -> tuple[list[ForeignInvestorData], list[ForeignInvestorData]]:
        """Return (top_buy, top_sell) by net value."""
        items = list(self._session.values())
        by_net = sorted(items, key=lambda d: d.net_value)
        top_sell = by_net[:n]
        top_buy = by_net[-n:][::-1]
        return top_buy, top_sell

    def reconcile(self, msg: SSIForeignMessage):
        """Re-seed cumulative baseline after reconnect (from REST snapshot)."""
        self._prev[msg.symbol] = msg

    def reset(self):
        """Clear all session data. Called at 15:00 VN daily."""
        self._prev.clear()
        self._session.clear()
        self._history.clear()
        self._prev_speed.clear()

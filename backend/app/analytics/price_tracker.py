"""PriceTracker — real-time alert generator for 4 market signal types.

Detects volume spikes, price breakouts, foreign acceleration, and basis flips.
Uses QuoteCache, ForeignInvestorTracker, DerivativesTracker as data sources.
Registers alerts via AlertService (gets dedup for free).
"""

import logging
from collections import deque
from datetime import datetime, timedelta

from app.analytics.alert_models import Alert, AlertSeverity, AlertType
from app.analytics.alert_service import AlertService
from app.services.derivatives_tracker import DerivativesTracker
from app.services.foreign_investor_tracker import ForeignInvestorTracker
from app.services.quote_cache import QuoteCache

logger = logging.getLogger(__name__)

# Volume spike: current trade vol > N× average over window
_VOL_WINDOW_MIN = 20
_VOL_SPIKE_MULTIPLIER = 3.0
_VOL_HISTORY_MAXLEN = 1200  # ~20min at 1 trade/sec

# Foreign acceleration: net_value change >30% in 5min
_FOREIGN_WINDOW_MIN = 5
_FOREIGN_CHANGE_THRESHOLD = 0.30
_FOREIGN_HISTORY_MAXLEN = 300  # ~5min at 1 msg/sec
_FOREIGN_MIN_VALUE = 1_000_000_000  # 1B VND — ignore noise on tiny values


class PriceTracker:
    """Real-time market alert generator. 4 signal types, no ML, no scoring."""

    def __init__(
        self,
        alert_service: AlertService,
        quote_cache: QuoteCache,
        foreign_tracker: ForeignInvestorTracker,
        derivatives_tracker: DerivativesTracker,
    ):
        self._alerts = alert_service
        self._quotes = quote_cache
        self._foreign = foreign_tracker
        self._derivatives = derivatives_tracker
        # Volume history: symbol → deque of (timestamp, trade_vol)
        self._vol_history: dict[str, deque[tuple[datetime, int]]] = {}
        # Foreign net_value history: symbol → deque of (timestamp, net_value)
        self._foreign_history: dict[str, deque[tuple[datetime, float]]] = {}
        # Previous basis sign for zero-crossing detection (True=premium)
        self._prev_basis_sign: bool | None = None

    # -- Public callbacks (called by MarketDataProcessor) --

    def on_trade(self, symbol: str, last_price: float, last_vol: int):
        """Called per stock trade. Checks volume spike + price breakout."""
        self._check_volume_spike(symbol, last_price, last_vol)
        self._check_price_breakout(symbol, last_price)

    def on_foreign(self, symbol: str):
        """Called per foreign update. Checks foreign acceleration."""
        self._check_foreign_acceleration(symbol)

    def on_basis_update(self):
        """Called after basis recomputation. Checks basis zero-crossing."""
        self._check_basis_flip()

    def reset(self):
        """Clear all tracking state. Called at 15:00 VN daily."""
        self._vol_history.clear()
        self._foreign_history.clear()
        self._prev_basis_sign = None

    # -- Detection rules --

    def _check_volume_spike(self, symbol: str, last_price: float, last_vol: int):
        """VOLUME_SPIKE: current trade vol > 3× avg vol over 20min window."""
        now = datetime.now()
        if symbol not in self._vol_history:
            self._vol_history[symbol] = deque(maxlen=_VOL_HISTORY_MAXLEN)
        history = self._vol_history[symbol]
        history.append((now, last_vol))

        # Need minimum sample for meaningful average
        cutoff = now - timedelta(minutes=_VOL_WINDOW_MIN)
        recent = [v for ts, v in history if ts >= cutoff]
        if len(recent) < 10:
            return

        avg_vol = sum(recent) / len(recent)
        if avg_vol <= 0:
            return

        ratio = last_vol / avg_vol
        if ratio > _VOL_SPIKE_MULTIPLIER:
            self._alerts.register_alert(Alert(
                alert_type=AlertType.VOLUME_SPIKE,
                severity=AlertSeverity.WARNING,
                symbol=symbol,
                message=f"{symbol} vol spike: {last_vol:,} ({ratio:.1f}x avg)",
                data={"last_vol": last_vol, "avg_vol": round(avg_vol, 1),
                       "ratio": round(ratio, 1), "price": last_price},
            ))

    def _check_price_breakout(self, symbol: str, last_price: float):
        """PRICE_BREAKOUT: price hits ceiling or floor."""
        _ref, ceiling, floor = self._quotes.get_price_refs(symbol)
        if ceiling <= 0 or floor <= 0:
            return

        if last_price >= ceiling:
            self._alerts.register_alert(Alert(
                alert_type=AlertType.PRICE_BREAKOUT,
                severity=AlertSeverity.CRITICAL,
                symbol=symbol,
                message=f"{symbol} hit ceiling {ceiling:,.0f}",
                data={"price": last_price, "ceiling": ceiling, "direction": "ceiling"},
            ))
        elif last_price <= floor:
            self._alerts.register_alert(Alert(
                alert_type=AlertType.PRICE_BREAKOUT,
                severity=AlertSeverity.CRITICAL,
                symbol=symbol,
                message=f"{symbol} hit floor {floor:,.0f}",
                data={"price": last_price, "floor": floor, "direction": "floor"},
            ))

    def _check_foreign_acceleration(self, symbol: str):
        """FOREIGN_ACCELERATION: net_value changes >30% in 5min window."""
        data = self._foreign.get(symbol)
        now = datetime.now()
        net_value = data.net_value

        if symbol not in self._foreign_history:
            self._foreign_history[symbol] = deque(maxlen=_FOREIGN_HISTORY_MAXLEN)
        history = self._foreign_history[symbol]
        history.append((now, net_value))

        # Find value closest to 5min ago
        cutoff = now - timedelta(minutes=_FOREIGN_WINDOW_MIN)
        past_entries = [(ts, v) for ts, v in history if ts <= cutoff]
        if not past_entries:
            return

        past_value = past_entries[-1][1]  # most recent entry before cutoff
        if abs(past_value) < _FOREIGN_MIN_VALUE:
            return

        change_pct = abs((net_value - past_value) / past_value)
        if change_pct > _FOREIGN_CHANGE_THRESHOLD:
            direction = "buying" if net_value > past_value else "selling"
            self._alerts.register_alert(Alert(
                alert_type=AlertType.FOREIGN_ACCELERATION,
                severity=AlertSeverity.WARNING,
                symbol=symbol,
                message=f"{symbol} foreign {direction} accel {change_pct:.0%} in 5min",
                data={"net_value": net_value, "prev_value": past_value,
                       "change_pct": round(change_pct, 3)},
            ))

    def _check_basis_flip(self):
        """BASIS_DIVERGENCE: futures basis crosses zero (premium↔discount)."""
        basis = self._derivatives.get_current_basis()
        if basis is None:
            return

        current_sign = basis.is_premium  # True=premium, False=discount
        if self._prev_basis_sign is not None and current_sign != self._prev_basis_sign:
            direction = "premium→discount" if not current_sign else "discount→premium"
            self._alerts.register_alert(Alert(
                alert_type=AlertType.BASIS_DIVERGENCE,
                severity=AlertSeverity.WARNING,
                symbol=basis.futures_symbol,
                message=f"Basis flipped {direction}: {basis.basis:+.2f} ({basis.basis_pct:+.3f}%)",
                data={"basis": basis.basis, "basis_pct": basis.basis_pct,
                       "futures_price": basis.futures_price, "spot_value": basis.spot_value},
            ))
        self._prev_basis_sign = current_sign

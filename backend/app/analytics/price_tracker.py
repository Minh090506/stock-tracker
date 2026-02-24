"""PriceTracker — real-time alert generator for 6 market signal types.

Detects volume spikes, price breakouts, foreign acceleration, basis flips,
velocity divergence, and imbalance extremes.
Uses QuoteCache, ForeignInvestorTracker, DerivativesTracker, VelocityTracker as data sources.
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
from app.services.velocity_tracker import VelocityTracker

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

# Velocity divergence: buy velocity surging but VN30F price flat
_VELOCITY_WINDOW_MIN = 5
_VELOCITY_SURGE_THRESHOLD = 0.50  # 50% increase in net velocity
_PRICE_FLAT_THRESHOLD = 0.001  # 0.1% price change
_VELOCITY_MIN_BASELINE = 100  # min vol/min for meaningful signal

# Imbalance extreme: buy/sell ratio thresholds
_IMBALANCE_HIGH = 3.0  # buy/sell > 3.0 = extreme buy
_IMBALANCE_LOW = 0.33  # buy/sell < 0.33 = extreme sell


class PriceTracker:
    """Real-time market alert generator. 6 signal types, no ML, no scoring."""

    def __init__(
        self,
        alert_service: AlertService,
        quote_cache: QuoteCache,
        foreign_tracker: ForeignInvestorTracker,
        derivatives_tracker: DerivativesTracker,
        velocity_tracker: VelocityTracker | None = None,
    ):
        self._alerts = alert_service
        self._quotes = quote_cache
        self._foreign = foreign_tracker
        self._derivatives = derivatives_tracker
        self._velocity = velocity_tracker
        # Volume history: symbol → deque of (timestamp, trade_vol)
        self._vol_history: dict[str, deque[tuple[datetime, int]]] = {}
        # Foreign net_value history: symbol → deque of (timestamp, net_value)
        self._foreign_history: dict[str, deque[tuple[datetime, float]]] = {}
        # Previous basis sign for zero-crossing detection (True=premium)
        self._prev_basis_sign: bool | None = None
        # Velocity divergence history: (timestamp, net_velocity, vn30f_price)
        self._velocity_history: deque[tuple[datetime, float, float]] = deque(maxlen=300)

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

    def on_velocity_update(self):
        """Called after each minute velocity rotation. Checks velocity divergence + imbalance."""
        if not self._velocity:
            return
        self._check_velocity_divergence()
        self._check_imbalance_extreme()

    def reset(self):
        """Clear all tracking state. Called at 15:00 VN daily."""
        self._vol_history.clear()
        self._foreign_history.clear()
        self._prev_basis_sign = None
        self._velocity_history.clear()

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

    def _check_velocity_divergence(self):
        """VELOCITY_DIVERGENCE: buy velocity surging but VN30F price flat."""
        vn30f_vel = self._velocity.get_vn30f_velocity()
        if not vn30f_vel:
            return

        active = self._derivatives.active_symbol if self._derivatives else None
        if not active:
            return
        vn30f_price = self._derivatives.get_futures_price(active)
        if vn30f_price <= 0:
            return

        now = datetime.now()
        self._velocity_history.append((now, vn30f_vel.net_vol_per_min, vn30f_price))

        # Need 5+ minutes of data
        cutoff = now - timedelta(minutes=_VELOCITY_WINDOW_MIN)
        past = [(ts, nv, p) for ts, nv, p in self._velocity_history if ts <= cutoff]
        if not past:
            return

        past_vel = past[-1][1]
        past_price = past[-1][2]
        current_vel = vn30f_vel.net_vol_per_min

        # Guard: need meaningful baseline velocity
        if abs(past_vel) < _VELOCITY_MIN_BASELINE:
            return

        vel_change = (current_vel - past_vel) / abs(past_vel)
        price_change = abs(vn30f_price - past_price) / past_price

        if vel_change > _VELOCITY_SURGE_THRESHOLD and price_change < _PRICE_FLAT_THRESHOLD:
            direction = "mua" if current_vel > 0 else "bán"
            symbol = active or "VN30F"
            self._alerts.register_alert(Alert(
                alert_type=AlertType.VELOCITY_DIVERGENCE,
                severity=AlertSeverity.WARNING,
                symbol=symbol,
                message=f"Velocity divergence: {direction} velocity +{vel_change:.0%} but price flat ({price_change:.2%})",
                data={
                    "net_velocity": round(current_vel, 1),
                    "prev_velocity": round(past_vel, 1),
                    "vel_change_pct": round(vel_change, 3),
                    "price_change_pct": round(price_change, 4),
                    "vn30f_price": vn30f_price,
                },
            ))

    def _check_imbalance_extreme(self):
        """IMBALANCE_EXTREME: buy/sell ratio extremely skewed."""
        vn30f_vel = self._velocity.get_vn30f_velocity()
        if not vn30f_vel:
            return

        ratio = vn30f_vel.imbalance_ratio
        # imbalance_ratio = buy/(buy+sell), convert to buy/sell ratio
        if ratio <= 0 or ratio >= 1:
            return  # avoid division by zero
        buy_sell_ratio = ratio / (1 - ratio)

        active = self._derivatives.active_symbol if self._derivatives else None
        symbol = active or "VN30F"

        if buy_sell_ratio > _IMBALANCE_HIGH:
            self._alerts.register_alert(Alert(
                alert_type=AlertType.IMBALANCE_EXTREME,
                severity=AlertSeverity.WARNING,
                symbol=symbol,
                message=f"Extreme buy imbalance: ratio {buy_sell_ratio:.1f}x ({ratio:.0%} buy)",
                data={"imbalance_ratio": round(ratio, 3),
                      "buy_sell_ratio": round(buy_sell_ratio, 1)},
            ))
        elif buy_sell_ratio < _IMBALANCE_LOW:
            sell_buy_ratio = 1 / buy_sell_ratio if buy_sell_ratio > 0 else 0
            self._alerts.register_alert(Alert(
                alert_type=AlertType.IMBALANCE_EXTREME,
                severity=AlertSeverity.WARNING,
                symbol=symbol,
                message=f"Extreme sell imbalance: ratio {sell_buy_ratio:.1f}x ({1 - ratio:.0%} sell)",
                data={"imbalance_ratio": round(ratio, 3),
                      "buy_sell_ratio": round(buy_sell_ratio, 2)},
            ))

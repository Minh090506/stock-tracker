"""Tests for velocity alert signals — VELOCITY_DIVERGENCE and IMBALANCE_EXTREME."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.analytics.alert_models import AlertSeverity, AlertType
from app.analytics.alert_service import AlertService
from app.analytics.price_tracker import PriceTracker
from app.models.domain import VelocityData
from app.services.derivatives_tracker import DerivativesTracker
from app.services.foreign_investor_tracker import ForeignInvestorTracker
from app.services.index_tracker import IndexTracker
from app.services.quote_cache import QuoteCache
from app.services.velocity_tracker import VelocityTracker


@pytest.fixture
def alert_service():
    return AlertService()


@pytest.fixture
def quote_cache():
    return QuoteCache()


@pytest.fixture
def foreign_tracker():
    return MagicMock(spec=ForeignInvestorTracker)


@pytest.fixture
def index_tracker():
    return MagicMock(spec=IndexTracker)


@pytest.fixture
def derivatives_tracker(index_tracker):
    dt = DerivativesTracker(index_tracker, QuoteCache())
    dt._active_symbol = "VN30F2603"
    dt._prices = {"VN30F2603": 1250.0}
    return dt


@pytest.fixture
def velocity_tracker():
    return MagicMock(spec=VelocityTracker)


@pytest.fixture
def tracker(alert_service, quote_cache, foreign_tracker, derivatives_tracker, velocity_tracker):
    return PriceTracker(
        alert_service=alert_service,
        quote_cache=quote_cache,
        foreign_tracker=foreign_tracker,
        derivatives_tracker=derivatives_tracker,
        velocity_tracker=velocity_tracker,
    )


# -- Velocity Divergence --

class TestVelocityDivergence:
    """VELOCITY_DIVERGENCE: buy velocity surging >50% but VN30F price flat (<0.1%)."""

    def test_divergence_triggers_when_velocity_surges_price_flat(self, tracker, alert_service, velocity_tracker):
        """Velocity +60% but price unchanged → should trigger."""
        with patch("app.analytics.price_tracker.datetime") as mock_dt:
            # Seed 5 minutes of history with baseline velocity=200
            t0 = datetime(2026, 2, 24, 10, 0, 0)
            mock_dt.now.return_value = t0
            velocity_tracker.get_vn30f_velocity.return_value = VelocityData(
                symbol="VN30F2603", net_vol_per_min=200.0, imbalance_ratio=0.6,
            )
            tracker.on_velocity_update()

            # 6 minutes later: velocity surges to 340 (+70%), price barely moves
            t1 = t0 + timedelta(minutes=6)
            mock_dt.now.return_value = t1
            velocity_tracker.get_vn30f_velocity.return_value = VelocityData(
                symbol="VN30F2603", net_vol_per_min=340.0, imbalance_ratio=0.65,
            )
            tracker.on_velocity_update()

        alerts = alert_service.get_recent_alerts(type_filter=AlertType.VELOCITY_DIVERGENCE)
        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.WARNING
        assert alerts[0].symbol == "VN30F2603"
        assert alerts[0].data["vel_change_pct"] > 0.5

    def test_divergence_not_triggered_when_price_moves(self, tracker, alert_service, velocity_tracker, derivatives_tracker):
        """Velocity surges but price also moves proportionally → should NOT trigger."""
        with patch("app.analytics.price_tracker.datetime") as mock_dt:
            t0 = datetime(2026, 2, 24, 10, 0, 0)
            mock_dt.now.return_value = t0
            velocity_tracker.get_vn30f_velocity.return_value = VelocityData(
                symbol="VN30F2603", net_vol_per_min=200.0, imbalance_ratio=0.6,
            )
            tracker.on_velocity_update()

            # 6 min later: velocity surges AND price moves significantly
            t1 = t0 + timedelta(minutes=6)
            mock_dt.now.return_value = t1
            derivatives_tracker._prices["VN30F2603"] = 1260.0  # +0.8% change
            velocity_tracker.get_vn30f_velocity.return_value = VelocityData(
                symbol="VN30F2603", net_vol_per_min=340.0, imbalance_ratio=0.65,
            )
            tracker.on_velocity_update()

        alerts = alert_service.get_recent_alerts(type_filter=AlertType.VELOCITY_DIVERGENCE)
        assert len(alerts) == 0

    def test_divergence_not_triggered_with_low_baseline_velocity(self, tracker, alert_service, velocity_tracker):
        """Baseline velocity < 100 vol/min → guard prevents alert."""
        with patch("app.analytics.price_tracker.datetime") as mock_dt:
            t0 = datetime(2026, 2, 24, 10, 0, 0)
            mock_dt.now.return_value = t0
            velocity_tracker.get_vn30f_velocity.return_value = VelocityData(
                symbol="VN30F2603", net_vol_per_min=50.0, imbalance_ratio=0.6,
            )
            tracker.on_velocity_update()

            # 6 min: big % jump but from tiny baseline
            t1 = t0 + timedelta(minutes=6)
            mock_dt.now.return_value = t1
            velocity_tracker.get_vn30f_velocity.return_value = VelocityData(
                symbol="VN30F2603", net_vol_per_min=150.0, imbalance_ratio=0.65,
            )
            tracker.on_velocity_update()

        alerts = alert_service.get_recent_alerts(type_filter=AlertType.VELOCITY_DIVERGENCE)
        assert len(alerts) == 0

    def test_divergence_not_triggered_insufficient_history(self, tracker, alert_service, velocity_tracker):
        """Only 2 min of data (need 5 min window) → should NOT trigger."""
        with patch("app.analytics.price_tracker.datetime") as mock_dt:
            t0 = datetime(2026, 2, 24, 10, 0, 0)
            mock_dt.now.return_value = t0
            velocity_tracker.get_vn30f_velocity.return_value = VelocityData(
                symbol="VN30F2603", net_vol_per_min=200.0, imbalance_ratio=0.6,
            )
            tracker.on_velocity_update()

            # Only 2 min later — not enough for 5-min window
            t1 = t0 + timedelta(minutes=2)
            mock_dt.now.return_value = t1
            velocity_tracker.get_vn30f_velocity.return_value = VelocityData(
                symbol="VN30F2603", net_vol_per_min=400.0, imbalance_ratio=0.7,
            )
            tracker.on_velocity_update()

        alerts = alert_service.get_recent_alerts(type_filter=AlertType.VELOCITY_DIVERGENCE)
        assert len(alerts) == 0

    def test_divergence_no_velocity_tracker(self, alert_service, quote_cache, foreign_tracker, derivatives_tracker):
        """PriceTracker without velocity_tracker → on_velocity_update() is a no-op."""
        pt = PriceTracker(
            alert_service=alert_service,
            quote_cache=quote_cache,
            foreign_tracker=foreign_tracker,
            derivatives_tracker=derivatives_tracker,
            velocity_tracker=None,
        )
        # Should not raise
        pt.on_velocity_update()
        assert len(alert_service.get_recent_alerts()) == 0


# -- Imbalance Extreme --

class TestImbalanceExtreme:
    """IMBALANCE_EXTREME: buy/sell ratio > 3x or < 0.33x."""

    def test_extreme_buy_imbalance_triggers(self, tracker, alert_service, velocity_tracker):
        """imbalance_ratio = 0.8 → buy/sell = 4.0x (> 3.0) → should trigger."""
        velocity_tracker.get_vn30f_velocity.return_value = VelocityData(
            symbol="VN30F2603", net_vol_per_min=300.0, imbalance_ratio=0.8,
        )
        tracker.on_velocity_update()

        alerts = alert_service.get_recent_alerts(type_filter=AlertType.IMBALANCE_EXTREME)
        assert len(alerts) == 1
        assert "buy" in alerts[0].message.lower()
        assert alerts[0].data["buy_sell_ratio"] == 4.0

    def test_extreme_sell_imbalance_triggers(self, tracker, alert_service, velocity_tracker):
        """imbalance_ratio = 0.2 → buy/sell = 0.25x (< 0.33) → should trigger."""
        velocity_tracker.get_vn30f_velocity.return_value = VelocityData(
            symbol="VN30F2603", net_vol_per_min=-300.0, imbalance_ratio=0.2,
        )
        tracker.on_velocity_update()

        alerts = alert_service.get_recent_alerts(type_filter=AlertType.IMBALANCE_EXTREME)
        assert len(alerts) == 1
        assert "sell" in alerts[0].message.lower()

    def test_moderate_ratio_no_alert(self, tracker, alert_service, velocity_tracker):
        """imbalance_ratio = 0.55 → buy/sell = 1.22x → should NOT trigger."""
        velocity_tracker.get_vn30f_velocity.return_value = VelocityData(
            symbol="VN30F2603", net_vol_per_min=50.0, imbalance_ratio=0.55,
        )
        tracker.on_velocity_update()

        alerts = alert_service.get_recent_alerts(type_filter=AlertType.IMBALANCE_EXTREME)
        assert len(alerts) == 0

    def test_exact_threshold_no_alert(self, tracker, alert_service, velocity_tracker):
        """imbalance_ratio = 0.75 → buy/sell = 3.0x exactly → NOT trigger (> not >=)."""
        velocity_tracker.get_vn30f_velocity.return_value = VelocityData(
            symbol="VN30F2603", net_vol_per_min=200.0, imbalance_ratio=0.75,
        )
        tracker.on_velocity_update()

        alerts = alert_service.get_recent_alerts(type_filter=AlertType.IMBALANCE_EXTREME)
        assert len(alerts) == 0

    def test_boundary_ratio_zero_or_one_no_alert(self, tracker, alert_service, velocity_tracker):
        """imbalance_ratio = 0 or 1 → guard prevents division by zero."""
        for ratio in [0.0, 1.0]:
            velocity_tracker.get_vn30f_velocity.return_value = VelocityData(
                symbol="VN30F2603", net_vol_per_min=200.0, imbalance_ratio=ratio,
            )
            tracker.on_velocity_update()

        alerts = alert_service.get_recent_alerts(type_filter=AlertType.IMBALANCE_EXTREME)
        assert len(alerts) == 0

    def test_no_vn30f_velocity_no_alert(self, tracker, alert_service, velocity_tracker):
        """VelocityTracker returns None for VN30F → should NOT trigger."""
        velocity_tracker.get_vn30f_velocity.return_value = None
        tracker.on_velocity_update()

        alerts = alert_service.get_recent_alerts(type_filter=AlertType.IMBALANCE_EXTREME)
        assert len(alerts) == 0


# -- Dedup --

class TestVelocityAlertDedup:
    """Same velocity alert type+symbol within 60s → second skipped."""

    def test_imbalance_deduped_within_60s(self, tracker, alert_service, velocity_tracker):
        """Two extreme buy imbalance alerts in quick succession → only first accepted."""
        velocity_tracker.get_vn30f_velocity.return_value = VelocityData(
            symbol="VN30F2603", net_vol_per_min=300.0, imbalance_ratio=0.8,
        )
        tracker.on_velocity_update()
        tracker.on_velocity_update()  # immediate repeat

        alerts = alert_service.get_recent_alerts(type_filter=AlertType.IMBALANCE_EXTREME)
        assert len(alerts) == 1


# -- Reset --

class TestVelocityReset:
    """Reset clears velocity_history."""

    def test_reset_clears_velocity_history(self, tracker):
        """After reset, _velocity_history should be empty."""
        # Add some dummy history
        tracker._velocity_history.append((datetime.now(), 200.0, 1250.0))
        assert len(tracker._velocity_history) == 1

        tracker.reset()
        assert len(tracker._velocity_history) == 0

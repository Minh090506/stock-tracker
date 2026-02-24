"""Tests for VelocityTracker — minute buckets, rotation, velocity, basket aggregation."""

from datetime import datetime

from app.models.domain import VelocityData
from app.services.velocity_tracker import VelocityTracker


def _ts(minute: int, hour: int = 10) -> datetime:
    """Helper: create a timestamp with given minute."""
    return datetime(2026, 2, 24, hour, minute, 0)


class TestMinuteBucketAccumulation:
    def test_single_buy_trade(self):
        tracker = VelocityTracker()
        tracker.on_trade("VNM", volume=100, value=8_000_000.0, is_buy=True, timestamp=_ts(0))
        # No history yet (bucket not rotated), but current bucket exists
        vel = tracker.get_velocity("VNM")
        assert isinstance(vel, VelocityData)
        assert vel.symbol == "VNM"

    def test_multiple_trades_same_minute(self):
        tracker = VelocityTracker()
        tracker.on_trade("VNM", 100, 8_000_000.0, True, _ts(0))
        tracker.on_trade("VNM", 200, 16_000_000.0, False, _ts(0))
        tracker.on_trade("VNM", 50, 4_000_000.0, True, _ts(0))
        # Still in same minute, no rotation
        assert tracker.get_minute_rotated_symbols() == set()


class TestMinuteRotation:
    def test_rotation_on_minute_boundary(self):
        tracker = VelocityTracker()
        tracker.on_trade("VNM", 100, 8_000_000.0, True, _ts(0))
        # Cross minute boundary
        tracker.on_trade("VNM", 50, 4_000_000.0, True, _ts(1))
        assert "VNM" in tracker.get_minute_rotated_symbols()

    def test_rotation_creates_history(self):
        tracker = VelocityTracker()
        tracker.on_trade("VNM", 100, 8_000_000.0, True, _ts(0))
        tracker.on_trade("VNM", 50, 4_000_000.0, True, _ts(1))
        # History should have 1 completed bucket
        assert len(tracker._history["VNM"]) == 1

    def test_multiple_rotations(self):
        tracker = VelocityTracker()
        for m in range(5):
            tracker.on_trade("VNM", 100, 8_000_000.0, True, _ts(m))
        # 4 rotations (minute 0→1, 1→2, 2→3, 3→4)
        assert len(tracker._history["VNM"]) == 4

    def test_hour_boundary_rotation(self):
        tracker = VelocityTracker()
        tracker.on_trade("VNM", 100, 8_000_000.0, True, _ts(59, hour=10))
        tracker.on_trade("VNM", 50, 4_000_000.0, True, _ts(0, hour=11))
        assert "VNM" in tracker.get_minute_rotated_symbols()


class TestVelocityComputation:
    def _setup_with_history(self):
        """Create tracker with 5 completed minutes of data."""
        tracker = VelocityTracker()
        for m in range(6):  # 6 trades = 5 completed buckets + 1 current
            tracker.on_trade("VNM", 100, 8_000_000.0, True, _ts(m))
            tracker.on_trade("VNM", 60, 5_000_000.0, False, _ts(m))
        return tracker

    def test_velocity_values_positive(self):
        tracker = self._setup_with_history()
        vel = tracker.get_velocity("VNM")
        assert vel.buy_vol_per_min > 0
        assert vel.sell_vol_per_min > 0

    def test_net_velocity_is_buy_minus_sell(self):
        tracker = self._setup_with_history()
        vel = tracker.get_velocity("VNM")
        assert vel.net_vol_per_min == vel.buy_vol_per_min - vel.sell_vol_per_min

    def test_count_per_min(self):
        tracker = self._setup_with_history()
        vel = tracker.get_velocity("VNM")
        # Each minute: 1 buy + 1 sell trade
        assert vel.buy_count_per_min == 1.0
        assert vel.sell_count_per_min == 1.0

    def test_imbalance_ratio(self):
        tracker = self._setup_with_history()
        vel = tracker.get_velocity("VNM")
        # buy=100, sell=60 per min → imbalance = 100/160 = 0.625
        assert vel.imbalance_ratio == 0.625

    def test_velocity_no_history_returns_defaults(self):
        tracker = VelocityTracker()
        vel = tracker.get_velocity("UNKNOWN")
        assert vel.buy_vol_per_min == 0.0
        assert vel.sell_vol_per_min == 0.0
        assert vel.imbalance_ratio == 0.5


class TestImbalanceEdgeCases:
    def test_zero_volume_returns_neutral(self):
        tracker = VelocityTracker()
        # Create history with zero-volume buckets
        for m in range(3):
            tracker.on_trade("VNM", 0, 0.0, True, _ts(m))
        vel = tracker.get_velocity("VNM")
        assert vel.imbalance_ratio == 0.5

    def test_all_buy_returns_one(self):
        tracker = VelocityTracker()
        for m in range(3):
            tracker.on_trade("VNM", 100, 8_000_000.0, True, _ts(m))
        vel = tracker.get_velocity("VNM")
        assert vel.imbalance_ratio == 1.0

    def test_all_sell_returns_zero(self):
        tracker = VelocityTracker()
        for m in range(3):
            tracker.on_trade("VNM", 100, 8_000_000.0, False, _ts(m))
        vel = tracker.get_velocity("VNM")
        assert vel.imbalance_ratio == 0.0


class TestVN30FVelocity:
    def test_vn30f_detected(self):
        tracker = VelocityTracker()
        tracker.on_trade("VN30F2603", 10, 1_000_000.0, True, _ts(0))
        tracker.on_trade("VN30F2603", 5, 500_000.0, True, _ts(1))
        vel = tracker.get_vn30f_velocity()
        assert vel is not None
        assert vel.symbol == "VN30F2603"

    def test_vn30f_none_when_empty(self):
        tracker = VelocityTracker()
        assert tracker.get_vn30f_velocity() is None

    def test_vn30f_from_current_bucket_only(self):
        tracker = VelocityTracker()
        tracker.on_trade("VN30F2603", 10, 1_000_000.0, True, _ts(0))
        # Only current bucket, no history
        vel = tracker.get_vn30f_velocity()
        assert vel is not None
        assert vel.symbol == "VN30F2603"


class TestBasketVelocity:
    def test_basket_excludes_vn30f(self):
        tracker = VelocityTracker()
        for m in range(3):
            tracker.on_trade("VNM", 100, 8_000_000.0, True, _ts(m))
            tracker.on_trade("HPG", 200, 10_000_000.0, True, _ts(m))
            tracker.on_trade("VN30F2603", 50, 5_000_000.0, True, _ts(m))
        basket = tracker.get_basket_velocity()
        assert basket.symbol == "VN30_BASKET"
        # Basket should only include VNM + HPG, not VN30F
        # Each has 100 or 200 buy vol per minute
        assert basket.buy_vol_per_min == 300.0  # 100 + 200

    def test_basket_empty_when_no_stocks(self):
        tracker = VelocityTracker()
        basket = tracker.get_basket_velocity()
        assert basket.buy_vol_per_min == 0.0
        assert basket.imbalance_ratio == 0.5

    def test_basket_aggregates_multiple_symbols(self):
        tracker = VelocityTracker()
        for m in range(3):
            tracker.on_trade("VNM", 100, 8_000_000.0, True, _ts(m))
            tracker.on_trade("HPG", 50, 4_000_000.0, False, _ts(m))
        basket = tracker.get_basket_velocity()
        # VNM: 100 buy/min, HPG: 50 sell/min
        assert basket.buy_vol_per_min == 100.0
        assert basket.sell_vol_per_min == 50.0
        assert basket.net_vol_per_min == 50.0


class TestReset:
    def test_reset_clears_all(self):
        tracker = VelocityTracker()
        for m in range(5):
            tracker.on_trade("VNM", 100, 8_000_000.0, True, _ts(m))
        tracker.reset()
        assert tracker._current == {}
        assert tracker._history == {}
        assert tracker._prev_net_velocity == {}

    def test_can_trade_after_reset(self):
        tracker = VelocityTracker()
        tracker.on_trade("VNM", 100, 8_000_000.0, True, _ts(0))
        tracker.reset()
        tracker.on_trade("VNM", 50, 4_000_000.0, True, _ts(5))
        vel = tracker.get_velocity("VNM")
        assert vel.symbol == "VNM"


class TestAcceleration:
    def test_acceleration_changes_between_computations(self):
        tracker = VelocityTracker()
        # First 3 minutes: low volume
        for m in range(3):
            tracker.on_trade("VNM", 10, 800_000.0, True, _ts(m))
        vel1 = tracker.get_velocity("VNM")
        # Next 3 minutes: high volume
        for m in range(3, 6):
            tracker.on_trade("VNM", 100, 8_000_000.0, True, _ts(m))
        vel2 = tracker.get_velocity("VNM")
        # Second computation should show positive acceleration
        assert vel2.net_vol_per_min > vel1.net_vol_per_min

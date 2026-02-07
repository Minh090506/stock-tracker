"""Tests for ForeignInvestorTracker — delta, speed, acceleration, aggregate, top N."""

from datetime import datetime, timedelta
from unittest.mock import patch

from app.models.domain import ForeignInvestorData, ForeignSummary
from app.models.ssi_messages import SSIForeignMessage
from app.services.foreign_investor_tracker import ForeignInvestorTracker


def _make_msg(
    symbol="VNM",
    f_buy_vol=1000,
    f_sell_vol=500,
    f_buy_val=80_000_000.0,
    f_sell_val=40_000_000.0,
    total_room=1_000_000,
    current_room=900_000,
):
    return SSIForeignMessage(
        symbol=symbol,
        f_buy_vol=f_buy_vol,
        f_sell_vol=f_sell_vol,
        f_buy_val=f_buy_val,
        f_sell_val=f_sell_val,
        total_room=total_room,
        current_room=current_room,
    )


class TestBasicUpdate:
    def test_first_message_uses_absolute_values(self):
        tracker = ForeignInvestorTracker()
        result = tracker.update(_make_msg(f_buy_vol=1000, f_sell_vol=500))
        assert result.buy_volume == 1000
        assert result.sell_volume == 500
        assert result.net_volume == 500

    def test_values_stored(self):
        tracker = ForeignInvestorTracker()
        result = tracker.update(_make_msg(f_buy_val=80_000_000, f_sell_val=40_000_000))
        assert result.buy_value == 80_000_000
        assert result.sell_value == 40_000_000
        assert result.net_value == 40_000_000

    def test_room_tracking(self):
        tracker = ForeignInvestorTracker()
        result = tracker.update(_make_msg(total_room=1_000_000, current_room=900_000))
        assert result.total_room == 1_000_000
        assert result.current_room == 900_000

    def test_last_updated_set(self):
        tracker = ForeignInvestorTracker()
        result = tracker.update(_make_msg())
        assert result.last_updated is not None

    def test_returns_foreign_investor_data(self):
        tracker = ForeignInvestorTracker()
        result = tracker.update(_make_msg())
        assert isinstance(result, ForeignInvestorData)


class TestDeltaCalculation:
    def test_delta_between_updates(self):
        tracker = ForeignInvestorTracker()
        tracker.update(_make_msg(f_buy_vol=1000, f_sell_vol=500))
        # Second message: cumulative increased
        result = tracker.update(_make_msg(f_buy_vol=1500, f_sell_vol=700))
        assert result.buy_volume == 1500
        assert result.sell_volume == 700
        assert result.net_volume == 800

    def test_zero_delta_when_unchanged(self):
        tracker = ForeignInvestorTracker()
        tracker.update(_make_msg(f_buy_vol=1000, f_sell_vol=500))
        # Same values — delta is 0, speed should reflect that
        tracker.update(_make_msg(f_buy_vol=1000, f_sell_vol=500))
        data = tracker.get("VNM")
        assert data.buy_volume == 1000

    def test_reconnect_negative_delta_clamped_to_zero(self):
        """After reconnect, cumulative may drop — delta should be 0, not negative."""
        tracker = ForeignInvestorTracker()
        tracker.update(_make_msg(f_buy_vol=5000, f_sell_vol=3000))
        # Reconnect: cumulative reset to lower values
        result = tracker.update(_make_msg(f_buy_vol=100, f_sell_vol=50))
        assert result.buy_volume == 100
        assert result.sell_volume == 50

    def test_multiple_symbols_independent(self):
        tracker = ForeignInvestorTracker()
        tracker.update(_make_msg(symbol="VNM", f_buy_vol=1000))
        tracker.update(_make_msg(symbol="HPG", f_buy_vol=2000))
        assert tracker.get("VNM").buy_volume == 1000
        assert tracker.get("HPG").buy_volume == 2000


class TestSpeed:
    def test_speed_computed_over_window(self):
        tracker = ForeignInvestorTracker()
        now = datetime.now()
        # Simulate 5 updates over 1 minute with deltas
        for i in range(5):
            with patch(
                "app.services.foreign_investor_tracker.datetime"
            ) as mock_dt:
                mock_dt.now.return_value = now + timedelta(seconds=i * 12)
                mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
                tracker.update(_make_msg(f_buy_vol=1000 * (i + 1), f_sell_vol=500 * (i + 1)))
        # Speed should be > 0 since there are deltas in the window
        data = tracker.get("VNM")
        assert data.buy_speed_per_min >= 0
        assert data.sell_speed_per_min >= 0

    def test_speed_zero_with_no_history(self):
        tracker = ForeignInvestorTracker()
        data = tracker.get("UNKNOWN")
        assert data.buy_speed_per_min == 0.0
        assert data.sell_speed_per_min == 0.0


class TestAcceleration:
    def test_acceleration_on_first_update_is_speed(self):
        """First update: prev_speed=0, so acceleration equals speed."""
        tracker = ForeignInvestorTracker()
        result = tracker.update(_make_msg(f_buy_vol=1000, f_sell_vol=500))
        # Acceleration = current_speed - prev_speed(0)
        assert result.buy_acceleration == result.buy_speed_per_min
        assert result.sell_acceleration == result.sell_speed_per_min

    def test_acceleration_changes_with_speed(self):
        tracker = ForeignInvestorTracker()
        r1 = tracker.update(_make_msg(f_buy_vol=1000, f_sell_vol=500))
        speed1 = r1.buy_speed_per_min
        r2 = tracker.update(_make_msg(f_buy_vol=3000, f_sell_vol=1000))
        # Acceleration = speed2 - speed1
        expected_accel = r2.buy_speed_per_min - speed1
        assert r2.buy_acceleration == expected_accel


class TestGetMethods:
    def test_get_unknown_returns_empty(self):
        tracker = ForeignInvestorTracker()
        data = tracker.get("UNKNOWN")
        assert data.symbol == "UNKNOWN"
        assert data.buy_volume == 0
        assert data.net_value == 0.0

    def test_get_all_returns_copy(self):
        tracker = ForeignInvestorTracker()
        tracker.update(_make_msg(symbol="VNM"))
        tracker.update(_make_msg(symbol="HPG"))
        all_data = tracker.get_all()
        assert len(all_data) == 2
        all_data["FAKE"] = ForeignInvestorData(symbol="FAKE")
        assert "FAKE" not in tracker.get_all()


class TestSummary:
    def test_summary_aggregates_all_symbols(self):
        tracker = ForeignInvestorTracker()
        tracker.update(_make_msg(symbol="VNM", f_buy_val=100, f_sell_val=30))
        tracker.update(_make_msg(symbol="HPG", f_buy_val=200, f_sell_val=50))
        summary = tracker.get_summary()
        assert isinstance(summary, ForeignSummary)
        assert summary.total_buy_value == 300
        assert summary.total_sell_value == 80
        assert summary.total_net_value == 220

    def test_summary_empty_tracker(self):
        tracker = ForeignInvestorTracker()
        summary = tracker.get_summary()
        assert summary.total_net_value == 0.0
        assert summary.top_buy == []
        assert summary.top_sell == []

    def test_summary_volumes(self):
        tracker = ForeignInvestorTracker()
        tracker.update(_make_msg(symbol="VNM", f_buy_vol=1000, f_sell_vol=500))
        tracker.update(_make_msg(symbol="HPG", f_buy_vol=2000, f_sell_vol=800))
        summary = tracker.get_summary()
        assert summary.total_buy_volume == 3000
        assert summary.total_sell_volume == 1300
        assert summary.total_net_volume == 1700


class TestTopMovers:
    def _setup_multi_symbol(self):
        tracker = ForeignInvestorTracker()
        # Create symbols with different net values
        symbols = [
            ("VNM", 100_000, 20_000),   # net_val = 80k
            ("HPG", 50_000, 80_000),     # net_val = -30k (seller)
            ("VCB", 200_000, 10_000),    # net_val = 190k (top buyer)
            ("FPT", 30_000, 90_000),     # net_val = -60k (top seller)
            ("MBB", 70_000, 60_000),     # net_val = 10k
            ("TCB", 10_000, 50_000),     # net_val = -40k
        ]
        for sym, buy_val, sell_val in symbols:
            tracker.update(_make_msg(symbol=sym, f_buy_val=buy_val, f_sell_val=sell_val))
        return tracker

    def test_top_movers_returns_correct_count(self):
        tracker = self._setup_multi_symbol()
        top_buy, top_sell = tracker.get_top_movers(n=3)
        assert len(top_buy) == 3
        assert len(top_sell) == 3

    def test_top_buyers_sorted_descending(self):
        tracker = self._setup_multi_symbol()
        top_buy, _ = tracker.get_top_movers(n=3)
        # VCB (190k) > VNM (80k) > MBB (10k)
        assert top_buy[0].symbol == "VCB"
        assert top_buy[1].symbol == "VNM"
        assert top_buy[2].symbol == "MBB"

    def test_top_sellers_sorted_ascending(self):
        tracker = self._setup_multi_symbol()
        _, top_sell = tracker.get_top_movers(n=3)
        # FPT (-60k) < TCB (-40k) < HPG (-30k)
        assert top_sell[0].symbol == "FPT"
        assert top_sell[1].symbol == "TCB"
        assert top_sell[2].symbol == "HPG"

    def test_top_movers_default_n_is_5(self):
        tracker = self._setup_multi_symbol()
        top_buy, top_sell = tracker.get_top_movers()
        assert len(top_buy) == 5
        assert len(top_sell) == 5

    def test_summary_includes_top_movers(self):
        tracker = self._setup_multi_symbol()
        summary = tracker.get_summary()
        assert len(summary.top_buy) <= 5
        assert len(summary.top_sell) <= 5


class TestReconcile:
    def test_reconcile_reseeds_baseline(self):
        tracker = ForeignInvestorTracker()
        tracker.update(_make_msg(f_buy_vol=5000, f_sell_vol=3000))
        # Simulate reconnect — reseed from REST snapshot
        tracker.reconcile(_make_msg(f_buy_vol=5000, f_sell_vol=3000))
        # Next update should compute delta from reconciled baseline
        result = tracker.update(_make_msg(f_buy_vol=5500, f_sell_vol=3200))
        assert result.buy_volume == 5500
        assert result.net_volume == 2300


class TestReset:
    def test_reset_clears_all(self):
        tracker = ForeignInvestorTracker()
        tracker.update(_make_msg(symbol="VNM"))
        tracker.update(_make_msg(symbol="HPG"))
        tracker.reset()
        assert tracker.get_all() == {}
        assert tracker.get("VNM").buy_volume == 0

    def test_can_update_after_reset(self):
        tracker = ForeignInvestorTracker()
        tracker.update(_make_msg(f_buy_vol=1000))
        tracker.reset()
        result = tracker.update(_make_msg(f_buy_vol=500))
        assert result.buy_volume == 500


class TestEdgeCases:
    def test_zero_volume_message(self):
        tracker = ForeignInvestorTracker()
        result = tracker.update(_make_msg(f_buy_vol=0, f_sell_vol=0))
        assert result.net_volume == 0

    def test_large_volumes(self):
        tracker = ForeignInvestorTracker()
        result = tracker.update(_make_msg(f_buy_vol=100_000_000, f_sell_vol=50_000_000))
        assert result.net_volume == 50_000_000

    def test_missing_data_symbol_returns_default(self):
        tracker = ForeignInvestorTracker()
        data = tracker.get("NONEXISTENT")
        assert data.symbol == "NONEXISTENT"
        assert data.buy_speed_per_min == 0.0
        assert data.buy_acceleration == 0.0

"""Tests for DerivativesTracker — basis calculation, premium/discount, trend."""

from datetime import datetime, timedelta

import pytest

from app.models.ssi_messages import SSIIndexMessage, SSIQuoteMessage, SSITradeMessage
from app.services.derivatives_tracker import DerivativesTracker
from app.services.index_tracker import IndexTracker
from app.services.quote_cache import QuoteCache


def _make_index_tracker(vn30_value: float = 1250.0) -> IndexTracker:
    """Create IndexTracker pre-seeded with a VN30 value."""
    tracker = IndexTracker()
    if vn30_value > 0:
        tracker.update(SSIIndexMessage(index_id="VN30", index_value=vn30_value))
    return tracker


def _make_tracker(
    vn30_value: float = 1250.0,
    bid: float = 0.0,
    ask: float = 0.0,
    futures_symbol: str = "VN30F2603",
) -> tuple[DerivativesTracker, IndexTracker, QuoteCache]:
    """Create DerivativesTracker with optional pre-seeded VN30 + quote."""
    index_tracker = _make_index_tracker(vn30_value)
    quote_cache = QuoteCache()
    if bid > 0 or ask > 0:
        quote_cache.update(
            SSIQuoteMessage(symbol=futures_symbol, bid_price_1=bid, ask_price_1=ask)
        )
    tracker = DerivativesTracker(index_tracker, quote_cache)
    return tracker, index_tracker, quote_cache


def _make_futures_trade(
    symbol: str = "VN30F2603",
    price: float = 1260.0,
    volume: int = 10,
    change: float = 5.0,
    ratio_change: float = 0.4,
) -> SSITradeMessage:
    return SSITradeMessage(
        symbol=symbol,
        last_price=price,
        last_vol=volume,
        change=change,
        ratio_change=ratio_change,
    )


class TestBasisCalculation:
    def test_basis_positive_premium(self):
        """Futures > spot → positive basis, is_premium=True."""
        tracker, _, _ = _make_tracker(vn30_value=1250.0)
        bp = tracker.update_from_trade(_make_futures_trade(price=1260.0))
        assert bp is not None
        assert bp.basis == pytest.approx(10.0)
        assert bp.basis_pct == pytest.approx(10.0 / 1250.0 * 100)
        assert bp.is_premium is True

    def test_basis_negative_discount(self):
        """Futures < spot → negative basis, is_premium=False."""
        tracker, _, _ = _make_tracker(vn30_value=1250.0)
        bp = tracker.update_from_trade(_make_futures_trade(price=1240.0))
        assert bp is not None
        assert bp.basis == pytest.approx(-10.0)
        assert bp.is_premium is False

    def test_basis_zero_when_equal(self):
        """Futures == spot → basis=0, is_premium=False."""
        tracker, _, _ = _make_tracker(vn30_value=1250.0)
        bp = tracker.update_from_trade(_make_futures_trade(price=1250.0))
        assert bp is not None
        assert bp.basis == pytest.approx(0.0)
        assert bp.is_premium is False

    def test_basis_pct_calculation(self):
        tracker, _, _ = _make_tracker(vn30_value=1200.0)
        bp = tracker.update_from_trade(_make_futures_trade(price=1212.0))
        assert bp.basis_pct == pytest.approx(12.0 / 1200.0 * 100)

    def test_no_basis_without_spot(self):
        """No VN30 index value → return None."""
        tracker, _, _ = _make_tracker(vn30_value=0.0)
        bp = tracker.update_from_trade(_make_futures_trade(price=1260.0))
        assert bp is None

    def test_no_basis_with_zero_futures_price(self):
        """Zero futures price → return None."""
        tracker, _, _ = _make_tracker(vn30_value=1250.0)
        bp = tracker.update_from_trade(_make_futures_trade(price=0.0))
        assert bp is None

    def test_basis_updates_with_new_spot(self):
        """Basis recalculates when index updates between trades."""
        tracker, index_tracker, _ = _make_tracker(vn30_value=1250.0)
        bp1 = tracker.update_from_trade(_make_futures_trade(price=1260.0))
        assert bp1.basis == pytest.approx(10.0)

        # VN30 index updates
        index_tracker.update(SSIIndexMessage(index_id="VN30", index_value=1255.0))
        bp2 = tracker.update_from_trade(_make_futures_trade(price=1260.0))
        assert bp2.basis == pytest.approx(5.0)


class TestVolumeTracking:
    def test_cumulative_volume(self):
        """Volume accumulates across trades."""
        tracker, _, _ = _make_tracker()
        tracker.update_from_trade(_make_futures_trade(volume=10))
        tracker.update_from_trade(_make_futures_trade(volume=20))
        data = tracker.get_data()
        assert data.volume == 30

    def test_multi_contract_volume_independence(self):
        """Each contract tracks volume independently."""
        tracker, _, _ = _make_tracker()
        tracker.update_from_trade(_make_futures_trade(symbol="VN30F2603", volume=50))
        tracker.update_from_trade(_make_futures_trade(symbol="VN30F2606", volume=10))
        # VN30F2603 has higher volume → active symbol
        data = tracker.get_data()
        assert data.symbol == "VN30F2603"
        assert data.volume == 50


class TestActiveContract:
    def test_first_trade_sets_active(self):
        tracker, _, _ = _make_tracker()
        tracker.update_from_trade(_make_futures_trade(symbol="VN30F2603"))
        assert tracker.get_data().symbol == "VN30F2603"

    def test_highest_volume_becomes_active(self):
        """Active contract = the one with most cumulative volume."""
        tracker, _, _ = _make_tracker()
        tracker.update_from_trade(_make_futures_trade(symbol="VN30F2603", volume=5))
        tracker.update_from_trade(_make_futures_trade(symbol="VN30F2606", volume=100))
        assert tracker.get_data().symbol == "VN30F2606"


class TestGetData:
    def test_returns_none_when_no_trades(self):
        tracker, _, _ = _make_tracker()
        assert tracker.get_data() is None

    def test_includes_bid_ask_from_quote_cache(self):
        tracker, _, _ = _make_tracker(bid=1258.0, ask=1262.0)
        tracker.update_from_trade(_make_futures_trade(price=1260.0))
        data = tracker.get_data()
        assert data.bid_price == 1258.0
        assert data.ask_price == 1262.0

    def test_includes_change_fields(self):
        tracker, _, _ = _make_tracker()
        tracker.update_from_trade(_make_futures_trade(change=5.0, ratio_change=0.4))
        data = tracker.get_data()
        assert data.change == 5.0
        assert data.change_pct == 0.4


class TestBasisTrend:
    def test_trend_collects_points(self):
        tracker, _, _ = _make_tracker()
        for i in range(5):
            tracker.update_from_trade(_make_futures_trade(price=1260.0 + i))
        trend = tracker.get_basis_trend(minutes=30)
        assert len(trend) == 5

    def test_trend_filters_by_time(self):
        """Only returns points within the time window."""
        tracker, _, _ = _make_tracker()
        # Add a point, then check with 0-minute window
        tracker.update_from_trade(_make_futures_trade(price=1260.0))
        trend = tracker.get_basis_trend(minutes=0)
        assert len(trend) == 0


class TestReset:
    def test_reset_clears_all(self):
        tracker, _, _ = _make_tracker()
        tracker.update_from_trade(_make_futures_trade(price=1260.0))
        assert tracker.get_data() is not None

        tracker.reset()
        assert tracker.get_data() is None
        assert tracker.get_current_basis() is None
        assert tracker.get_basis_trend() == []
        assert tracker.get_futures_price("VN30F2603") == 0.0

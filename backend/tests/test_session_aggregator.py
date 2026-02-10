"""Tests for SessionAggregator — accumulates classified trade totals."""

from datetime import datetime

from app.models.domain import ClassifiedTrade, SessionBreakdown, SessionStats, TradeType
from app.services.session_aggregator import SessionAggregator


def _make_trade(
    symbol="VNM",
    trade_type=TradeType.MUA_CHU_DONG,
    volume=100,
    value=8050000.0,
    trading_session="",
):
    return ClassifiedTrade(
        symbol=symbol,
        price=80.5,
        volume=volume,
        value=value,
        trade_type=trade_type,
        bid_price=80.0,
        ask_price=80.5,
        timestamp=datetime.now(),
        trading_session=trading_session,
    )


class TestAddTrade:
    def test_mua_accumulates(self):
        agg = SessionAggregator()
        agg.add_trade(_make_trade(trade_type=TradeType.MUA_CHU_DONG, volume=100, value=8050000))
        agg.add_trade(_make_trade(trade_type=TradeType.MUA_CHU_DONG, volume=200, value=16100000))
        stats = agg.get_stats("VNM")
        assert stats.mua_chu_dong_volume == 300
        assert stats.mua_chu_dong_value == 8050000 + 16100000

    def test_ban_accumulates(self):
        agg = SessionAggregator()
        agg.add_trade(_make_trade(trade_type=TradeType.BAN_CHU_DONG, volume=150))
        stats = agg.get_stats("VNM")
        assert stats.ban_chu_dong_volume == 150

    def test_neutral_accumulates(self):
        agg = SessionAggregator()
        agg.add_trade(_make_trade(trade_type=TradeType.NEUTRAL, volume=50))
        stats = agg.get_stats("VNM")
        assert stats.neutral_volume == 50

    def test_total_volume_is_sum(self):
        agg = SessionAggregator()
        agg.add_trade(_make_trade(trade_type=TradeType.MUA_CHU_DONG, volume=100))
        agg.add_trade(_make_trade(trade_type=TradeType.BAN_CHU_DONG, volume=200))
        agg.add_trade(_make_trade(trade_type=TradeType.NEUTRAL, volume=50))
        stats = agg.get_stats("VNM")
        assert stats.total_volume == 350

    def test_last_updated_set(self):
        agg = SessionAggregator()
        trade = _make_trade()
        agg.add_trade(trade)
        stats = agg.get_stats("VNM")
        assert stats.last_updated == trade.timestamp

    def test_returns_updated_stats(self):
        agg = SessionAggregator()
        result = agg.add_trade(_make_trade(volume=100))
        assert isinstance(result, SessionStats)
        assert result.total_volume == 100


class TestMultipleSymbols:
    def test_separate_tracking(self):
        agg = SessionAggregator()
        agg.add_trade(_make_trade(symbol="VNM", volume=100))
        agg.add_trade(_make_trade(symbol="HPG", volume=200))
        assert agg.get_stats("VNM").total_volume == 100
        assert agg.get_stats("HPG").total_volume == 200

    def test_get_all_stats(self):
        agg = SessionAggregator()
        agg.add_trade(_make_trade(symbol="VNM"))
        agg.add_trade(_make_trade(symbol="HPG"))
        agg.add_trade(_make_trade(symbol="VCB"))
        all_stats = agg.get_all_stats()
        assert len(all_stats) == 3
        assert "VNM" in all_stats
        assert "HPG" in all_stats
        assert "VCB" in all_stats

    def test_get_all_returns_copy(self):
        agg = SessionAggregator()
        agg.add_trade(_make_trade(symbol="VNM"))
        result = agg.get_all_stats()
        result["FAKE"] = SessionStats(symbol="FAKE")
        assert "FAKE" not in agg.get_all_stats()


class TestGetStats:
    def test_unknown_symbol_returns_empty(self):
        agg = SessionAggregator()
        stats = agg.get_stats("UNKNOWN")
        assert stats.symbol == "UNKNOWN"
        assert stats.total_volume == 0
        assert stats.mua_chu_dong_volume == 0
        assert stats.ban_chu_dong_volume == 0


class TestReset:
    def test_reset_clears_all(self):
        agg = SessionAggregator()
        agg.add_trade(_make_trade(symbol="VNM", volume=100))
        agg.add_trade(_make_trade(symbol="HPG", volume=200))
        agg.reset()
        assert agg.get_all_stats() == {}
        assert agg.get_stats("VNM").total_volume == 0

    def test_can_add_after_reset(self):
        agg = SessionAggregator()
        agg.add_trade(_make_trade(volume=100))
        agg.reset()
        agg.add_trade(_make_trade(volume=50))
        assert agg.get_stats("VNM").total_volume == 50


class TestEdgeCases:
    def test_zero_volume_trade(self):
        agg = SessionAggregator()
        agg.add_trade(_make_trade(volume=0))
        assert agg.get_stats("VNM").total_volume == 0

    def test_large_volume(self):
        agg = SessionAggregator()
        agg.add_trade(_make_trade(volume=10_000_000))
        assert agg.get_stats("VNM").total_volume == 10_000_000

    def test_many_trades_accumulate(self):
        agg = SessionAggregator()
        for _ in range(1000):
            agg.add_trade(_make_trade(volume=10))
        assert agg.get_stats("VNM").total_volume == 10_000


class TestSessionBreakdownModel:
    """Test SessionBreakdown domain model initialization."""

    def test_default_initialization(self):
        breakdown = SessionBreakdown()
        assert breakdown.mua_chu_dong_volume == 0
        assert breakdown.ban_chu_dong_volume == 0
        assert breakdown.neutral_volume == 0
        assert breakdown.total_volume == 0

    def test_custom_initialization(self):
        breakdown = SessionBreakdown(
            mua_chu_dong_volume=100,
            ban_chu_dong_volume=50,
            neutral_volume=25,
            total_volume=175,
        )
        assert breakdown.mua_chu_dong_volume == 100
        assert breakdown.ban_chu_dong_volume == 50
        assert breakdown.neutral_volume == 25
        assert breakdown.total_volume == 175


class TestTradingSessionRouting:
    """Test SessionAggregator routes trades to correct session buckets."""

    def test_ato_routes_to_ato_bucket(self):
        agg = SessionAggregator()
        agg.add_trade(_make_trade(trade_type=TradeType.MUA_CHU_DONG, volume=100, trading_session="ATO"))
        stats = agg.get_stats("VNM")
        assert stats.ato.mua_chu_dong_volume == 100
        assert stats.ato.total_volume == 100
        assert stats.continuous.total_volume == 0
        assert stats.atc.total_volume == 0

    def test_atc_routes_to_atc_bucket(self):
        agg = SessionAggregator()
        agg.add_trade(_make_trade(trade_type=TradeType.BAN_CHU_DONG, volume=200, trading_session="ATC"))
        stats = agg.get_stats("VNM")
        assert stats.atc.ban_chu_dong_volume == 200
        assert stats.atc.total_volume == 200
        assert stats.continuous.total_volume == 0
        assert stats.ato.total_volume == 0

    def test_continuous_routes_to_continuous_bucket(self):
        agg = SessionAggregator()
        agg.add_trade(_make_trade(trade_type=TradeType.NEUTRAL, volume=50, trading_session=""))
        stats = agg.get_stats("VNM")
        assert stats.continuous.neutral_volume == 50
        assert stats.continuous.total_volume == 50
        assert stats.ato.total_volume == 0
        assert stats.atc.total_volume == 0

    def test_mixed_sessions_accumulate_separately(self):
        agg = SessionAggregator()
        agg.add_trade(_make_trade(trade_type=TradeType.MUA_CHU_DONG, volume=100, trading_session="ATO"))
        agg.add_trade(_make_trade(trade_type=TradeType.MUA_CHU_DONG, volume=200, trading_session=""))
        agg.add_trade(_make_trade(trade_type=TradeType.MUA_CHU_DONG, volume=150, trading_session="ATC"))
        stats = agg.get_stats("VNM")
        # Overall totals
        assert stats.mua_chu_dong_volume == 450
        assert stats.total_volume == 450
        # Per-session breakdown
        assert stats.ato.mua_chu_dong_volume == 100
        assert stats.continuous.mua_chu_dong_volume == 200
        assert stats.atc.mua_chu_dong_volume == 150

    def test_all_trade_types_in_single_session(self):
        agg = SessionAggregator()
        agg.add_trade(_make_trade(trade_type=TradeType.MUA_CHU_DONG, volume=100, trading_session=""))
        agg.add_trade(_make_trade(trade_type=TradeType.BAN_CHU_DONG, volume=50, trading_session=""))
        agg.add_trade(_make_trade(trade_type=TradeType.NEUTRAL, volume=25, trading_session=""))
        stats = agg.get_stats("VNM")
        assert stats.continuous.mua_chu_dong_volume == 100
        assert stats.continuous.ban_chu_dong_volume == 50
        assert stats.continuous.neutral_volume == 25
        assert stats.continuous.total_volume == 175


class TestResetSessionBreakdowns:
    """Test reset clears session breakdowns."""

    def test_reset_clears_all_session_buckets(self):
        agg = SessionAggregator()
        agg.add_trade(_make_trade(volume=100, trading_session="ATO"))
        agg.add_trade(_make_trade(volume=200, trading_session=""))
        agg.add_trade(_make_trade(volume=150, trading_session="ATC"))
        agg.reset()
        stats = agg.get_stats("VNM")
        # All buckets should be zero
        assert stats.ato.total_volume == 0
        assert stats.continuous.total_volume == 0
        assert stats.atc.total_volume == 0
        assert stats.total_volume == 0

    def test_can_accumulate_after_reset(self):
        agg = SessionAggregator()
        agg.add_trade(_make_trade(volume=100, trading_session="ATO"))
        agg.reset()
        agg.add_trade(_make_trade(volume=50, trading_session="ATO"))
        stats = agg.get_stats("VNM")
        assert stats.ato.total_volume == 50
        assert stats.total_volume == 50


class TestSessionTotalsInvariant:
    """Verify session breakdown totals always sum to overall totals."""

    def test_session_totals_match_overall(self):
        agg = SessionAggregator()
        agg.add_trade(_make_trade(trade_type=TradeType.MUA_CHU_DONG, volume=100, trading_session="ATO"))
        agg.add_trade(_make_trade(trade_type=TradeType.BAN_CHU_DONG, volume=200, trading_session=""))
        agg.add_trade(_make_trade(trade_type=TradeType.NEUTRAL, volume=50, trading_session="ATC"))
        agg.add_trade(_make_trade(trade_type=TradeType.MUA_CHU_DONG, volume=300, trading_session=""))
        stats = agg.get_stats("VNM")
        session_sum = stats.ato.total_volume + stats.continuous.total_volume + stats.atc.total_volume
        assert session_sum == stats.total_volume


class TestClassifiedTradeTradingSession:
    """Test ClassifiedTrade includes trading_session field."""

    def test_trading_session_field_exists(self):
        trade = _make_trade(trading_session="ATO")
        assert hasattr(trade, "trading_session")
        assert trade.trading_session == "ATO"

    def test_trading_session_default_empty(self):
        trade = _make_trade()
        assert trade.trading_session == ""

    def test_trading_session_preserved_in_model(self):
        trade_ato = _make_trade(trading_session="ATO")
        trade_atc = _make_trade(trading_session="ATC")
        trade_continuous = _make_trade(trading_session="")
        assert trade_ato.trading_session == "ATO"
        assert trade_atc.trading_session == "ATC"
        assert trade_continuous.trading_session == ""

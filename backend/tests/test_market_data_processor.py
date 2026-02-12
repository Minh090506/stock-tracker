"""Tests for MarketDataProcessor — orchestrates all data processing services."""

import pytest

from app.models.domain import TradeType
from app.models.ssi_messages import (
    SSIForeignMessage,
    SSIIndexMessage,
    SSIQuoteMessage,
    SSITradeMessage,
)
from app.services.market_data_processor import MarketDataProcessor


@pytest.fixture
def proc():
    return MarketDataProcessor()


class TestHandleQuote:
    @pytest.mark.asyncio
    async def test_caches_quote(self, proc):
        await proc.handle_quote(SSIQuoteMessage(symbol="VNM", bid_price_1=80.0, ask_price_1=80.5))
        assert proc.quote_cache.get_bid_ask("VNM") == (80.0, 80.5)


class TestHandleTrade:
    @pytest.mark.asyncio
    async def test_classifies_and_aggregates(self, proc):
        await proc.handle_quote(SSIQuoteMessage(symbol="VNM", bid_price_1=80.0, ask_price_1=80.5))
        trade = SSITradeMessage(symbol="VNM", last_price=80.5, last_vol=100, trading_session="LO")
        classified, stats, bp = await proc.handle_trade(trade)
        assert classified.trade_type == TradeType.MUA_CHU_DONG
        assert stats.mua_chu_dong_volume == 100
        assert bp is None

    @pytest.mark.asyncio
    async def test_routes_futures_to_derivatives_tracker(self, proc):
        """VN30F trades go to DerivativesTracker AND are classified for persistence."""
        # Seed VN30 index so basis can be computed
        await proc.handle_index(SSIIndexMessage(index_id="VN30", index_value=1250.0))
        trade = SSITradeMessage(symbol="VN30F2603", last_price=1260.0, last_vol=10)
        classified, stats, bp = await proc.handle_trade(trade)
        assert classified is not None  # now classified for tick_data persistence
        assert stats is None
        assert bp is not None  # basis point computed
        # Verify derivatives tracker received the trade
        data = proc.derivatives_tracker.get_data()
        assert data is not None
        assert data.symbol == "VN30F2603"
        assert data.last_price == 1260.0

    @pytest.mark.asyncio
    async def test_multiple_trades_accumulate(self, proc):
        await proc.handle_quote(SSIQuoteMessage(symbol="VNM", bid_price_1=80.0, ask_price_1=80.5))
        for _ in range(3):
            await proc.handle_trade(
                SSITradeMessage(symbol="VNM", last_price=80.5, last_vol=100, trading_session="LO")
            )
        stats = proc.aggregator.get_stats("VNM")
        assert stats.mua_chu_dong_volume == 300


class TestUnifiedAPI:
    @pytest.mark.asyncio
    async def test_get_market_snapshot(self, proc):
        # Seed data across all processors
        await proc.handle_quote(SSIQuoteMessage(symbol="VNM", bid_price_1=80.0, ask_price_1=80.5))
        await proc.handle_trade(
            SSITradeMessage(symbol="VNM", last_price=80.5, last_vol=100, trading_session="LO")
        )
        await proc.handle_index(SSIIndexMessage(index_id="VN30", index_value=1250.0))
        await proc.handle_foreign(SSIForeignMessage(symbol="VNM", f_buy_vol=1000, f_buy_val=80000.0))
        await proc.handle_trade(SSITradeMessage(symbol="VN30F2603", last_price=1260.0, last_vol=10))

        snapshot = proc.get_market_snapshot()
        assert "VNM" in snapshot.quotes
        assert "VN30" in snapshot.indices
        assert snapshot.foreign is not None
        assert snapshot.derivatives is not None
        assert snapshot.derivatives.symbol == "VN30F2603"

    @pytest.mark.asyncio
    async def test_get_foreign_summary(self, proc):
        await proc.handle_foreign(SSIForeignMessage(symbol="VNM", f_buy_vol=500, f_buy_val=40000.0))
        summary = proc.get_foreign_summary()
        assert summary.total_buy_volume == 500

    @pytest.mark.asyncio
    async def test_get_trade_analysis(self, proc):
        await proc.handle_quote(SSIQuoteMessage(symbol="VNM", bid_price_1=80.0, ask_price_1=80.5))
        await proc.handle_trade(
            SSITradeMessage(symbol="VNM", last_price=80.5, last_vol=100, trading_session="LO")
        )
        stats = proc.get_trade_analysis("VNM")
        assert stats.mua_chu_dong_volume == 100

    def test_get_trade_analysis_unknown_symbol(self, proc):
        stats = proc.get_trade_analysis("UNKNOWN")
        assert stats.total_volume == 0

    @pytest.mark.asyncio
    async def test_get_derivatives_data(self, proc):
        await proc.handle_index(SSIIndexMessage(index_id="VN30", index_value=1250.0))
        await proc.handle_trade(SSITradeMessage(symbol="VN30F2603", last_price=1260.0, last_vol=10))
        data = proc.get_derivatives_data()
        assert data is not None
        assert data.basis == pytest.approx(10.0)

    def test_get_derivatives_data_none_when_empty(self, proc):
        assert proc.get_derivatives_data() is None


class TestSubscribers:
    def test_subscribe_and_unsubscribe(self, proc):
        cb = lambda: None  # noqa: E731
        proc.subscribe(cb)
        assert len(proc._subscribers) == 1
        proc.unsubscribe(cb)
        assert len(proc._subscribers) == 0


class TestResetSession:
    @pytest.mark.asyncio
    async def test_reset_clears_aggregator(self, proc):
        await proc.handle_quote(SSIQuoteMessage(symbol="VNM", bid_price_1=80.0, ask_price_1=80.5))
        await proc.handle_trade(
            SSITradeMessage(symbol="VNM", last_price=80.5, last_vol=100, trading_session="LO")
        )
        proc.reset_session()
        assert proc.aggregator.get_stats("VNM").total_volume == 0

    @pytest.mark.asyncio
    async def test_reset_preserves_quote_cache(self, proc):
        """Quote cache should NOT be reset — quotes persist across sessions."""
        await proc.handle_quote(SSIQuoteMessage(symbol="VNM", bid_price_1=80.0, ask_price_1=80.5))
        proc.reset_session()
        assert proc.quote_cache.get_bid_ask("VNM") == (80.0, 80.5)

    @pytest.mark.asyncio
    async def test_reset_clears_derivatives(self, proc):
        await proc.handle_index(SSIIndexMessage(index_id="VN30", index_value=1250.0))
        await proc.handle_trade(SSITradeMessage(symbol="VN30F2603", last_price=1260.0, last_vol=10))
        assert proc.get_derivatives_data() is not None
        proc.reset_session()
        assert proc.get_derivatives_data() is None

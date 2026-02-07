"""Tests for MarketDataProcessor — orchestrates quote cache, classifier, aggregator."""

import pytest

from app.models.domain import TradeType
from app.models.ssi_messages import SSIQuoteMessage, SSITradeMessage
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
        # Pre-cache quote
        await proc.handle_quote(SSIQuoteMessage(symbol="VNM", bid_price_1=80.0, ask_price_1=80.5))
        # Trade at ask → MUA_CHU_DONG
        trade = SSITradeMessage(symbol="VNM", last_price=80.5, last_vol=100, trading_session="LO")
        classified, stats = await proc.handle_trade(trade)
        assert classified.trade_type == TradeType.MUA_CHU_DONG
        assert stats.mua_chu_dong_volume == 100

    @pytest.mark.asyncio
    async def test_skips_futures(self, proc):
        trade = SSITradeMessage(symbol="VN30F2603", last_price=1300.0, last_vol=10)
        classified, stats = await proc.handle_trade(trade)
        assert classified is None
        assert stats is None

    @pytest.mark.asyncio
    async def test_multiple_trades_accumulate(self, proc):
        await proc.handle_quote(SSIQuoteMessage(symbol="VNM", bid_price_1=80.0, ask_price_1=80.5))
        for _ in range(3):
            await proc.handle_trade(
                SSITradeMessage(symbol="VNM", last_price=80.5, last_vol=100, trading_session="LO")
            )
        stats = proc.aggregator.get_stats("VNM")
        assert stats.mua_chu_dong_volume == 300


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

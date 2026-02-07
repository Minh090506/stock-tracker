"""Integration test — wire MarketDataProcessor with simulated SSI stream.

Simulates 100+ ticks across multiple symbols and channels,
verifying all processors update correctly and get_market_snapshot()
returns complete, consistent data.
"""

import random

import pytest

from app.models.ssi_messages import (
    SSIForeignMessage,
    SSIIndexMessage,
    SSIQuoteMessage,
    SSITradeMessage,
)
from app.services.market_data_processor import MarketDataProcessor

# Test symbols
VN30_STOCKS = ["VNM", "VHM", "VIC", "HPG", "MSN"]
FUTURES_SYMBOL = "VN30F2603"


def _random_price(base: float, spread: float = 2.0) -> float:
    return round(base + random.uniform(-spread, spread), 1)


class TestMultiChannelIntegration:
    """Simulate realistic market data flow across all channels."""

    @pytest.mark.asyncio
    async def test_100_ticks_across_all_channels(self):
        """Simulate 100+ ticks, verify all processors update."""
        proc = MarketDataProcessor()
        random.seed(42)  # deterministic

        # Phase 1: Seed quotes for all stocks (bid/ask cache)
        for symbol in VN30_STOCKS:
            base = random.uniform(50, 150)
            await proc.handle_quote(
                SSIQuoteMessage(
                    symbol=symbol,
                    bid_price_1=round(base, 1),
                    ask_price_1=round(base + 0.5, 1),
                    ref_price=round(base + 0.2, 1),
                    ceiling=round(base * 1.07, 1),
                    floor=round(base * 0.93, 1),
                )
            )

        # Seed futures quote
        await proc.handle_quote(
            SSIQuoteMessage(
                symbol=FUTURES_SYMBOL, bid_price_1=1258.0, ask_price_1=1262.0
            )
        )

        # Phase 2: Seed VN30 index
        await proc.handle_index(
            SSIIndexMessage(
                index_id="VN30",
                index_value=1250.0,
                prior_index_value=1245.0,
                change=5.0,
                ratio_change=0.4,
                advances=15,
                declines=10,
                no_changes=5,
            )
        )
        await proc.handle_index(
            SSIIndexMessage(
                index_id="VNINDEX",
                index_value=1280.0,
                prior_index_value=1275.0,
                change=5.0,
                ratio_change=0.39,
                advances=200,
                declines=150,
                no_changes=50,
            )
        )

        # Phase 3: Fire 100 trade ticks across stocks + futures
        trade_count = 0
        for _ in range(80):
            symbol = random.choice(VN30_STOCKS)
            bid, ask = proc.quote_cache.get_bid_ask(symbol)
            # Vary price around bid/ask
            price = random.choice([bid, ask, (bid + ask) / 2])
            await proc.handle_trade(
                SSITradeMessage(
                    symbol=symbol,
                    last_price=price,
                    last_vol=random.randint(10, 500),
                    trading_session="LO",
                )
            )
            trade_count += 1

        # 20 futures trades
        for _ in range(20):
            await proc.handle_trade(
                SSITradeMessage(
                    symbol=FUTURES_SYMBOL,
                    last_price=_random_price(1260.0, 5.0),
                    last_vol=random.randint(1, 50),
                    change=random.uniform(-3, 8),
                    ratio_change=random.uniform(-0.2, 0.6),
                )
            )
            trade_count += 1

        assert trade_count == 100

        # Phase 4: Foreign investor updates
        for symbol in VN30_STOCKS:
            await proc.handle_foreign(
                SSIForeignMessage(
                    symbol=symbol,
                    f_buy_vol=random.randint(100, 5000),
                    f_sell_vol=random.randint(100, 5000),
                    f_buy_val=random.uniform(10000, 500000),
                    f_sell_val=random.uniform(10000, 500000),
                    total_room=1000000,
                    current_room=random.randint(500000, 999000),
                )
            )

        # === Verify all processors ===

        # 1. Trade classification: all 5 stocks should have stats
        all_stats = proc.aggregator.get_all_stats()
        assert len(all_stats) == len(VN30_STOCKS)
        for symbol in VN30_STOCKS:
            stats = all_stats[symbol]
            assert stats.total_volume > 0
            # Volume breakdown should sum to total
            vol_sum = (
                stats.mua_chu_dong_volume
                + stats.ban_chu_dong_volume
                + stats.neutral_volume
            )
            assert vol_sum == stats.total_volume

        # 2. Index tracker: VN30 and VNINDEX present
        indices = proc.index_tracker.get_all()
        assert "VN30" in indices
        assert "VNINDEX" in indices
        assert indices["VN30"].value == 1250.0
        assert indices["VN30"].advance_ratio == pytest.approx(15 / 25)

        # 3. Foreign tracker: all 5 stocks tracked
        foreign_all = proc.foreign_tracker.get_all()
        assert len(foreign_all) == len(VN30_STOCKS)
        summary = proc.get_foreign_summary()
        assert summary.total_buy_volume > 0

        # 4. Derivatives tracker: futures trades processed
        deriv = proc.get_derivatives_data()
        assert deriv is not None
        assert deriv.symbol == FUTURES_SYMBOL
        assert deriv.volume > 0
        assert deriv.last_price > 0
        # Basis should be computed (VN30 was seeded)
        basis = proc.derivatives_tracker.get_current_basis()
        assert basis is not None
        assert basis.futures_symbol == FUTURES_SYMBOL

        # 5. Unified snapshot: everything present
        snapshot = proc.get_market_snapshot()
        assert len(snapshot.quotes) == len(VN30_STOCKS)
        assert len(snapshot.indices) == 2
        assert snapshot.foreign is not None
        assert snapshot.derivatives is not None

    @pytest.mark.asyncio
    async def test_snapshot_empty_on_fresh_processor(self):
        """Fresh processor returns valid but empty snapshot."""
        proc = MarketDataProcessor()
        snapshot = proc.get_market_snapshot()
        assert len(snapshot.quotes) == 0
        assert len(snapshot.indices) == 0
        assert snapshot.foreign is not None  # ForeignSummary with zeros
        assert snapshot.derivatives is None

    @pytest.mark.asyncio
    async def test_reset_then_resume(self):
        """After reset, new data accumulates fresh."""
        proc = MarketDataProcessor()

        # Seed and process
        await proc.handle_quote(SSIQuoteMessage(symbol="VNM", bid_price_1=80.0, ask_price_1=80.5))
        await proc.handle_trade(
            SSITradeMessage(symbol="VNM", last_price=80.5, last_vol=100, trading_session="LO")
        )
        await proc.handle_index(SSIIndexMessage(index_id="VN30", index_value=1250.0))
        await proc.handle_trade(
            SSITradeMessage(symbol="VN30F2603", last_price=1260.0, last_vol=10)
        )

        # Reset
        proc.reset_session()
        assert proc.aggregator.get_stats("VNM").total_volume == 0
        assert proc.get_derivatives_data() is None

        # Resume with new data
        await proc.handle_trade(
            SSITradeMessage(symbol="VNM", last_price=80.0, last_vol=50, trading_session="LO")
        )
        stats = proc.aggregator.get_stats("VNM")
        assert stats.total_volume == 50
        # Quote cache persists — classification still works
        assert stats.ban_chu_dong_volume == 50

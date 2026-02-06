"""Tests for Pydantic models — SSI messages and domain models."""

from datetime import datetime

import pytest

from app.models.ssi_messages import (
    SSIBarMessage,
    SSIForeignMessage,
    SSIIndexMessage,
    SSIQuoteMessage,
    SSITradeMessage,
)
from app.models.domain import (
    BasisPoint,
    ClassifiedTrade,
    ForeignInvestorData,
    IndexData,
    SessionStats,
    TradeType,
)


class TestSSITradeMessage:
    def test_defaults(self):
        msg = SSITradeMessage()
        assert msg.symbol == ""
        assert msg.last_price == 0.0
        assert msg.last_vol == 0

    def test_full_construction(self):
        msg = SSITradeMessage(
            symbol="VNM", exchange="HOSE", last_price=85000,
            last_vol=100, total_vol=50000, total_val=4.25e9,
            change=1500, ratio_change=1.8, trading_session="LO",
        )
        assert msg.symbol == "VNM"
        assert msg.last_vol == 100  # per-trade, NOT cumulative


class TestSSIQuoteMessage:
    def test_defaults(self):
        msg = SSIQuoteMessage()
        assert msg.bid_price_1 == 0.0
        assert msg.ask_vol_1 == 0

    def test_three_levels(self):
        msg = SSIQuoteMessage(
            symbol="HPG", bid_price_1=25400, bid_vol_1=1000,
            bid_price_2=25300, bid_vol_2=2000,
            bid_price_3=25200, bid_vol_3=3000,
        )
        assert msg.bid_price_3 == 25200
        assert msg.bid_vol_3 == 3000


class TestSSIForeignMessage:
    def test_cumulative_values(self):
        msg = SSIForeignMessage(
            symbol="VCB", f_buy_vol=500, f_sell_vol=300,
            f_buy_val=50e6, f_sell_val=30e6,
            total_room=100000, current_room=95000,
        )
        assert msg.f_buy_vol == 500
        assert msg.current_room == 95000


class TestSSIIndexMessage:
    def test_index_snapshot(self):
        msg = SSIIndexMessage(
            index_id="VN30", index_value=1234.56,
            prior_index_value=1230.0, change=4.56, ratio_change=0.37,
            advances=20, declines=8, no_changes=2,
        )
        assert msg.index_id == "VN30"
        assert msg.advances == 20


class TestSSIBarMessage:
    def test_ohlcv(self):
        msg = SSIBarMessage(
            symbol="VNM", time="14:30:00",
            open=84000, high=85500, low=83500, close=85000, volume=100000,
        )
        assert msg.high == 85500
        assert msg.volume == 100000


class TestTradeType:
    def test_enum_values(self):
        assert TradeType.MUA_CHU_DONG == "mua_chu_dong"
        assert TradeType.BAN_CHU_DONG == "ban_chu_dong"
        assert TradeType.NEUTRAL == "neutral"


class TestClassifiedTrade:
    def test_active_buy(self):
        trade = ClassifiedTrade(
            symbol="VNM", price=85000, volume=100, value=8500000,
            trade_type=TradeType.MUA_CHU_DONG,
            bid_price=84900, ask_price=85000,
            timestamp=datetime(2026, 2, 6, 10, 30),
        )
        assert trade.trade_type == TradeType.MUA_CHU_DONG
        assert trade.volume == 100


class TestSessionStats:
    def test_defaults(self):
        stats = SessionStats(symbol="HPG")
        assert stats.mua_chu_dong_volume == 0
        assert stats.ban_chu_dong_volume == 0
        assert stats.last_updated is None

    def test_with_values(self):
        now = datetime.now()
        stats = SessionStats(
            symbol="HPG", mua_chu_dong_volume=5000,
            ban_chu_dong_volume=3000, total_volume=9000,
            last_updated=now,
        )
        assert stats.total_volume == 9000
        assert stats.last_updated == now


class TestForeignInvestorData:
    def test_net_calculation_stored(self):
        data = ForeignInvestorData(
            symbol="VCB", buy_volume=500, sell_volume=300, net_volume=200,
        )
        assert data.net_volume == 200

    def test_speed_defaults_zero(self):
        data = ForeignInvestorData(symbol="FPT")
        assert data.buy_speed_per_min == 0.0
        assert data.sell_speed_per_min == 0.0


class TestIndexData:
    def test_snapshot(self):
        data = IndexData(
            index_id="VNINDEX", value=1280.5, prior_value=1275.0,
            change=5.5, ratio_change=0.43,
        )
        assert data.index_id == "VNINDEX"
        assert data.change == 5.5


class TestBasisPoint:
    def test_premium(self):
        bp = BasisPoint(
            timestamp=datetime.now(), futures_symbol="VN30F2602",
            futures_price=1240.0, spot_value=1234.56,
            basis=5.44, is_premium=True,
        )
        assert bp.is_premium is True
        assert bp.basis == 5.44

    def test_discount(self):
        bp = BasisPoint(
            timestamp=datetime.now(), futures_symbol="VN30F2602",
            futures_price=1230.0, spot_value=1234.56,
            basis=-4.56, is_premium=False,
        )
        assert bp.is_premium is False
        assert bp.basis == -4.56

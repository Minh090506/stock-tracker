"""Tests for TradeClassifier — active buy/sell classification logic."""

from app.models.domain import TradeType
from app.models.ssi_messages import SSIQuoteMessage, SSITradeMessage
from app.services.quote_cache import QuoteCache
from app.services.trade_classifier import TradeClassifier


def _make_classifier_with_quote(symbol="VNM", bid=80.0, ask=80.5):
    """Helper: create classifier with a pre-cached quote."""
    cache = QuoteCache()
    cache.update(SSIQuoteMessage(symbol=symbol, bid_price_1=bid, ask_price_1=ask))
    return TradeClassifier(cache)


def _make_trade(symbol="VNM", price=80.5, volume=100, session="LO"):
    return SSITradeMessage(
        symbol=symbol, last_price=price, last_vol=volume, trading_session=session,
    )


class TestClassifyActiveBuy:
    def test_price_at_ask_is_mua(self):
        c = _make_classifier_with_quote(bid=80.0, ask=80.5)
        result = c.classify(_make_trade(price=80.5))
        assert result.trade_type == TradeType.MUA_CHU_DONG

    def test_price_above_ask_is_mua(self):
        c = _make_classifier_with_quote(bid=80.0, ask=80.5)
        result = c.classify(_make_trade(price=81.0))
        assert result.trade_type == TradeType.MUA_CHU_DONG

    def test_mua_volume_is_last_vol(self):
        c = _make_classifier_with_quote(bid=80.0, ask=80.5)
        result = c.classify(_make_trade(price=80.5, volume=500))
        assert result.volume == 500

    def test_mua_value_calculation(self):
        c = _make_classifier_with_quote(bid=80.0, ask=80.5)
        result = c.classify(_make_trade(price=80.5, volume=100))
        # value = price * volume * 1000 (price in 1000 VND)
        assert result.value == 80.5 * 100 * 1000


class TestClassifyActiveSell:
    def test_price_at_bid_is_ban(self):
        c = _make_classifier_with_quote(bid=80.0, ask=80.5)
        result = c.classify(_make_trade(price=80.0))
        assert result.trade_type == TradeType.BAN_CHU_DONG

    def test_price_below_bid_is_ban(self):
        c = _make_classifier_with_quote(bid=80.0, ask=80.5)
        result = c.classify(_make_trade(price=79.5))
        assert result.trade_type == TradeType.BAN_CHU_DONG


class TestClassifyNeutral:
    def test_mid_spread_is_neutral(self):
        c = _make_classifier_with_quote(bid=80.0, ask=80.5)
        result = c.classify(_make_trade(price=80.2))
        assert result.trade_type == TradeType.NEUTRAL

    def test_no_cached_quote_is_neutral(self):
        """If no quote cached yet (first trade before quote), classify as neutral."""
        cache = QuoteCache()
        c = TradeClassifier(cache)
        result = c.classify(_make_trade(price=80.0))
        assert result.trade_type == TradeType.NEUTRAL

    def test_zero_bid_ask_is_neutral(self):
        c = _make_classifier_with_quote(bid=0.0, ask=0.0)
        result = c.classify(_make_trade(price=80.0))
        assert result.trade_type == TradeType.NEUTRAL


class TestAuctionSessions:
    def test_ato_always_neutral(self):
        c = _make_classifier_with_quote(bid=80.0, ask=80.5)
        result = c.classify(_make_trade(price=80.5, session="ATO"))
        assert result.trade_type == TradeType.NEUTRAL

    def test_atc_always_neutral(self):
        c = _make_classifier_with_quote(bid=80.0, ask=80.5)
        result = c.classify(_make_trade(price=80.0, session="ATC"))
        assert result.trade_type == TradeType.NEUTRAL

    def test_ato_preserves_volume(self):
        """ATO auction volume should still be recorded (just not classified)."""
        c = _make_classifier_with_quote(bid=80.0, ask=80.5)
        result = c.classify(_make_trade(price=80.5, volume=10000, session="ATO"))
        assert result.volume == 10000


class TestClassifyOutputFields:
    def test_output_has_all_fields(self):
        c = _make_classifier_with_quote(bid=80.0, ask=80.5)
        result = c.classify(_make_trade(symbol="VNM", price=80.5, volume=200))
        assert result.symbol == "VNM"
        assert result.price == 80.5
        assert result.volume == 200
        assert result.bid_price == 80.0
        assert result.ask_price == 80.5
        assert result.timestamp is not None

    def test_different_symbols_use_own_quotes(self):
        cache = QuoteCache()
        cache.update(SSIQuoteMessage(symbol="VNM", bid_price_1=80.0, ask_price_1=80.5))
        cache.update(SSIQuoteMessage(symbol="HPG", bid_price_1=25.0, ask_price_1=25.5))
        c = TradeClassifier(cache)

        vnm = c.classify(_make_trade(symbol="VNM", price=80.5))
        hpg = c.classify(_make_trade(symbol="HPG", price=25.0))
        assert vnm.trade_type == TradeType.MUA_CHU_DONG
        assert hpg.trade_type == TradeType.BAN_CHU_DONG

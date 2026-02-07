"""Tests for QuoteCache — bid/ask caching from SSI Quote messages."""

from app.models.ssi_messages import SSIQuoteMessage
from app.services.quote_cache import QuoteCache


class TestQuoteCacheUpdate:
    def test_update_stores_quote(self):
        cache = QuoteCache()
        q = SSIQuoteMessage(symbol="VNM", bid_price_1=80.0, ask_price_1=80.5)
        cache.update(q)
        assert cache.get_quote("VNM") is q

    def test_update_overwrites_previous(self):
        cache = QuoteCache()
        cache.update(SSIQuoteMessage(symbol="VNM", bid_price_1=80.0))
        cache.update(SSIQuoteMessage(symbol="VNM", bid_price_1=81.0))
        assert cache.get_quote("VNM").bid_price_1 == 81.0

    def test_update_multiple_symbols(self):
        cache = QuoteCache()
        cache.update(SSIQuoteMessage(symbol="VNM", bid_price_1=80.0))
        cache.update(SSIQuoteMessage(symbol="HPG", bid_price_1=25.0))
        assert cache.get_quote("VNM").bid_price_1 == 80.0
        assert cache.get_quote("HPG").bid_price_1 == 25.0


class TestGetBidAsk:
    def test_returns_bid_ask(self):
        cache = QuoteCache()
        cache.update(SSIQuoteMessage(symbol="VNM", bid_price_1=80.0, ask_price_1=80.5))
        assert cache.get_bid_ask("VNM") == (80.0, 80.5)

    def test_returns_zeros_for_unknown_symbol(self):
        cache = QuoteCache()
        assert cache.get_bid_ask("UNKNOWN") == (0.0, 0.0)

    def test_returns_zeros_for_empty_cache(self):
        cache = QuoteCache()
        assert cache.get_bid_ask("VNM") == (0.0, 0.0)


class TestGetPriceRefs:
    def test_returns_ref_ceiling_floor(self):
        cache = QuoteCache()
        cache.update(SSIQuoteMessage(
            symbol="VNM", ref_price=82.0, ceiling=87.7, floor=76.3,
        ))
        assert cache.get_price_refs("VNM") == (82.0, 87.7, 76.3)

    def test_returns_zeros_for_unknown(self):
        cache = QuoteCache()
        assert cache.get_price_refs("UNKNOWN") == (0.0, 0.0, 0.0)


class TestGetAll:
    def test_returns_all_cached(self):
        cache = QuoteCache()
        cache.update(SSIQuoteMessage(symbol="VNM"))
        cache.update(SSIQuoteMessage(symbol="HPG"))
        result = cache.get_all()
        assert len(result) == 2
        assert "VNM" in result
        assert "HPG" in result

    def test_returns_copy(self):
        cache = QuoteCache()
        cache.update(SSIQuoteMessage(symbol="VNM"))
        result = cache.get_all()
        result["NEW"] = SSIQuoteMessage(symbol="NEW")
        assert "NEW" not in cache.get_all()

    def test_empty_cache(self):
        cache = QuoteCache()
        assert cache.get_all() == {}


class TestClear:
    def test_clears_all(self):
        cache = QuoteCache()
        cache.update(SSIQuoteMessage(symbol="VNM"))
        cache.update(SSIQuoteMessage(symbol="HPG"))
        cache.clear()
        assert cache.get_all() == {}
        assert cache.get_quote("VNM") is None

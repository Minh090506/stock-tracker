"""Cache latest bid/ask from SSI Quote messages for trade classification.

Stores the most recent SSIQuoteMessage per symbol. Used by TradeClassifier
to look up bid/ask prices when classifying trades as mua/ban chu dong.
"""

from app.models.ssi_messages import SSIQuoteMessage


class QuoteCache:
    """In-memory cache of latest quote per symbol."""

    def __init__(self):
        self._cache: dict[str, SSIQuoteMessage] = {}

    def update(self, quote: SSIQuoteMessage):
        """Store/overwrite the latest quote for a symbol."""
        self._cache[quote.symbol] = quote

    def get_bid_ask(self, symbol: str) -> tuple[float, float]:
        """Returns (bid_price_1, ask_price_1). (0, 0) if not yet cached."""
        q = self._cache.get(symbol)
        return (q.bid_price_1, q.ask_price_1) if q else (0.0, 0.0)

    def get_quote(self, symbol: str) -> SSIQuoteMessage | None:
        """Return full quote snapshot for a symbol, or None."""
        return self._cache.get(symbol)

    def get_price_refs(self, symbol: str) -> tuple[float, float, float]:
        """Returns (ref_price, ceiling, floor) for VN market color coding."""
        q = self._cache.get(symbol)
        return (q.ref_price, q.ceiling, q.floor) if q else (0.0, 0.0, 0.0)

    def get_all(self) -> dict[str, SSIQuoteMessage]:
        """Return all cached quotes."""
        return dict(self._cache)

    def clear(self):
        """Clear all cached quotes."""
        self._cache.clear()

"""Orchestrates all data processing — wired to SSI stream callbacks.

Phase 3A: QuoteCache, TradeClassifier, SessionAggregator.
Phase 3B: ForeignInvestorTracker, IndexTracker.
Phase 3C: DerivativesTracker, unified API, subscriber push.
"""

import logging
from collections.abc import Callable

from app.models.domain import (
    DerivativesData,
    ForeignSummary,
    MarketSnapshot,
    PriceData,
    SessionStats,
)
from app.models.ssi_messages import (
    SSIForeignMessage,
    SSIIndexMessage,
    SSIQuoteMessage,
    SSITradeMessage,
)
from app.services.derivatives_tracker import DerivativesTracker
from app.services.foreign_investor_tracker import ForeignInvestorTracker
from app.services.index_tracker import IndexTracker
from app.services.quote_cache import QuoteCache
from app.services.session_aggregator import SessionAggregator
from app.services.trade_classifier import TradeClassifier

logger = logging.getLogger(__name__)

# Subscriber callback type: fn(channel_name) -> None
SubscriberCallback = Callable[[str], None]


class MarketDataProcessor:
    """Central processor that coordinates all data processing services."""

    def __init__(self):
        self.quote_cache = QuoteCache()
        self.classifier = TradeClassifier(self.quote_cache)
        self.aggregator = SessionAggregator()
        self.foreign_tracker = ForeignInvestorTracker()
        self.index_tracker = IndexTracker()
        self.derivatives_tracker = DerivativesTracker(
            self.index_tracker, self.quote_cache
        )
        self._subscribers: list[SubscriberCallback] = []
        # Price cache: symbol -> (last_price, change, ratio_change)
        self._price_cache: dict[str, tuple[float, float, float]] = {}
        # Optional price tracker for alert generation (set externally)
        self.price_tracker = None
        # Watchlist: only process symbols in this set (empty = process all)
        self._watchlist: set[str] = set()

    # -- Watchlist --

    def set_watchlist(self, symbols: set[str]):
        """Set allowed symbols. Empty set = process all (no filter)."""
        self._watchlist = symbols
        logger.info("Watchlist set: %d symbols", len(symbols))

    def _is_watched(self, symbol: str) -> bool:
        """Check if symbol is in watchlist. VN30F* always allowed for derivatives."""
        if not self._watchlist:
            return True  # no filter
        if symbol.startswith("VN30F"):
            return True  # futures always tracked
        return symbol in self._watchlist

    # -- Stream callbacks --

    async def handle_quote(self, msg: SSIQuoteMessage):
        """Cache latest quote for bid/ask lookup by trade classifier."""
        if not self._is_watched(msg.symbol):
            return
        self.quote_cache.update(msg)
        self._notify("market")

    async def handle_trade(self, msg: SSITradeMessage):
        """Classify trade and accumulate session stats.

        Routes VN30F trades to DerivativesTracker AND classifies for persistence.
        Returns (ClassifiedTrade, SessionStats | None, BasisPoint | None).
        """
        if not self._is_watched(msg.symbol):
            return None, None, None

        if msg.symbol.startswith("VN30F"):
            bp = self.derivatives_tracker.update_from_trade(msg)
            if bp and self.price_tracker:
                self.price_tracker.on_basis_update()
            # Also classify for tick_data persistence (candle generation)
            classified = self.classifier.classify(msg)
            self._notify("market")
            return classified, None, bp

        # Cache latest price data from trade
        self._price_cache[msg.symbol] = (
            msg.last_price, msg.change, msg.ratio_change
        )

        classified = self.classifier.classify(msg)
        stats = self.aggregator.add_trade(classified)
        if self.price_tracker:
            self.price_tracker.on_trade(msg.symbol, msg.last_price, msg.last_vol)
        self._notify("market")
        return classified, stats, None

    async def handle_foreign(self, msg: SSIForeignMessage):
        """Track foreign investor delta, speed, and acceleration."""
        if not self._is_watched(msg.symbol):
            return None
        result = self.foreign_tracker.update(msg)
        if self.price_tracker:
            self.price_tracker.on_foreign(msg.symbol)
        self._notify("foreign")
        return result

    async def handle_index(self, msg: SSIIndexMessage):
        """Track index values (VN30, VNINDEX, HNX)."""
        result = self.index_tracker.update(msg)
        self._notify("index")
        return result

    # -- Unified API --

    def get_market_snapshot(self) -> MarketSnapshot:
        """All quotes + prices + indices + foreign + derivatives."""
        prices: dict[str, PriceData] = {}
        for symbol, (last_price, change, ratio_change) in self._price_cache.items():
            ref, ceiling, floor = self.quote_cache.get_price_refs(symbol)
            prices[symbol] = PriceData(
                last_price=last_price,
                change=change,
                change_pct=ratio_change,
                ref_price=ref,
                ceiling=ceiling,
                floor=floor,
            )

        return MarketSnapshot(
            quotes=self.aggregator.get_all_stats(),
            prices=prices,
            indices=self.index_tracker.get_all(),
            foreign=self.foreign_tracker.get_summary(),
            derivatives=self.derivatives_tracker.get_data(),
        )

    def get_foreign_summary(self) -> ForeignSummary:
        """Aggregate foreign flow across all tracked symbols."""
        return self.foreign_tracker.get_summary()

    def get_trade_analysis(self, symbol: str) -> SessionStats:
        """Active buy/sell breakdown for a single symbol."""
        return self.aggregator.get_stats(symbol)

    def get_derivatives_data(self) -> DerivativesData | None:
        """Current derivatives snapshot."""
        return self.derivatives_tracker.get_data()

    # -- Subscriber push --

    def subscribe(self, callback: SubscriberCallback):
        """Register a callback for real-time update push."""
        self._subscribers.append(callback)

    def unsubscribe(self, callback: SubscriberCallback):
        """Remove a subscriber callback."""
        self._subscribers = [cb for cb in self._subscribers if cb is not callback]

    def _notify(self, channel: str):
        """Notify all subscribers of a data change on a channel."""
        for cb in self._subscribers:
            try:
                cb(channel)
            except Exception:
                logger.exception("Subscriber notification error")

    # -- Session management --

    def reset_session(self):
        """Reset all session data. Called at 15:00 VN daily."""
        self.aggregator.reset()
        self.foreign_tracker.reset()
        self.index_tracker.reset()
        self.derivatives_tracker.reset()
        self._price_cache.clear()
        if self.price_tracker:
            self.price_tracker.reset()
        logger.info("Session data reset")

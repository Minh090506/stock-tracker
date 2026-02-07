"""Orchestrates all data processing — wired to SSI stream callbacks.

Phase 3A: QuoteCache, TradeClassifier, SessionAggregator.
Phase 3B: ForeignInvestorTracker, IndexTracker.
Phase 3C (future): DerivativesTracker.
"""

import logging

from app.models.ssi_messages import (
    SSIForeignMessage,
    SSIIndexMessage,
    SSIQuoteMessage,
    SSITradeMessage,
)
from app.services.foreign_investor_tracker import ForeignInvestorTracker
from app.services.index_tracker import IndexTracker
from app.services.quote_cache import QuoteCache
from app.services.session_aggregator import SessionAggregator
from app.services.trade_classifier import TradeClassifier

logger = logging.getLogger(__name__)


class MarketDataProcessor:
    """Central processor that coordinates all data processing services."""

    def __init__(self):
        self.quote_cache = QuoteCache()
        self.classifier = TradeClassifier(self.quote_cache)
        self.aggregator = SessionAggregator()
        self.foreign_tracker = ForeignInvestorTracker()
        self.index_tracker = IndexTracker()

    async def handle_quote(self, msg: SSIQuoteMessage):
        """Cache latest quote for bid/ask lookup by trade classifier."""
        self.quote_cache.update(msg)

    async def handle_trade(self, msg: SSITradeMessage):
        """Classify trade and accumulate session stats.

        Returns (ClassifiedTrade, SessionStats) or (None, None) for futures.
        """
        # Skip derivatives — will be handled by DerivativesTracker in Phase 3C
        if msg.symbol.startswith("VN30F"):
            return None, None

        classified = self.classifier.classify(msg)
        stats = self.aggregator.add_trade(classified)
        return classified, stats

    async def handle_foreign(self, msg: SSIForeignMessage):
        """Track foreign investor delta, speed, and acceleration."""
        return self.foreign_tracker.update(msg)

    async def handle_index(self, msg: SSIIndexMessage):
        """Track index values (VN30, VNINDEX, HNX)."""
        return self.index_tracker.update(msg)

    def reset_session(self):
        """Reset all session data. Called at 15:00 VN daily."""
        self.aggregator.reset()
        self.foreign_tracker.reset()
        self.index_tracker.reset()
        logger.info("Session data reset")

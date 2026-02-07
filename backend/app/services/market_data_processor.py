"""Orchestrates all data processing — wired to SSI stream callbacks.

Phase 3A: QuoteCache, TradeClassifier, SessionAggregator.
Phase 3B will add: ForeignInvestorTracker, IndexTracker, DerivativesTracker.
"""

import logging

from app.models.ssi_messages import SSIQuoteMessage, SSITradeMessage
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

    async def handle_quote(self, msg: SSIQuoteMessage):
        """Cache latest quote for bid/ask lookup by trade classifier."""
        self.quote_cache.update(msg)

    async def handle_trade(self, msg: SSITradeMessage):
        """Classify trade and accumulate session stats.

        Returns (ClassifiedTrade, SessionStats) or (None, None) for futures.
        """
        # Skip derivatives — will be handled by DerivativesTracker in Phase 3B
        if msg.symbol.startswith("VN30F"):
            return None, None

        classified = self.classifier.classify(msg)
        stats = self.aggregator.add_trade(classified)
        return classified, stats

    def reset_session(self):
        """Reset all session data. Called at 15:00 VN daily."""
        self.aggregator.reset()
        logger.info("Session data reset")

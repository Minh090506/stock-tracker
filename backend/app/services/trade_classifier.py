"""Classify trades as mua chu dong / ban chu dong / neutral.

Uses LastVol (PER-TRADE volume, NOT cumulative TotalVol) against cached
bid/ask from QuoteCache. ATO/ATC auction trades → NEUTRAL.
"""

from datetime import datetime

from app.models.domain import ClassifiedTrade, TradeType
from app.models.ssi_messages import SSITradeMessage
from app.services.quote_cache import QuoteCache


class TradeClassifier:
    """Classify each trade event using bid/ask from QuoteCache."""

    def __init__(self, quote_cache: QuoteCache):
        self._cache = quote_cache

    def classify(self, trade: SSITradeMessage) -> ClassifiedTrade:
        """Classify a single trade as active buy/sell/neutral.

        Logic:
        - ATO/ATC session → NEUTRAL (batch auction, not individual trades)
        - LastPrice >= AskPrice1 → MUA_CHU_DONG (active buy)
        - LastPrice <= BidPrice1 → BAN_CHU_DONG (active sell)
        - Otherwise → NEUTRAL (mid-spread or no bid/ask data)
        """
        bid, ask = self._cache.get_bid_ask(trade.symbol)
        volume = trade.last_vol  # PER-TRADE volume, NOT cumulative

        # Auction sessions: classify as neutral
        if trade.trading_session in ("ATO", "ATC"):
            trade_type = TradeType.NEUTRAL
        elif ask > 0 and trade.last_price >= ask:
            trade_type = TradeType.MUA_CHU_DONG
        elif bid > 0 and trade.last_price <= bid:
            trade_type = TradeType.BAN_CHU_DONG
        else:
            trade_type = TradeType.NEUTRAL

        return ClassifiedTrade(
            symbol=trade.symbol,
            price=trade.last_price,
            volume=volume,
            value=trade.last_price * volume * 1000,  # price in 1000 VND
            trade_type=trade_type,
            bid_price=bid,
            ask_price=ask,
            timestamp=datetime.now(),
        )

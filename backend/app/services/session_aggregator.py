"""Accumulate active buy/sell totals per symbol for the trading session.

Tracks mua chu dong / ban chu dong / neutral volume and value.
Resets daily at 15:00 VN time (end of trading session).
"""

from datetime import datetime

from app.models.domain import ClassifiedTrade, SessionStats, TradeType


class SessionAggregator:
    """Running totals of classified trades per symbol."""

    def __init__(self):
        self._stats: dict[str, SessionStats] = {}

    def add_trade(self, trade: ClassifiedTrade) -> SessionStats:
        """Add a classified trade to session totals. Returns updated stats."""
        if trade.symbol not in self._stats:
            self._stats[trade.symbol] = SessionStats(symbol=trade.symbol)
        stats = self._stats[trade.symbol]

        if trade.trade_type == TradeType.MUA_CHU_DONG:
            stats.mua_chu_dong_volume += trade.volume
            stats.mua_chu_dong_value += trade.value
        elif trade.trade_type == TradeType.BAN_CHU_DONG:
            stats.ban_chu_dong_volume += trade.volume
            stats.ban_chu_dong_value += trade.value
        else:
            stats.neutral_volume += trade.volume

        stats.total_volume += trade.volume
        stats.last_updated = trade.timestamp
        return stats

    def get_stats(self, symbol: str) -> SessionStats:
        """Get session stats for a symbol. Returns empty stats if not tracked."""
        return self._stats.get(symbol, SessionStats(symbol=symbol))

    def get_all_stats(self) -> dict[str, SessionStats]:
        """Return all tracked symbols' stats."""
        return dict(self._stats)

    def reset(self):
        """Clear all session stats. Called at 15:00 VN daily."""
        self._stats.clear()

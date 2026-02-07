"""Track VN30F futures price and compute basis against VN30 spot index.

Input: X-TRADE messages for VN30F contracts.
Basis = futures_price - VN30_spot (from IndexTracker).
Maintains historical basis array for charting.
"""

import logging
from collections import deque
from datetime import datetime, timedelta

from app.models.domain import BasisPoint, DerivativesData
from app.models.ssi_messages import SSITradeMessage
from app.services.index_tracker import IndexTracker
from app.services.quote_cache import QuoteCache

logger = logging.getLogger(__name__)

# Max basis history points (~1h at 1 trade/sec)
_BASIS_HISTORY_MAXLEN = 3600


class DerivativesTracker:
    """Track VN30F futures and compute basis against VN30 spot."""

    def __init__(self, index_tracker: IndexTracker, quote_cache: QuoteCache):
        self._index = index_tracker
        self._quote_cache = quote_cache
        # Per-symbol futures state
        self._prices: dict[str, float] = {}
        self._volumes: dict[str, int] = {}
        self._changes: dict[str, float] = {}
        self._change_pcts: dict[str, float] = {}
        # Basis tracking (shared across all VN30F symbols)
        self._basis_history: deque[BasisPoint] = deque(maxlen=_BASIS_HISTORY_MAXLEN)
        self._current_basis: BasisPoint | None = None
        # Track which symbol is the active (nearest) contract
        self._active_symbol: str = ""

    def update_from_trade(self, trade: SSITradeMessage) -> BasisPoint | None:
        """Process a VN30F trade. Returns BasisPoint if computable."""
        symbol = trade.symbol
        self._prices[symbol] = trade.last_price
        self._volumes[symbol] = self._volumes.get(symbol, 0) + trade.last_vol
        self._changes[symbol] = trade.change
        self._change_pcts[symbol] = trade.ratio_change

        # Track the most-traded contract as active
        if not self._active_symbol or self._volumes.get(symbol, 0) >= self._volumes.get(
            self._active_symbol, 0
        ):
            self._active_symbol = symbol

        return self._compute_basis(symbol)

    def _compute_basis(self, futures_symbol: str) -> BasisPoint | None:
        """Compute basis = futures_price - VN30_spot."""
        futures_price = self._prices.get(futures_symbol, 0.0)
        spot_value = self._index.get_vn30_value()
        if futures_price <= 0 or spot_value <= 0:
            return None

        basis = futures_price - spot_value
        basis_pct = basis / spot_value * 100

        bp = BasisPoint(
            timestamp=datetime.now(),
            futures_symbol=futures_symbol,
            futures_price=futures_price,
            spot_value=spot_value,
            basis=basis,
            basis_pct=basis_pct,
            is_premium=basis > 0,
        )
        self._basis_history.append(bp)
        self._current_basis = bp
        return bp

    def get_current_basis(self) -> BasisPoint | None:
        """Latest basis point."""
        return self._current_basis

    def get_basis_trend(self, minutes: int = 30) -> list[BasisPoint]:
        """Historical basis points within the time window."""
        cutoff = datetime.now() - timedelta(minutes=minutes)
        return [b for b in self._basis_history if b.timestamp >= cutoff]

    def get_data(self) -> DerivativesData | None:
        """Full derivatives snapshot for the active contract."""
        if not self._active_symbol:
            return None
        symbol = self._active_symbol
        bid, ask = self._quote_cache.get_bid_ask(symbol)
        return DerivativesData(
            symbol=symbol,
            last_price=self._prices.get(symbol, 0.0),
            change=self._changes.get(symbol, 0.0),
            change_pct=self._change_pcts.get(symbol, 0.0),
            volume=self._volumes.get(symbol, 0),
            bid_price=bid,
            ask_price=ask,
            basis=self._current_basis.basis if self._current_basis else 0.0,
            basis_pct=self._current_basis.basis_pct if self._current_basis else 0.0,
            is_premium=self._current_basis.is_premium if self._current_basis else True,
            last_updated=datetime.now(),
        )

    def get_futures_price(self, symbol: str) -> float:
        """Get cached futures price for a specific contract."""
        return self._prices.get(symbol, 0.0)

    def reset(self):
        """Clear all session data. Called at 15:00 VN daily."""
        self._prices.clear()
        self._volumes.clear()
        self._changes.clear()
        self._change_pcts.clear()
        self._basis_history.clear()
        self._current_basis = None
        self._active_symbol = ""

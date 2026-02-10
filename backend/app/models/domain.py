"""Domain models for processed/classified data.

Used by Phase 3+ data processing services (TradeClassifier, ForeignTracker, etc.).
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, computed_field


class TradeType(str, Enum):
    MUA_CHU_DONG = "mua_chu_dong"
    BAN_CHU_DONG = "ban_chu_dong"
    NEUTRAL = "neutral"


class ClassifiedTrade(BaseModel):
    """A single trade classified as active buy/sell/neutral."""

    symbol: str
    price: float
    volume: int  # PER-TRADE from LastVol
    value: float
    trade_type: TradeType
    bid_price: float
    ask_price: float
    timestamp: datetime
    trading_session: str = ""  # "ATO", "ATC", or "" (continuous)


class SessionBreakdown(BaseModel):
    """Volume breakdown for a single trading session phase (ATO/Continuous/ATC)."""

    mua_chu_dong_volume: int = 0
    ban_chu_dong_volume: int = 0
    neutral_volume: int = 0
    total_volume: int = 0


class SessionStats(BaseModel):
    """Aggregated active buy/sell stats for a single symbol session."""

    symbol: str
    mua_chu_dong_volume: int = 0
    mua_chu_dong_value: float = 0.0
    ban_chu_dong_volume: int = 0
    ban_chu_dong_value: float = 0.0
    neutral_volume: int = 0
    total_volume: int = 0
    last_updated: datetime | None = None
    # Per-session phase breakdown
    ato: SessionBreakdown = SessionBreakdown()
    continuous: SessionBreakdown = SessionBreakdown()
    atc: SessionBreakdown = SessionBreakdown()


class PriceData(BaseModel):
    """Last trade price + reference levels for a single stock."""

    last_price: float = 0.0
    change: float = 0.0       # last_price - ref_price (from SSI)
    change_pct: float = 0.0   # ratio_change (from SSI, already %)
    ref_price: float = 0.0    # reference/opening price
    ceiling: float = 0.0      # price ceiling (tran)
    floor: float = 0.0        # price floor (san)


class ForeignInvestorData(BaseModel):
    """Foreign investor tracking with computed deltas, speed, and acceleration."""

    symbol: str
    buy_volume: int = 0
    sell_volume: int = 0
    net_volume: int = 0
    buy_value: float = 0.0
    sell_value: float = 0.0
    net_value: float = 0.0
    total_room: int = 0
    current_room: int = 0
    buy_speed_per_min: float = 0.0
    sell_speed_per_min: float = 0.0
    buy_acceleration: float = 0.0  # speed change rate (vol/min^2)
    sell_acceleration: float = 0.0
    last_updated: datetime | None = None


class ForeignSummary(BaseModel):
    """VN30 aggregate foreign flow + top movers."""

    total_buy_value: float = 0.0
    total_sell_value: float = 0.0
    total_net_value: float = 0.0
    total_buy_volume: int = 0
    total_sell_volume: int = 0
    total_net_volume: int = 0
    top_buy: list[ForeignInvestorData] = []
    top_sell: list[ForeignInvestorData] = []


class IntradayPoint(BaseModel):
    """Single point for sparkline chart."""

    timestamp: datetime
    value: float


class IndexData(BaseModel):
    """Real-time index snapshot (VN30, VNINDEX)."""

    index_id: str
    value: float = 0.0
    prior_value: float = 0.0
    change: float = 0.0
    ratio_change: float = 0.0
    total_volume: int = 0
    advances: int = 0
    declines: int = 0
    no_changes: int = 0
    intraday: list[IntradayPoint] = []
    last_updated: datetime | None = None

    @computed_field
    @property
    def advance_ratio(self) -> float:
        """Breadth: advance / (advance + decline). 0.0 if no data."""
        total = self.advances + self.declines
        return self.advances / total if total > 0 else 0.0


class BasisPoint(BaseModel):
    """Futures-spot basis at a point in time."""

    timestamp: datetime
    futures_symbol: str
    futures_price: float
    spot_value: float
    basis: float  # futures_price - spot_value
    basis_pct: float = 0.0  # basis / spot_value * 100
    is_premium: bool  # basis > 0


class DerivativesData(BaseModel):
    """Real-time snapshot of a VN30F futures contract."""

    symbol: str
    last_price: float = 0.0
    change: float = 0.0
    change_pct: float = 0.0
    volume: int = 0  # cumulative session volume
    bid_price: float = 0.0
    ask_price: float = 0.0
    basis: float = 0.0  # futures_price - VN30_spot
    basis_pct: float = 0.0  # basis / VN30_spot * 100
    is_premium: bool = True  # basis > 0
    last_updated: datetime | None = None


class MarketSnapshot(BaseModel):
    """Unified snapshot of all market data for API consumers."""

    quotes: dict[str, "SessionStats"] = {}
    prices: dict[str, "PriceData"] = {}
    indices: dict[str, IndexData] = {}
    foreign: ForeignSummary | None = None
    derivatives: DerivativesData | None = None

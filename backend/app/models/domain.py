"""Domain models for processed/classified data.

Used by Phase 3+ data processing services (TradeClassifier, ForeignTracker, etc.).
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


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


class SessionStats(BaseModel):
    """Aggregated active buy/sell stats for a single symbol session."""

    symbol: str
    mua_chu_dong_volume: int = 0
    mua_chu_dong_value: float = 0.0
    ban_chu_dong_volume: int = 0
    ban_chu_dong_value: float = 0.0
    neutral_volume: int = 0
    total_volume: int = 0
    last_updated: Optional[datetime] = None


class ForeignInvestorData(BaseModel):
    """Foreign investor tracking with computed deltas and speed."""

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
    last_updated: Optional[datetime] = None


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
    last_updated: Optional[datetime] = None


class BasisPoint(BaseModel):
    """Futures-spot basis at a point in time."""

    timestamp: datetime
    futures_symbol: str
    futures_price: float
    spot_value: float
    basis: float  # futures_price - spot_value
    is_premium: bool  # basis > 0

"""Pydantic models for raw SSI WebSocket message types.

Each model maps 1:1 to SSI channel message format after PascalCase→snake_case normalization.
"""

from pydantic import BaseModel


class SSITradeMessage(BaseModel):
    """Channel X, RType='Trade' - per-trade event."""

    symbol: str = ""
    exchange: str = ""
    last_price: float = 0.0
    last_vol: int = 0  # PER-TRADE volume (NOT cumulative)
    total_vol: int = 0
    total_val: float = 0.0
    change: float = 0.0
    ratio_change: float = 0.0
    trading_session: str = ""


class SSIQuoteMessage(BaseModel):
    """Channel X, RType='Quote' - order book snapshot."""

    symbol: str = ""
    exchange: str = ""
    ceiling: float = 0.0
    floor: float = 0.0
    ref_price: float = 0.0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    bid_price_1: float = 0.0
    bid_vol_1: int = 0
    ask_price_1: float = 0.0
    ask_vol_1: int = 0
    bid_price_2: float = 0.0
    bid_vol_2: int = 0
    ask_price_2: float = 0.0
    ask_vol_2: int = 0
    bid_price_3: float = 0.0
    bid_vol_3: int = 0
    ask_price_3: float = 0.0
    ask_vol_3: int = 0


class SSIForeignMessage(BaseModel):
    """Channel R - foreign investor cumulative data."""

    symbol: str = ""
    f_buy_vol: int = 0
    f_sell_vol: int = 0
    f_buy_val: float = 0.0
    f_sell_val: float = 0.0
    total_room: int = 0
    current_room: int = 0


class SSIIndexMessage(BaseModel):
    """Channel MI - index values."""

    index_id: str = ""
    index_value: float = 0.0
    prior_index_value: float = 0.0
    change: float = 0.0
    ratio_change: float = 0.0
    total_qtty: int = 0
    total_val: float = 0.0
    advances: int = 0
    declines: int = 0
    no_changes: int = 0


class SSIBarMessage(BaseModel):
    """Channel B - OHLC bar."""

    symbol: str = ""
    time: str = ""
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: int = 0

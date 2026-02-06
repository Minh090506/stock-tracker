"""SSI PascalCase→snake_case field normalization and message parsing.

Converts raw SSI WebSocket message dicts into typed Pydantic models
by mapping PascalCase field names to snake_case model fields.
"""

import json
import logging
from typing import Dict, Optional, Tuple

from app.models.ssi_messages import (
    SSIBarMessage,
    SSIForeignMessage,
    SSIIndexMessage,
    SSIQuoteMessage,
    SSITradeMessage,
)

logger = logging.getLogger(__name__)

# PascalCase→snake_case mapping for all known SSI fields
FIELD_MAP: Dict[str, str] = {
    "Symbol": "symbol",
    "Exchange": "exchange",
    "StockSymbol": "symbol",
    # Trade fields
    "LastPrice": "last_price",
    "LastVol": "last_vol",
    "TotalVol": "total_vol",
    "TotalVal": "total_val",
    "Change": "change",
    "RatioChange": "ratio_change",
    "TradingSession": "trading_session",
    # Quote fields
    "Ceiling": "ceiling",
    "Floor": "floor",
    "RefPrice": "ref_price",
    "Open": "open",
    "High": "high",
    "Low": "low",
    "BidPrice1": "bid_price_1",
    "BidVol1": "bid_vol_1",
    "AskPrice1": "ask_price_1",
    "AskVol1": "ask_vol_1",
    "BidPrice2": "bid_price_2",
    "BidVol2": "bid_vol_2",
    "AskPrice2": "ask_price_2",
    "AskVol2": "ask_vol_2",
    "BidPrice3": "bid_price_3",
    "BidVol3": "bid_vol_3",
    "AskPrice3": "ask_price_3",
    "AskVol3": "ask_vol_3",
    # Foreign fields
    "FBuyVol": "f_buy_vol",
    "FSellVol": "f_sell_vol",
    "FBuyVal": "f_buy_val",
    "FSellVal": "f_sell_val",
    "TotalRoom": "total_room",
    "CurrentRoom": "current_room",
    # Index fields
    "IndexId": "index_id",
    "IndexValue": "index_value",
    "PriorIndexValue": "prior_index_value",
    "TotalQtty": "total_qtty",
    "Advances": "advances",
    "Declines": "declines",
    "NoChanges": "no_changes",
    # Bar fields
    "Time": "time",
    "Volume": "volume",
    "Close": "close",
}


def normalize_fields(content: dict) -> dict:
    """Convert SSI PascalCase fields to snake_case. Only mapped fields pass through."""
    return {FIELD_MAP[k]: v for k, v in content.items() if k in FIELD_MAP}


def extract_content(raw) -> Optional[dict]:
    """Extract the content dict from a raw SSI message."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.debug("Failed to parse SSI message as JSON: %s", raw[:200] if raw else raw)
            return None
    if not isinstance(raw, dict):
        return None
    # SSI wraps payload in "Content" or "content" key, or sends flat
    return raw.get("Content") or raw.get("content") or raw


# RType→(model_class) routing table
RTYPE_ROUTER: Dict[str, type] = {
    "Trade": SSITradeMessage,
    "Quote": SSIQuoteMessage,
    "R": SSIForeignMessage,
    "MI": SSIIndexMessage,
    "B": SSIBarMessage,
}


def parse_message(content: dict) -> Optional[Tuple[str, object]]:
    """Parse SSI content dict into (rtype, typed_model) or None if unknown."""
    rtype = content.get("RType", "")
    model_cls = RTYPE_ROUTER.get(rtype)
    if not model_cls:
        logger.debug("Unknown RType: %s", rtype)
        return None
    try:
        fields = normalize_fields(content)
        return rtype, model_cls(**fields)
    except Exception:
        logger.debug("Failed to parse %s message", rtype, exc_info=True)
        return None

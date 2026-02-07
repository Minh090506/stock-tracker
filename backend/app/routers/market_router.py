"""REST endpoints for real-time market data snapshots.

Exposes MarketDataProcessor in-memory state via REST for frontend polling.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/snapshot")
async def get_snapshot():
    """Full market snapshot: quotes + indices + foreign + derivatives."""
    from app.main import processor

    return processor.get_market_snapshot()


@router.get("/foreign-detail")
async def get_foreign_detail():
    """Per-symbol foreign investor data for heatmap/table."""
    from app.main import processor

    summary = processor.get_foreign_summary()
    stocks = list(processor.foreign_tracker.get_all().values())
    return {"summary": summary, "stocks": stocks}


@router.get("/volume-stats")
async def get_volume_stats():
    """Per-symbol active buy/sell session stats."""
    from app.main import processor

    stats = list(processor.aggregator.get_all_stats().values())
    return {"stats": stats}

"""Background task that broadcasts market data to all WebSocket channels.

Channels:
  market  — full MarketSnapshot
  foreign — ForeignSummary only
  index   — dict of IndexData (VN30 + VNINDEX)
"""

import asyncio
import json
import logging

from app.config import settings

logger = logging.getLogger(__name__)


async def broadcast_loop(
    processor,
    market_ws_manager,
    foreign_ws_manager,
    index_ws_manager,
) -> None:
    """Broadcast to 3 WebSocket channels. Skips channels with zero clients."""
    interval = settings.ws_broadcast_interval
    logger.info("Broadcast loop started (interval=%.1fs)", interval)
    try:
        while True:
            await asyncio.sleep(interval)
            total = (
                market_ws_manager.client_count
                + foreign_ws_manager.client_count
                + index_ws_manager.client_count
            )
            if total == 0:
                continue

            try:
                if market_ws_manager.client_count > 0:
                    snapshot = processor.get_market_snapshot()
                    market_ws_manager.broadcast(snapshot.model_dump_json())

                if foreign_ws_manager.client_count > 0:
                    foreign = processor.get_foreign_summary()
                    foreign_ws_manager.broadcast(foreign.model_dump_json())

                if index_ws_manager.client_count > 0:
                    indices = processor.index_tracker.get_all()
                    data = json.dumps({k: v.model_dump() for k, v in indices.items()})
                    index_ws_manager.broadcast(data)

            except Exception:
                logger.exception("Error in broadcast loop iteration")
    except asyncio.CancelledError:
        logger.info("Broadcast loop stopped")

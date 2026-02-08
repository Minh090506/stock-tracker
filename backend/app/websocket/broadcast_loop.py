"""Background task that broadcasts MarketSnapshot to all WebSocket clients."""

import asyncio
import logging

from app.config import settings

logger = logging.getLogger(__name__)


async def broadcast_loop(processor, ws_manager) -> None:
    """Periodically serialize snapshot and push to all WS clients.

    Skips serialization when no clients are connected (zero-cost idle).
    """
    interval = settings.ws_broadcast_interval
    logger.info("Broadcast loop started (interval=%.1fs)", interval)
    try:
        while True:
            await asyncio.sleep(interval)
            if ws_manager.client_count == 0:
                continue
            try:
                snapshot = processor.get_market_snapshot()
                data = snapshot.model_dump_json()
                ws_manager.broadcast(data)
            except Exception:
                logger.exception("Error in broadcast loop iteration")
    except asyncio.CancelledError:
        logger.info("Broadcast loop stopped")

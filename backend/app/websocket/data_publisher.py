"""Event-driven WebSocket publisher with per-channel throttling.

Bridges SSI stream events to client WebSocket channels.
Replaces poll-based broadcast_loop with reactive push.

Throttle: trailing-edge — if data arrives within the throttle window,
schedules a deferred broadcast so the latest state always gets sent.
"""

import asyncio
import json
import logging
import time

from app.config import settings
from app.websocket.connection_manager import ConnectionManager

logger = logging.getLogger(__name__)

# Channel constants matching WebSocket endpoints
CH_MARKET = "market"
CH_FOREIGN = "foreign"
CH_INDEX = "index"


class DataPublisher:
    """Event-driven publisher that throttles per-channel broadcasts.

    Usage:
        publisher = DataPublisher(processor, market_mgr, foreign_mgr, index_mgr)
        publisher.start()
        processor.subscribe(publisher.notify)
    """

    def __init__(
        self,
        processor,
        market_mgr: ConnectionManager,
        foreign_mgr: ConnectionManager,
        index_mgr: ConnectionManager,
    ):
        self._processor = processor
        self._managers: dict[str, ConnectionManager] = {
            CH_MARKET: market_mgr,
            CH_FOREIGN: foreign_mgr,
            CH_INDEX: index_mgr,
        }
        self._throttle_s = settings.ws_throttle_interval_ms / 1000.0
        self._last_broadcast: dict[str, float] = {}
        self._pending: dict[str, asyncio.TimerHandle] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._running = False

    def start(self):
        """Capture event loop and mark as running."""
        self._loop = asyncio.get_running_loop()
        self._running = True
        logger.info(
            "DataPublisher started (throttle=%dms)",
            settings.ws_throttle_interval_ms,
        )

    def stop(self):
        """Cancel pending timers and stop publishing."""
        self._running = False
        for handle in self._pending.values():
            handle.cancel()
        self._pending.clear()
        logger.info("DataPublisher stopped")

    # -- Event notification (called by MarketDataProcessor) --

    def notify(self, channel: str):
        """Throttled notification — schedules or fires broadcast for channel.

        Called synchronously from processor after each handle_* update.
        """
        if not self._running or not self._loop:
            return

        manager = self._managers.get(channel)
        if not manager or manager.client_count == 0:
            return

        now = time.monotonic()
        last = self._last_broadcast.get(channel, 0)
        elapsed = now - last

        if elapsed >= self._throttle_s:
            # Enough time passed — broadcast immediately
            self._do_broadcast(channel)
        elif channel not in self._pending:
            # Schedule trailing-edge broadcast for remaining window
            delay = self._throttle_s - elapsed
            handle = self._loop.call_later(delay, self._do_broadcast, channel)
            self._pending[channel] = handle

    # -- Broadcast execution --

    def _do_broadcast(self, channel: str):
        """Pull latest data from processor and broadcast to channel clients."""
        # Clear pending timer reference
        self._pending.pop(channel, None)

        if not self._running:
            return

        manager = self._managers.get(channel)
        if not manager or manager.client_count == 0:
            return

        try:
            data = self._get_channel_data(channel)
            if data:
                manager.broadcast(data)
                self._last_broadcast[channel] = time.monotonic()
        except Exception:
            logger.exception("Error broadcasting to %s", channel)

    def _get_channel_data(self, channel: str) -> str | None:
        """Serialize latest processor state for a channel."""
        match channel:
            case "market":
                return self._processor.get_market_snapshot().model_dump_json()
            case "foreign":
                return self._processor.get_foreign_summary().model_dump_json()
            case "index":
                indices = self._processor.index_tracker.get_all()
                return json.dumps(
                    {k: v.model_dump() for k, v in indices.items()},
                    default=str,
                )
            case _:
                return None

    # -- SSI connection status notifications --

    def on_ssi_disconnect(self):
        """Broadcast disconnect status to all channels with clients."""
        msg = json.dumps({"type": "status", "connected": False})
        count = self._broadcast_status(msg)
        logger.warning("SSI disconnected — notified %d WS channels", count)

    def on_ssi_reconnect(self):
        """Broadcast reconnect status to all channels with clients."""
        msg = json.dumps({"type": "status", "connected": True})
        count = self._broadcast_status(msg)
        logger.info("SSI reconnected — notified %d WS channels", count)

    def _broadcast_status(self, msg: str) -> int:
        """Send status message to all channels with connected clients."""
        count = 0
        for manager in self._managers.values():
            if manager.client_count > 0:
                manager.broadcast(msg)
                count += 1
        return count

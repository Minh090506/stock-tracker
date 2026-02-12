"""SSI WebSocket stream service — connection lifecycle, demux, and reconnect.

Connects to SSI SignalR hub via asyncio.to_thread (ssi-fc-data is sync-only),
demuxes incoming messages by RType, dispatches to registered callbacks,
and handles reconnection with REST snapshot reconciliation.
"""

import asyncio
import logging
from collections.abc import Callable

from ssi_fc_data.fc_md_client import MarketDataClient
from ssi_fc_data.fc_md_stream import MarketDataStream

from app.metrics import ssi_messages_received_total
from app.services.ssi_field_normalizer import extract_content, parse_message_multi

logger = logging.getLogger(__name__)

# Map RType → Prometheus label
_RTYPE_LABEL = {"Trade": "trade", "Quote": "quote", "R": "foreign", "MI": "index", "B": "bar"}

# Callback type: async function receiving a typed SSI message
MessageCallback = Callable  # async (msg) -> None


class SSIStreamService:
    """Manages SSI WebSocket connection, message demux, and auto-reconnect."""

    _BASE_RECONNECT_DELAY = 2.0  # seconds
    _MAX_RECONNECT_DELAY = 60.0  # cap for exponential backoff

    def __init__(self, auth_service, market_service):
        self._auth = auth_service
        self._market = market_service
        self._stream: MarketDataStream | None = None
        self._stream_task: asyncio.Task | None = None
        self._reconnecting = False
        self._shutting_down = False
        self._channels: list[str] = []
        self._reconnect_task: asyncio.Task | None = None
        # Callback registry keyed by RType
        self._callbacks: dict[str, list[MessageCallback]] = {
            "Trade": [],
            "Quote": [],
            "R": [],
            "MI": [],
            "B": [],
        }
        # Prevent GC of fire-and-forget callback tasks
        self._background_tasks: set[asyncio.Task] = set()
        # Reconciliation callback set by the app layer (Phase 3)
        self._reconcile_callback: Callable | None = None
        # Disconnect/reconnect callbacks for downstream notification
        self._disconnect_callback: Callable | None = None
        self._reconnect_callback: Callable | None = None
        # Main event loop ref — captured at connect() time for cross-thread dispatch
        self._loop: asyncio.AbstractEventLoop | None = None

    # -- Callback registration --

    def on_trade(self, cb: MessageCallback):
        self._callbacks["Trade"].append(cb)

    def on_quote(self, cb: MessageCallback):
        self._callbacks["Quote"].append(cb)

    def on_foreign(self, cb: MessageCallback):
        self._callbacks["R"].append(cb)

    def on_index(self, cb: MessageCallback):
        self._callbacks["MI"].append(cb)

    def on_bar(self, cb: MessageCallback):
        self._callbacks["B"].append(cb)

    def set_reconcile_callback(self, cb: Callable):
        """Set callback for reconnect reconciliation (Phase 3)."""
        self._reconcile_callback = cb

    def set_disconnect_callback(self, cb: Callable):
        """Set callback fired when SSI stream disconnects/crashes."""
        self._disconnect_callback = cb

    def set_reconnect_callback(self, cb: Callable):
        """Set callback fired after SSI stream reconnects."""
        self._reconnect_callback = cb

    # -- Connection lifecycle --

    async def connect(self, channels: list[str]):
        """Connect SSI stream in a background thread.

        This is the DEFAULT approach — SignalR start() blocks the calling thread,
        so asyncio.to_thread is mandatory, not a fallback.
        """
        # Capture the running event loop for cross-thread callback dispatch
        self._loop = asyncio.get_running_loop()
        self._channels = channels
        config = self._auth.config
        self._stream = MarketDataStream(config, MarketDataClient(config))
        channel_str = ",".join(channels)
        logger.info("Connecting SSI stream — channels: %s", channel_str)
        self._stream_task = asyncio.create_task(
            asyncio.to_thread(
                self._stream.start,
                self._handle_message,
                self._handle_error,
                channel_str,
            )
        )
        # Store ref to prevent GC
        self._background_tasks.add(self._stream_task)
        self._stream_task.add_done_callback(self._on_stream_done)

    async def disconnect(self):
        """Graceful shutdown — cancel stream task and stop auto-reconnect."""
        self._shutting_down = True
        logger.info("Disconnecting SSI stream...")
        # Cancel pending reconnect attempt
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
        if self._stream_task and not self._stream_task.done():
            self._stream_task.cancel()
            try:
                await self._stream_task
            except asyncio.CancelledError:
                pass
        # Cancel all pending callback tasks
        for task in list(self._background_tasks):
            if not task.done():
                task.cancel()
        self._background_tasks.clear()
        logger.info("SSI stream disconnected")

    # -- Message handling --

    def _handle_message(self, raw):
        """Demux raw SSI message by RType and dispatch to callbacks.

        Called from the stream thread — schedules async callbacks on the event loop.
        X:ALL channel sends combined trade+quote data as RType="X",
        which parse_message_multi splits into separate Trade and Quote results.
        """
        content = extract_content(raw)
        if content is None:
            return
        for rtype, msg in parse_message_multi(content):
            ssi_messages_received_total.labels(channel=_RTYPE_LABEL.get(rtype, rtype)).inc()
            callbacks = self._callbacks.get(rtype, [])
            for cb in callbacks:
                self._schedule_callback(cb, msg)

    def _handle_error(self, error):
        """Log stream error. ssi-fc-data may auto-reconnect internally."""
        logger.error("SSI stream error: %s", error)

    def _schedule_callback(self, cb: MessageCallback, msg):
        """Schedule an async callback on the main event loop from the stream thread."""
        if not self._loop:
            logger.warning("No event loop — dropping callback for %s", type(msg).__name__)
            return
        asyncio.run_coroutine_threadsafe(self._run_callback(cb, msg), self._loop)

    async def _run_callback(self, cb: MessageCallback, msg):
        """Execute a callback with error isolation."""
        task = asyncio.current_task()
        if task:
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
        try:
            await cb(msg)
        except Exception:
            logger.exception("Callback error for %s", type(msg).__name__)

    # -- Reconnect reconciliation --

    async def reconcile_after_reconnect(self):
        """Fetch REST snapshot to reconcile state after reconnect.

        Prevents incorrect delta spikes in foreign data by re-seeding
        cumulative values from REST snapshot.
        """
        self._reconnecting = True
        logger.warning("SSI reconnected — fetching REST snapshot to reconcile")
        try:
            snapshot = await self._market.fetch_securities_snapshot()
            if self._reconcile_callback and snapshot:
                for item in snapshot:
                    self._reconcile_callback(item)
            logger.info("Reconnect reconciliation complete — %d items", len(snapshot))
        except Exception:
            logger.exception("Reconnect reconciliation failed. First deltas may be inaccurate.")
        finally:
            self._reconnecting = False
            # Notify downstream of reconnection
            if self._reconnect_callback:
                try:
                    self._reconnect_callback()
                except Exception:
                    logger.exception("Reconnect callback error")

    @property
    def is_reconnecting(self) -> bool:
        return self._reconnecting

    def _on_stream_done(self, task: asyncio.Task):
        """Handle stream task completion — notify downstream and auto-reconnect."""
        self._background_tasks.discard(task)
        if task.cancelled():
            logger.info("SSI stream task cancelled")
            return
        exc = task.exception()
        if exc:
            logger.error("SSI stream task crashed: %s", exc, exc_info=exc)
        else:
            logger.warning("SSI stream task ended unexpectedly without error")
        # Notify downstream of disconnection
        if self._disconnect_callback:
            try:
                self._disconnect_callback()
            except Exception:
                logger.exception("Disconnect callback error")
        # Schedule auto-reconnect (unless shutting down or already reconnecting)
        if self._shutting_down or not self._loop:
            return
        if self._reconnect_task and not self._reconnect_task.done():
            logger.info("Auto-reconnect already in progress — skipping duplicate")
            return
        self._reconnect_task = self._loop.create_task(self._auto_reconnect())

    async def _auto_reconnect(self):
        """Re-authenticate and reconnect SSI stream with exponential backoff.

        Waits briefly after connect() to verify stream stability before
        declaring success. If stream crashes immediately, backoff increases.
        """
        delay = self._BASE_RECONNECT_DELAY
        attempt = 0
        while not self._shutting_down:
            attempt += 1
            logger.warning("SSI auto-reconnect attempt %d in %.0fs...", attempt, delay)
            await asyncio.sleep(delay)
            if self._shutting_down:
                return
            try:
                # Re-authenticate (JWT token may have expired)
                await self._auth.authenticate()
                # Reconnect stream with same channels
                await self.connect(self._channels)
                # Wait briefly to verify stream didn't crash immediately
                await asyncio.sleep(3.0)
                if self._stream_task and self._stream_task.done():
                    raise RuntimeError("Stream crashed immediately after connect")
                # Reconcile cumulative state from REST snapshot
                await self.reconcile_after_reconnect()
                logger.info("SSI auto-reconnect successful after %d attempt(s)", attempt)
                return
            except Exception:
                logger.exception("SSI auto-reconnect attempt %d failed", attempt)
                delay = min(delay * 2, self._MAX_RECONNECT_DELAY)

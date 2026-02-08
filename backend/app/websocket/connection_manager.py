"""Manages WebSocket clients with per-client async queues."""

import asyncio
import logging

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.config import settings

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket client connections and message broadcasting.

    Each client gets a dedicated asyncio.Queue and sender task.
    Broadcast pushes to all queues; slow clients drop oldest messages.
    """

    def __init__(self) -> None:
        # WebSocket → (queue, sender_task)
        self._clients: dict[WebSocket, tuple[asyncio.Queue[str], asyncio.Task]] = {}

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def connect(self, ws: WebSocket) -> None:
        """Accept WS connection, create queue + sender task."""
        await ws.accept()
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=settings.ws_queue_size)
        task = asyncio.create_task(self._sender(ws, queue))
        self._clients[ws] = (queue, task)
        logger.info("WS client connected (%d total)", self.client_count)

    async def disconnect(self, ws: WebSocket) -> None:
        """Remove client, cancel sender task, close socket."""
        entry = self._clients.pop(ws, None)
        if entry is None:
            return
        _, task = entry
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        if ws.client_state == WebSocketState.CONNECTED:
            try:
                await ws.close()
            except Exception:
                pass
        logger.info("WS client disconnected (%d remaining)", self.client_count)

    def broadcast(self, data: str) -> None:
        """Push JSON string to all client queues. Drop oldest on overflow."""
        for _ws, (queue, _task) in self._clients.items():
            if queue.full():
                try:
                    queue.get_nowait()  # drop oldest
                except asyncio.QueueEmpty:
                    pass
            try:
                queue.put_nowait(data)
            except asyncio.QueueFull:
                pass  # safety fallback

    async def disconnect_all(self) -> None:
        """Disconnect all clients. Called on shutdown."""
        clients = list(self._clients.keys())
        for ws in clients:
            await self.disconnect(ws)

    async def _sender(self, ws: WebSocket, queue: asyncio.Queue[str]) -> None:
        """Per-client loop: pull from queue, send over WS."""
        try:
            while True:
                data = await queue.get()
                await ws.send_text(data)
        except (WebSocketDisconnect, RuntimeError, asyncio.CancelledError):
            pass
        except Exception:
            logger.exception("Unexpected error in WS sender")

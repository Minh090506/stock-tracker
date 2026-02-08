"""WebSocket endpoint for real-time market data broadcast."""

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


async def _heartbeat(ws: WebSocket) -> None:
    """Send ping bytes at interval. Gives up if send fails."""
    try:
        while True:
            await asyncio.sleep(settings.ws_heartbeat_interval)
            try:
                await asyncio.wait_for(
                    ws.send_bytes(b"ping"),
                    timeout=settings.ws_heartbeat_timeout,
                )
            except (asyncio.TimeoutError, Exception):
                logger.info("Heartbeat timeout, closing WS")
                return
    except asyncio.CancelledError:
        pass


@router.websocket("/ws/market")
async def market_websocket(ws: WebSocket) -> None:
    """Accept WS connection and keep alive until client disconnects."""
    from app.main import ws_manager

    await ws_manager.connect(ws)
    heartbeat_task = asyncio.create_task(_heartbeat(ws))
    try:
        while True:
            # Read loop — keeps connection alive, detects client disconnect
            await ws.receive_text()
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        await ws_manager.disconnect(ws)

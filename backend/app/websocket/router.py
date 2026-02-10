"""Multi-channel WebSocket router with authentication and rate limiting.

Channels:
  /ws/market  — full MarketSnapshot (quotes + indices + foreign + derivatives)
  /ws/foreign — ForeignSummary only (aggregate + top movers)
  /ws/index   — VN30 + VNINDEX IndexData only
  /ws/alerts  — real-time analytics alerts (volume spike, breakout, foreign accel, basis flip)
"""

import asyncio
import logging
from collections import defaultdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Rate limiter — tracks active connections per IP
# ---------------------------------------------------------------------------

class RateLimiter:
    """Track WebSocket connections per IP address."""

    def __init__(self) -> None:
        self._connections: dict[str, int] = defaultdict(int)

    def check(self, ip: str, limit: int) -> bool:
        return self._connections[ip] < limit

    def increment(self, ip: str) -> None:
        self._connections[ip] += 1

    def decrement(self, ip: str) -> None:
        self._connections[ip] = max(0, self._connections[ip] - 1)


_rate_limiter = RateLimiter()


# ---------------------------------------------------------------------------
# Shared helpers — auth, rate limit, heartbeat
# ---------------------------------------------------------------------------

async def _authenticate(ws: WebSocket) -> bool:
    """Validate token from query params. Returns False and closes WS if invalid."""
    if not settings.ws_auth_token:
        return True  # auth disabled when token is empty

    token = ws.query_params.get("token", "")
    if token != settings.ws_auth_token:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        logger.warning("WS auth failed from %s", ws.client.host if ws.client else "unknown")
        return False
    return True


async def _check_rate_limit(ws: WebSocket) -> bool:
    """Check IP is under connection limit. Returns False and closes WS if exceeded."""
    ip = ws.client.host if ws.client else "unknown"
    if not _rate_limiter.check(ip, settings.ws_max_connections_per_ip):
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        logger.warning("WS rate limit exceeded for %s", ip)
        return False
    return True


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


async def _ws_lifecycle(ws: WebSocket, manager) -> None:
    """Shared lifecycle: auth → rate limit → connect → heartbeat → read loop → cleanup."""
    if not await _authenticate(ws):
        return
    if not await _check_rate_limit(ws):
        return

    ip = ws.client.host if ws.client else "unknown"
    _rate_limiter.increment(ip)

    await manager.connect(ws)
    heartbeat_task = asyncio.create_task(_heartbeat(ws))
    try:
        while True:
            await ws.receive_text()  # keep-alive read loop
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        await manager.disconnect(ws)
        _rate_limiter.decrement(ip)


# ---------------------------------------------------------------------------
# WebSocket endpoints
# ---------------------------------------------------------------------------

@router.websocket("/ws/market")
async def market_websocket(ws: WebSocket) -> None:
    """Market data channel: full MarketSnapshot."""
    from app.main import market_ws_manager
    await _ws_lifecycle(ws, market_ws_manager)


@router.websocket("/ws/foreign")
async def foreign_websocket(ws: WebSocket) -> None:
    """Foreign flow channel: ForeignSummary only."""
    from app.main import foreign_ws_manager
    await _ws_lifecycle(ws, foreign_ws_manager)


@router.websocket("/ws/index")
async def index_websocket(ws: WebSocket) -> None:
    """Index channel: VN30 + VNINDEX data."""
    from app.main import index_ws_manager
    await _ws_lifecycle(ws, index_ws_manager)


@router.websocket("/ws/alerts")
async def alerts_websocket(ws: WebSocket) -> None:
    """Alerts channel: real-time analytics alerts."""
    from app.main import alerts_ws_manager
    await _ws_lifecycle(ws, alerts_ws_manager)

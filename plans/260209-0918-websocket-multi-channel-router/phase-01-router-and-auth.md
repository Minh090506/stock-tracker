# Phase 1: Router and Auth

**Priority:** P1
**Status:** Pending
**Effort:** 1.5h

## Context Links
- Plan: [plan.md](./plan.md)
- Current endpoint: `backend/app/websocket/endpoint.py`
- ConnectionManager: `backend/app/websocket/connection_manager.py`
- Config: `backend/app/config.py`

## Overview
Create multi-channel WebSocket router with token-based authentication and IP-based rate limiting.

## Key Insights
- ConnectionManager is already generic — reuse for all 3 channels
- Auth must happen BEFORE `ws.accept()` to reject early
- FastAPI WebSocket provides `client.host` for IP tracking
- Query params accessible via `ws.query_params.get("token")`

## Requirements

### Functional
- 3 WebSocket endpoints: `/ws/market`, `/ws/foreign`, `/ws/index`
- Token validation via query param `?token=xxx`
- Rate limiting: max N connections per IP (configurable)
- Heartbeat mechanism (reuse from endpoint.py)

### Non-Functional
- File under 200 LOC
- No code duplication
- Clear error messages for auth/rate limit failures

## Architecture

### Auth Flow
```
Client connects → Extract token from query params → Validate against config
→ If invalid: close with 403 → If valid: check rate limit
→ If exceeded: close with 429 → If OK: accept WebSocket
```

### Rate Limiter
```python
class RateLimiter:
    _connections: dict[str, int]  # ip → count

    def check(ip: str, limit: int) -> bool
    def increment(ip: str) -> None
    def decrement(ip: str) -> None
```

### Router Structure
```python
router = APIRouter()

# Shared helpers
async def _authenticate(ws: WebSocket) -> bool
async def _heartbeat(ws: WebSocket) -> None

# 3 endpoints (same pattern)
@router.websocket("/ws/market")
@router.websocket("/ws/foreign")
@router.websocket("/ws/index")
```

## Related Code Files

### To Create
- `backend/app/websocket/router.py` — new multi-channel router

### To Modify
- `backend/app/config.py` — add ws_auth_token, ws_max_connections_per_ip

### To Keep (no changes)
- `backend/app/websocket/connection_manager.py`
- `backend/app/websocket/broadcast_loop.py`

### To Delete (Phase 2)
- `backend/app/websocket/endpoint.py` — replaced by router.py

## Implementation Steps

### 1. Add Config Settings
**File:** `backend/app/config.py`

**Add after line 39:**
```python
# WebSocket authentication & rate limiting
ws_auth_token: str = ""              # Token for WS auth (empty = disabled)
ws_max_connections_per_ip: int = 5   # Max concurrent connections per IP
```

### 2. Create Rate Limiter
**File:** `backend/app/websocket/router.py` (new file)

**Lines 1-30:**
```python
"""Multi-channel WebSocket router with authentication and rate limiting."""

import asyncio
import logging
from collections import defaultdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


class RateLimiter:
    """Track WebSocket connections per IP address."""

    def __init__(self):
        self._connections: dict[str, int] = defaultdict(int)

    def check(self, ip: str, limit: int) -> bool:
        """Return True if IP is under the limit."""
        return self._connections[ip] < limit

    def increment(self, ip: str) -> None:
        self._connections[ip] += 1

    def decrement(self, ip: str) -> None:
        self._connections[ip] = max(0, self._connections[ip] - 1)


_rate_limiter = RateLimiter()
```

### 3. Create Auth Helper
**Add to `router.py` after RateLimiter:**

```python
async def _authenticate(ws: WebSocket) -> bool:
    """Validate token from query params. Close WS with 403 if invalid."""
    if not settings.ws_auth_token:
        return True  # Auth disabled

    token = ws.query_params.get("token", "")
    if token != settings.ws_auth_token:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        logger.warning("WS auth failed from %s", ws.client.host if ws.client else "unknown")
        return False
    return True


async def _check_rate_limit(ws: WebSocket) -> bool:
    """Check if IP is under connection limit. Close with 429 if exceeded."""
    ip = ws.client.host if ws.client else "unknown"
    if not _rate_limiter.check(ip, settings.ws_max_connections_per_ip):
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        logger.warning("WS rate limit exceeded for %s", ip)
        return False
    return True
```

### 4. Copy Heartbeat Helper
**Add to `router.py`:**

```python
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
```

### 5. Create `/ws/market` Endpoint
**Add to `router.py`:**

```python
@router.websocket("/ws/market")
async def market_websocket(ws: WebSocket) -> None:
    """Market data channel: full MarketSnapshot."""
    from app.main import market_ws_manager

    # Auth + rate limit BEFORE accept
    if not await _authenticate(ws):
        return
    if not await _check_rate_limit(ws):
        return

    ip = ws.client.host if ws.client else "unknown"
    _rate_limiter.increment(ip)

    await market_ws_manager.connect(ws)
    heartbeat_task = asyncio.create_task(_heartbeat(ws))
    try:
        while True:
            await ws.receive_text()  # Keep-alive loop
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        await market_ws_manager.disconnect(ws)
        _rate_limiter.decrement(ip)
```

### 6. Create `/ws/foreign` Endpoint
**Add to `router.py`:**

```python
@router.websocket("/ws/foreign")
async def foreign_websocket(ws: WebSocket) -> None:
    """Foreign flow channel: ForeignSummary only."""
    from app.main import foreign_ws_manager

    if not await _authenticate(ws):
        return
    if not await _check_rate_limit(ws):
        return

    ip = ws.client.host if ws.client else "unknown"
    _rate_limiter.increment(ip)

    await foreign_ws_manager.connect(ws)
    heartbeat_task = asyncio.create_task(_heartbeat(ws))
    try:
        while True:
            await ws.receive_text()
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        await foreign_ws_manager.disconnect(ws)
        _rate_limiter.decrement(ip)
```

### 7. Create `/ws/index` Endpoint
**Add to `router.py`:**

```python
@router.websocket("/ws/index")
async def index_websocket(ws: WebSocket) -> None:
    """Index channel: VN30 + VNINDEX only."""
    from app.main import index_ws_manager

    if not await _authenticate(ws):
        return
    if not await _check_rate_limit(ws):
        return

    ip = ws.client.host if ws.client else "unknown"
    _rate_limiter.increment(ip)

    await index_ws_manager.connect(ws)
    heartbeat_task = asyncio.create_task(_heartbeat(ws))
    try:
        while True:
            await ws.receive_text()
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        await index_ws_manager.disconnect(ws)
        _rate_limiter.decrement(ip)
```

## Todo List
- [ ] Add config settings for ws_auth_token and ws_max_connections_per_ip
- [ ] Create backend/app/websocket/router.py
- [ ] Implement RateLimiter class
- [ ] Implement _authenticate helper
- [ ] Implement _check_rate_limit helper
- [ ] Copy _heartbeat helper from endpoint.py
- [ ] Create /ws/market endpoint
- [ ] Create /ws/foreign endpoint
- [ ] Create /ws/index endpoint
- [ ] Verify file is under 200 LOC
- [ ] Run linter (ignore formatting, check syntax only)

## Success Criteria
- `router.py` created with 3 endpoints
- Auth rejects connections without valid token (if configured)
- Rate limiter enforces per-IP connection limit
- File under 200 LOC
- No syntax errors

## Risk Assessment
**Risk:** Circular import from `app.main`
**Mitigation:** Import managers inside endpoint functions (same pattern as endpoint.py)

**Risk:** Rate limiter leaks connections on crash
**Mitigation:** Always decrement in `finally` block

**Risk:** Token in query params visible in logs
**Mitigation:** Document this limitation (acceptable for internal tool)

## Security Considerations
- Token transmitted in URL (visible in server logs, browser history)
- No encryption beyond HTTPS/WSS
- Simple IP-based rate limiting (can be bypassed with proxies)
- Acceptable for internal tool, not public API

## Next Steps
Phase 2: Update broadcast loop and wire router to main.py

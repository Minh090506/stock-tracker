---
title: "WebSocket Broadcast Server"
description: "FastAPI WebSocket endpoint broadcasting full MarketSnapshot to all connected clients every 1s"
status: ✅ complete
priority: P1
effort: 3h
branch: master
tags: [websocket, backend, real-time, phase-4]
created: 2026-02-08
completed: 2026-02-08
---

# WebSocket Broadcast Server

## Summary

Add a WebSocket endpoint `/ws/market` that broadcasts the full `MarketSnapshot` to all connected clients every 1 second. Single stream, no subscriptions, per-client async queues, app-level heartbeat.

## Architecture

```
MarketDataProcessor.get_market_snapshot()
        |
   [1s broadcast loop]
        |
   ConnectionManager
   ├── client_1 → asyncio.Queue(50) → WebSocket
   ├── client_2 → asyncio.Queue(50) → WebSocket
   └── client_N → asyncio.Queue(50) → WebSocket
```

## Phases

| # | Phase | Status | Files |
|---|-------|--------|-------|
| 1 | [ConnectionManager + WS endpoint](phase-01-connection-manager.md) | ✅ complete | `websocket/connection_manager.py`, `websocket/endpoint.py`, `websocket/__init__.py` |
| 2 | [Broadcast loop + lifespan](phase-02-broadcast-loop.md) | ✅ complete | `websocket/broadcast_loop.py`, `main.py` |
| 3 | [Tests](phase-03-tests.md) | ✅ complete | `tests/test_connection_manager.py`, `tests/test_websocket_endpoint.py` |

## Key Dependencies

- `MarketDataProcessor.get_market_snapshot()` — already exists, returns `MarketSnapshot` Pydantic model
- `websockets>=14.0` — already in requirements.txt
- FastAPI native WebSocket support — no extra deps needed
- `backend/app/websocket/__init__.py` — exists, currently empty

## Design Decisions

1. Full snapshot broadcast (no deltas) — KISS, client always has complete state
2. Single `/ws/market` stream — no room subscriptions
3. Per-client `asyncio.Queue(maxsize=50)` — drop oldest on overflow (slow clients don't block fast ones)
4. App-level heartbeat: server sends ping every 30s, disconnects if no pong within 10s
5. Broadcast interval: 1s (configurable via `Settings.ws_broadcast_interval`)

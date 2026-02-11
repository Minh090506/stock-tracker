"""Base Locust user for WebSocket load testing.

Connects to a FastAPI WS endpoint, receives JSON messages,
and reports latency/throughput to Locust's event system.
"""

import asyncio
import json
import os
import time
import logging
from contextlib import suppress

import websockets
from locust import User, events

logger = logging.getLogger(__name__)

WS_TOKEN = os.getenv("WS_AUTH_TOKEN", "")


class WebSocketUser(User):
    """Base class for WebSocket load test users.

    Subclasses set `ws_path` (e.g., "/ws/market") and override
    `on_message(data: dict)` for custom assertions.
    """

    abstract = True
    ws_path: str = "/ws/market"

    def __init__(self, environment):
        super().__init__(environment)
        self._ws = None
        self._loop = None

    def on_start(self):
        """Create event loop and connect to WebSocket."""
        self._loop = asyncio.new_event_loop()
        self._loop.run_until_complete(self._connect())

    def on_stop(self):
        """Disconnect and close event loop."""
        if self._ws:
            self._loop.run_until_complete(self._disconnect())
        if self._loop:
            self._loop.close()

    async def _connect(self):
        """Connect to WebSocket endpoint and report latency."""
        host = self.environment.host.replace("http://", "ws://").replace(
            "https://", "wss://"
        )
        url = f"{host}{self.ws_path}"
        if WS_TOKEN:
            url += f"?token={WS_TOKEN}"

        start = time.monotonic()
        try:
            self._ws = await asyncio.wait_for(
                websockets.connect(url), timeout=15.0
            )
            elapsed_ms = (time.monotonic() - start) * 1000
            events.request.fire(
                request_type="WS",
                name=f"connect {self.ws_path}",
                response_time=elapsed_ms,
                response_length=0,
                exception=None,
                context={},
            )
        except Exception as e:
            elapsed_ms = (time.monotonic() - start) * 1000
            events.request.fire(
                request_type="WS",
                name=f"connect {self.ws_path}",
                response_time=elapsed_ms,
                response_length=0,
                exception=e,
                context={},
            )

    async def _disconnect(self):
        """Close WebSocket connection gracefully."""
        with suppress(Exception):
            await self._ws.close()

    async def receive_one(self) -> dict | None:
        """Receive one WS message, report latency to Locust."""
        start = time.monotonic()
        try:
            raw = await asyncio.wait_for(self._ws.recv(), timeout=10.0)
            elapsed_ms = (time.monotonic() - start) * 1000
            data = json.loads(raw) if isinstance(raw, str) else {}
            events.request.fire(
                request_type="WS",
                name=f"recv {self.ws_path}",
                response_time=elapsed_ms,
                response_length=len(raw),
                exception=None,
                context={},
            )
            return data
        except Exception as e:
            elapsed_ms = (time.monotonic() - start) * 1000
            events.request.fire(
                request_type="WS",
                name=f"recv {self.ws_path}",
                response_time=elapsed_ms,
                response_length=0,
                exception=e,
                context={},
            )
            return None

    def on_message(self, data: dict):
        """Override in subclass for custom validation."""
        pass

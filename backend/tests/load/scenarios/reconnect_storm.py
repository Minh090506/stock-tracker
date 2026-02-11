"""WS stress test: 100 clients disconnect/reconnect every 10s.

Measures reconnect latency and connection stability under churn.
Run: locust -f locustfile.py ReconnectUser --host http://localhost:8000
"""

import time

from locust import task, constant_pacing, events

from backend.tests.load.websocket_user import WebSocketUser


class ReconnectUser(WebSocketUser):
    """WebSocket user that cycles disconnect/reconnect every 10 seconds.

    Tests connection manager cleanup and reconnection handling.
    Reports reconnect latency as a separate metric.
    """

    ws_path = "/ws/market"
    wait_time = constant_pacing(10.0)  # Reconnect cycle every 10s

    @task
    def reconnect_cycle(self):
        """Receive a few messages, then disconnect and reconnect."""
        # Receive 3 messages to simulate brief session
        for _ in range(3):
            data = self._loop.run_until_complete(self.receive_one())
            if data is None:
                break

        # Measure full reconnect cycle
        start = time.monotonic()

        # Disconnect
        self._loop.run_until_complete(self._disconnect())

        # Reconnect
        self._loop.run_until_complete(self._connect())

        elapsed_ms = (time.monotonic() - start) * 1000

        events.request.fire(
            request_type="WS",
            name="reconnect /ws/market",
            response_time=elapsed_ms,
            response_length=0,
            exception=None,
            context={},
        )

"""WS load test: 500 concurrent connections to /ws/market.

Measures msg/sec throughput and per-message receive latency.
Run: locust -f locustfile.py MarketStreamUser --host http://localhost:8000
"""

from locust import task, between, events

from backend.tests.load.websocket_user import WebSocketUser


class MarketStreamUser(WebSocketUser):
    """WebSocket user that subscribes to /ws/market and receives continuous updates.

    Validates that MarketSnapshot contains expected keys:
    quotes, indices, foreign, derivatives, prices
    """

    ws_path = "/ws/market"
    wait_time = between(0.01, 0.05)  # Fast polling loop for continuous receive

    @task
    def receive_market_data(self):
        """Receive and validate one market snapshot."""
        data = self._loop.run_until_complete(self.receive_one())
        if data:
            self.on_message(data)

    def on_message(self, data: dict):
        """Validate MarketSnapshot structure."""
        # Skip status/heartbeat messages
        if data.get("type") in ("status", "ping", "pong"):
            return

        expected_keys = {"quotes", "indices", "foreign", "derivatives", "prices"}
        missing = expected_keys - set(data.keys())
        if missing:
            events.request.fire(
                request_type="WS",
                name="validate /ws/market",
                response_time=0,
                response_length=0,
                exception=ValueError(f"Missing keys: {missing}"),
                context={},
            )

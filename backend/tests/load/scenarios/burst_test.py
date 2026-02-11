"""Mixed load test: simulate 9:00 AM market open burst.

300 WS connections + 500 REST clients ramping up in 30s.
Uses LoadTestShape for custom ramp profile.
Run: locust -f locustfile.py BurstWsUser BurstRestUser --host http://localhost:8000
"""

from locust import HttpUser, task, between, LoadTestShape

from backend.tests.load.websocket_user import WebSocketUser


class BurstWsUser(WebSocketUser):
    """WebSocket user for burst scenario (37.5% of users)."""

    ws_path = "/ws/market"
    wait_time = between(0.05, 0.2)
    weight = 3  # 300 out of 800 total

    @task
    def receive_data(self):
        """Receive market data during burst."""
        self._loop.run_until_complete(self.receive_one())


class BurstRestUser(HttpUser):
    """REST user for burst scenario (62.5% of users)."""

    wait_time = between(0.1, 0.5)
    weight = 5  # 500 out of 800 total

    @task(5)
    def snapshot(self):
        """Fetch market snapshot."""
        self.client.get("/api/market/snapshot", name="/api/market/snapshot")

    @task(3)
    def foreign(self):
        """Fetch foreign detail."""
        self.client.get("/api/market/foreign-detail", name="/api/market/foreign-detail")

    @task(1)
    def alerts(self):
        """Fetch alerts."""
        self.client.get("/api/market/alerts?limit=50", name="/api/market/alerts")


class MarketOpenBurst(LoadTestShape):
    """Custom load shape: 30s ramp -> 2min sustain -> 30s ramp down.

    Simulates VN market 9:00 AM ATO auction spike pattern.
    Total duration: 3 minutes
    Peak users: 800 (300 WS + 500 REST based on weights)
    """

    stages = [
        {"duration": 30, "users": 800, "spawn_rate": 27},  # Ramp up in 30s
        {"duration": 150, "users": 800, "spawn_rate": 1},  # Sustain for 2min
        {"duration": 180, "users": 0, "spawn_rate": 50},  # Ramp down in 30s
    ]

    def tick(self):
        """Return (user_count, spawn_rate) for current time."""
        run_time = self.get_run_time()
        for stage in self.stages:
            if run_time < stage["duration"]:
                return (stage["users"], stage["spawn_rate"])
        return None

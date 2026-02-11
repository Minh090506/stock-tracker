"""REST load test: 500 clients polling /api/market/foreign-detail every 2s.

Measures p50/p95/p99 latency and error rate.
Run: locust -f locustfile.py ForeignFlowUser --host http://localhost:8000
"""

from locust import HttpUser, task, constant_pacing


class ForeignFlowUser(HttpUser):
    """REST user that polls foreign investor detail at fixed 2s intervals.

    Simulates dashboard clients refreshing foreign flow data.
    Validates response contains 'summary' and 'stocks' keys.
    """

    wait_time = constant_pacing(2.0)  # Exactly 1 request per 2s per user

    @task
    def poll_foreign_detail(self):
        """Poll foreign detail endpoint and validate response."""
        with self.client.get(
            "/api/market/foreign-detail",
            name="/api/market/foreign-detail",
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status {resp.status_code}")
            else:
                try:
                    data = resp.json()
                    if "summary" not in data or "stocks" not in data:
                        resp.failure("Missing 'summary' or 'stocks' key")
                except Exception as e:
                    resp.failure(f"JSON parse error: {e}")

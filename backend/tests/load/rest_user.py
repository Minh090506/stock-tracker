"""REST load test user — hits market endpoints with configurable weights."""

from locust import HttpUser, task, between


class RestUser(HttpUser):
    """General REST API load test user.

    Hits main market endpoints with weighted distribution:
    - /api/market/snapshot: 50% (most common)
    - /api/market/foreign-detail: 30%
    - /api/vn30-components: 15%
    - /api/market/alerts: 5%
    """

    wait_time = between(0.1, 0.5)

    @task(5)
    def snapshot(self):
        """Fetch full market snapshot."""
        self.client.get("/api/market/snapshot", name="/api/market/snapshot")

    @task(3)
    def foreign_detail(self):
        """Fetch foreign investor detail."""
        self.client.get("/api/market/foreign-detail", name="/api/market/foreign-detail")

    @task(2)
    def vn30_components(self):
        """Fetch VN30 component list."""
        self.client.get("/api/vn30-components", name="/api/vn30-components")

    @task(1)
    def alerts(self):
        """Fetch recent alerts."""
        self.client.get("/api/market/alerts?limit=50", name="/api/market/alerts")

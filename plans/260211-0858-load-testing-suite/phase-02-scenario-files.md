# Phase 2: Scenario Files

## Context Links

- [Phase 1 — Locust Core](./phase-01-locust-core-and-helpers.md) — WebSocketUser base class
- [WebSocket Router](/Users/minh/Projects/stock-tracker/backend/app/websocket/router.py) — endpoints: `/ws/market`, `/ws/foreign`, `/ws/alerts`
- [Market Router](/Users/minh/Projects/stock-tracker/backend/app/routers/market_router.py) — REST endpoints
- [DataPublisher](/Users/minh/Projects/stock-tracker/backend/app/websocket/data_publisher.py) — 500ms throttle per channel
- [ConnectionManager](/Users/minh/Projects/stock-tracker/backend/app/websocket/connection_manager.py) — queue maxsize=50

## Overview

- **Priority**: P1
- **Status**: pending
- **Effort**: 1.5h

Four scenario files, each < 200 LOC, covering WS streaming, REST polling, burst load, and reconnect storms.

## Key Insights

1. **DataPublisher throttle**: 500ms trailing-edge per channel. Max theoretical msg rate = 2 msg/s per client regardless of load. WS latency measurement reflects queue wait + send time, not processing time.
2. **Queue overflow**: ConnectionManager drops oldest message when queue full (maxsize=50). Under heavy load, clients may miss messages — this is expected behavior, not an error.
3. **REST endpoints are sync reads**: All market endpoints read from in-memory processor state. No DB calls. Expected latency < 5ms under normal conditions.
4. **Burst pattern**: VN market opens at 9:00 AM with ATO auction. Simulate by ramping up users rapidly then sustaining.

## Requirements

### Functional
- `market_stream.py`: 500 concurrent WS connections to `/ws/market`, measure msg/sec per client
- `foreign_flow.py`: 500 clients polling `/api/market/foreign-detail` every 2s
- `burst_test.py`: Ramp 0 -> 300 WS + 500 REST in 30s, sustain 2min
- `reconnect_storm.py`: 100 clients disconnect/reconnect simultaneously every 10s

### Non-functional
- Each file < 200 LOC
- Assertions checked via Locust event listeners (fail on threshold breach)
- All measurements reported to Locust stats for CSV export

## Architecture

```
scenarios/
├── market_stream.py       # WS /ws/market — subscribe all VN30, measure throughput
├── foreign_flow.py        # REST /api/market/foreign-detail — 500 pollers at 2s interval
├── burst_test.py          # Mixed WS+REST — simulate 9:00 AM market open spike
└── reconnect_storm.py     # WS disconnect/reconnect — 100 clients cycling every 10s
```

## Related Code Files

### Files to Create

| File | Purpose | LOC est. |
|------|---------|----------|
| `backend/tests/load/scenarios/market_stream.py` | WS streaming load test | ~80 |
| `backend/tests/load/scenarios/foreign_flow.py` | REST polling load test | ~50 |
| `backend/tests/load/scenarios/burst_test.py` | Mixed burst simulation | ~90 |
| `backend/tests/load/scenarios/reconnect_storm.py` | Reconnect stress test | ~70 |

## Implementation Steps

### Step 1: Create `market_stream.py`

WS user that connects to `/ws/market` and continuously receives messages. Measures:
- Per-message latency (time from recv call to response)
- Message count (throughput via Locust stats)
- Validates message has expected keys (quotes, indices, foreign, derivatives)

```python
"""WS load test: 500 concurrent connections to /ws/market.

Measures msg/sec throughput and per-message receive latency.
Run: locust -f locustfile.py --class-picker MarketStreamUser
"""

import time
from locust import task, between, events

from backend.tests.load.websocket_user import WebSocketUser


class MarketStreamUser(WebSocketUser):
    ws_path = "/ws/market"
    wait_time = between(0.01, 0.05)  # fast polling loop

    @task
    def receive_market_data(self):
        data = self._loop.run_until_complete(self.receive_one())
        if data:
            self.on_message(data)

    def on_message(self, data: dict):
        # Validate MarketSnapshot structure (skip "status" type messages)
        if data.get("type") == "status":
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
```

### Step 2: Create `foreign_flow.py`

REST user that polls `/api/market/foreign-detail` every 2 seconds. Simulates 500 dashboard clients.

```python
"""REST load test: 500 clients polling /api/market/foreign-detail every 2s.

Measures p50/p95/p99 latency and error rate.
"""

from locust import HttpUser, task, constant_pacing


class ForeignFlowUser(HttpUser):
    wait_time = constant_pacing(2.0)  # exactly 1 request per 2s per user

    @task
    def poll_foreign_detail(self):
        with self.client.get(
            "/api/market/foreign-detail",
            name="/api/market/foreign-detail",
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"Status {resp.status_code}")
            else:
                data = resp.json()
                if "summary" not in data or "stocks" not in data:
                    resp.failure("Missing summary or stocks key")
```

### Step 3: Create `burst_test.py`

Mixed scenario simulating market open. Uses Locust's `LoadTestShape` to define a custom ramp:
- 0-30s: ramp to 300 WS + 500 REST
- 30s-2m30s: sustain
- 2m30s-3m: ramp down

```python
"""Mixed load test: simulate 9:00 AM market open burst.

300 WS connections + 500 REST clients ramping up in 30s.
Uses LoadTestShape for custom ramp profile.
"""

from locust import HttpUser, task, between, LoadTestShape

from backend.tests.load.websocket_user import WebSocketUser


class BurstWsUser(WebSocketUser):
    ws_path = "/ws/market"
    wait_time = between(0.05, 0.2)
    weight = 3  # 300 out of 800 total = 37.5%

    @task
    def receive_data(self):
        self._loop.run_until_complete(self.receive_one())


class BurstRestUser(HttpUser):
    wait_time = between(0.1, 0.5)
    weight = 5  # 500 out of 800 total = 62.5%

    @task(5)
    def snapshot(self):
        self.client.get("/api/market/snapshot", name="/api/market/snapshot")

    @task(3)
    def foreign(self):
        self.client.get("/api/market/foreign-detail", name="/api/market/foreign-detail")

    @task(1)
    def alerts(self):
        self.client.get("/api/market/alerts?limit=50", name="/api/market/alerts")


class MarketOpenBurst(LoadTestShape):
    """Custom load shape: ramp -> sustain -> ramp down."""

    stages = [
        {"duration": 30, "users": 800, "spawn_rate": 27},   # ramp up
        {"duration": 150, "users": 800, "spawn_rate": 1},   # sustain
        {"duration": 180, "users": 0, "spawn_rate": 50},    # ramp down
    ]

    def tick(self):
        run_time = self.get_run_time()
        for stage in self.stages:
            if run_time < stage["duration"]:
                return (stage["users"], stage["spawn_rate"])
        return None
```

### Step 4: Create `reconnect_storm.py`

WS user that connects, receives a few messages, disconnects, and reconnects. Measures connect latency under reconnect storm conditions.

```python
"""WS stress test: 100 clients disconnect/reconnect every 10s.

Measures reconnect latency and connection stability.
"""

import asyncio
import time
from contextlib import suppress

from locust import task, constant_pacing, events

from backend.tests.load.websocket_user import WebSocketUser


class ReconnectUser(WebSocketUser):
    ws_path = "/ws/market"
    wait_time = constant_pacing(10.0)  # reconnect cycle every 10s

    @task
    def reconnect_cycle(self):
        """Receive a few messages, disconnect, reconnect."""
        # Receive 3-5 messages
        for _ in range(3):
            self._loop.run_until_complete(self.receive_one())

        # Disconnect
        start = time.monotonic()
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
```

## Assertions Configuration

Create `backend/tests/load/assertions.py` (~40 LOC) — event listener that fails the Locust run if thresholds breached:

```python
"""Locust event listener for performance assertions.

Attach via: --config or import in locustfile.
Thresholds:
  - WS recv p99 < 100ms
  - REST p95 < 200ms
  - Error rate < 1%
"""

import logging
from locust import events

logger = logging.getLogger(__name__)

WS_P99_LIMIT_MS = 100
REST_P95_LIMIT_MS = 200
ERROR_RATE_LIMIT = 0.01  # 1%


@events.quitting.add_listener
def check_assertions(environment, **kwargs):
    stats = environment.runner.stats
    failed = False

    for entry in stats.entries.values():
        if entry.num_requests == 0:
            continue

        error_rate = entry.num_failures / entry.num_requests
        if error_rate > ERROR_RATE_LIMIT:
            logger.error(
                "FAIL: %s error rate %.2f%% > %.2f%%",
                entry.name, error_rate * 100, ERROR_RATE_LIMIT * 100,
            )
            failed = True

        if entry.method == "WS" and "recv" in entry.name:
            p99 = entry.get_response_time_percentile(0.99) or 0
            if p99 > WS_P99_LIMIT_MS:
                logger.error(
                    "FAIL: %s p99=%dms > %dms",
                    entry.name, p99, WS_P99_LIMIT_MS,
                )
                failed = True

        if entry.method in ("GET", "POST"):
            p95 = entry.get_response_time_percentile(0.95) or 0
            if p95 > REST_P95_LIMIT_MS:
                logger.error(
                    "FAIL: %s p95=%dms > %dms",
                    entry.name, p95, REST_P95_LIMIT_MS,
                )
                failed = True

    if failed:
        environment.process_exit_code = 1
        logger.error("Load test FAILED — thresholds breached")
    else:
        logger.info("Load test PASSED — all thresholds met")
```

## Todo List

- [ ] Create `backend/tests/load/scenarios/__init__.py`
- [ ] Create `backend/tests/load/scenarios/market_stream.py` (~80 LOC)
- [ ] Create `backend/tests/load/scenarios/foreign_flow.py` (~50 LOC)
- [ ] Create `backend/tests/load/scenarios/burst_test.py` (~90 LOC)
- [ ] Create `backend/tests/load/scenarios/reconnect_storm.py` (~70 LOC)
- [ ] Create `backend/tests/load/assertions.py` (~40 LOC)
- [ ] Update `locustfile.py` to import assertions module
- [ ] Verify each scenario runs independently with 5 users for 30s

## Success Criteria

- Each scenario runs headless without errors (5 users, 30s)
- MarketStreamUser receives messages at ~2/sec (throttle-limited)
- ForeignFlowUser gets 200 OK responses
- BurstUser ramp shape visible in Locust web UI
- ReconnectUser shows reconnect latency in stats
- Assertions module fires on `quitting` event

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| No live data during test | High | Tests measure infra latency, not data correctness. Backend returns empty snapshots when SSI disconnected — still valid for load testing. |
| WS throttle masks true latency | Medium | Document that 500ms throttle is a feature, not a bottleneck. Actual server processing is <5ms. |
| Locust greenlet vs asyncio conflict | Medium | Each WebSocketUser creates its own event loop. Tested pattern from locust-plugins. |

## Security Considerations

- No credentials in scenario files
- Auth token via env var only
- Rate limit bypass via env var, not code change

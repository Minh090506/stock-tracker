"""Locust event listener for performance assertions.

Attach via import in locustfile.py.
Sets process exit code to 1 if thresholds breached.

Thresholds:
  - WS recv p99 < 100ms
  - REST p95 < 200ms
  - Error rate < 1%
"""

import logging

from locust import events

logger = logging.getLogger(__name__)

# Performance thresholds
WS_P99_LIMIT_MS = 100
REST_P95_LIMIT_MS = 200
ERROR_RATE_LIMIT = 0.01  # 1%


@events.quitting.add_listener
def check_assertions(environment, **kwargs):
    """Check performance assertions when Locust is quitting.

    Sets environment.process_exit_code = 1 if any threshold breached.
    """
    stats = environment.runner.stats
    failed = False

    for entry in stats.entries.values():
        if entry.num_requests == 0:
            continue

        # Check error rate
        error_rate = entry.num_failures / entry.num_requests
        if error_rate > ERROR_RATE_LIMIT:
            logger.error(
                "FAIL: %s error rate %.2f%% > %.2f%%",
                entry.name,
                error_rate * 100,
                ERROR_RATE_LIMIT * 100,
            )
            failed = True

        # Check WS p99 latency
        if entry.method == "WS" and "recv" in entry.name:
            p99 = entry.get_response_time_percentile(0.99) or 0
            if p99 > WS_P99_LIMIT_MS:
                logger.error(
                    "FAIL: %s p99=%dms > %dms",
                    entry.name,
                    p99,
                    WS_P99_LIMIT_MS,
                )
                failed = True

        # Check REST p95 latency
        if entry.method in ("GET", "POST"):
            p95 = entry.get_response_time_percentile(0.95) or 0
            if p95 > REST_P95_LIMIT_MS:
                logger.error(
                    "FAIL: %s p95=%dms > %dms",
                    entry.name,
                    p95,
                    REST_P95_LIMIT_MS,
                )
                failed = True

    if failed:
        environment.process_exit_code = 1
        logger.error("Load test FAILED — thresholds breached")
    else:
        logger.info("Load test PASSED — all thresholds met")

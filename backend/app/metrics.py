"""Prometheus metrics definitions for the VN Stock Tracker.

All metrics are defined here as a single registry. Services import
and increment/observe these directly — no wrapper abstractions needed.
"""

from prometheus_client import Counter, Gauge, Histogram

# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------
ws_connections_active = Gauge(
    "ws_connections_active",
    "Number of active WebSocket connections",
    ["channel"],
)

ws_messages_sent_total = Counter(
    "ws_messages_sent_total",
    "Total WebSocket messages sent to clients",
    ["channel"],
)

# ---------------------------------------------------------------------------
# SSI stream
# ---------------------------------------------------------------------------
ssi_messages_received_total = Counter(
    "ssi_messages_received_total",
    "Total messages received from SSI stream",
    ["channel"],
)

# ---------------------------------------------------------------------------
# Trade classification
# ---------------------------------------------------------------------------
trade_classification_duration_seconds = Histogram(
    "trade_classification_duration_seconds",
    "Time spent classifying a single trade",
    buckets=(0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05),
)

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
db_write_duration_seconds = Histogram(
    "db_write_duration_seconds",
    "Duration of database batch write (COPY) operations",
    ["table"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

db_pool_active_connections = Gauge(
    "db_pool_active_connections",
    "Number of active connections in the asyncpg pool",
)

# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------
alert_signals_fired_total = Counter(
    "alert_signals_fired_total",
    "Total alert signals fired",
    ["signal_type"],
)

# ---------------------------------------------------------------------------
# HTTP (populated by middleware)
# ---------------------------------------------------------------------------
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path", "status_code"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)

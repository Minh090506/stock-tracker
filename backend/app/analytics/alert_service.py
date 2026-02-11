"""AlertService — in-memory alert buffer with dedup and subscriber notifications.

Responsibilities:
- Buffer recent alerts (deque, max 500)
- Dedup: skip if same (alert_type, symbol) registered within 60s
- Filter by type/severity
- Subscribe/notify pattern for new alert consumers (e.g. WebSocket broadcast)
- Daily reset clears buffer and cooldowns
"""

import logging
from collections import deque
from datetime import datetime
from typing import Callable

from app.analytics.alert_models import Alert, AlertSeverity, AlertType
from app.metrics import alert_signals_fired_total

logger = logging.getLogger(__name__)

# Dedup window: ignore duplicate (type, symbol) alerts within this period
DEDUP_WINDOW_SECONDS = 60
MAX_BUFFER_SIZE = 500

# Subscriber receives an Alert when a new alert is registered
AlertSubscriber = Callable[[Alert], None]


class AlertService:
    """Central alert manager for the analytics engine."""

    def __init__(self):
        self._buffer: deque[Alert] = deque(maxlen=MAX_BUFFER_SIZE)
        # Dedup: (alert_type, symbol) → last alert timestamp
        self._cooldowns: dict[tuple[AlertType, str], datetime] = {}
        self._subscribers: list[AlertSubscriber] = []

    def register_alert(self, alert: Alert) -> bool:
        """Register a new alert. Returns True if accepted, False if deduped.

        Dedup rule: same (alert_type, symbol) within 60s → skip.
        """
        key = (alert.alert_type, alert.symbol)
        now = datetime.now()

        # Check dedup cooldown
        last_seen = self._cooldowns.get(key)
        if last_seen and (now - last_seen).total_seconds() < DEDUP_WINDOW_SECONDS:
            logger.debug(
                "Alert deduped: %s %s (within %ds)",
                alert.alert_type, alert.symbol, DEDUP_WINDOW_SECONDS,
            )
            return False

        # Accept alert
        self._cooldowns[key] = now
        self._buffer.append(alert)
        alert_signals_fired_total.labels(signal_type=alert.alert_type.value).inc()
        logger.info(
            "Alert registered: [%s] %s %s — %s",
            alert.severity.value, alert.alert_type.value,
            alert.symbol, alert.message,
        )

        # Notify subscribers
        self._notify(alert)
        return True

    def get_recent_alerts(
        self,
        limit: int = 50,
        type_filter: AlertType | None = None,
        severity_filter: AlertSeverity | None = None,
    ) -> list[Alert]:
        """Return recent alerts (newest first), optionally filtered."""
        alerts = list(self._buffer)
        if type_filter is not None:
            alerts = [a for a in alerts if a.alert_type == type_filter]
        if severity_filter is not None:
            alerts = [a for a in alerts if a.severity == severity_filter]
        # Newest first
        alerts.reverse()
        return alerts[:limit]

    def subscribe(self, callback: AlertSubscriber):
        """Register a subscriber to receive new alerts."""
        self._subscribers.append(callback)

    def unsubscribe(self, callback: AlertSubscriber):
        """Remove a subscriber."""
        self._subscribers = [cb for cb in self._subscribers if cb is not callback]

    def _notify(self, alert: Alert):
        """Notify all subscribers of a new alert."""
        for cb in self._subscribers:
            try:
                cb(alert)
            except Exception:
                logger.exception("Alert subscriber notification error")

    def reset_daily(self):
        """Clear buffer and cooldowns for new trading session."""
        self._buffer.clear()
        self._cooldowns.clear()
        logger.info("AlertService daily reset complete")

"""Track VN30, VNINDEX, and HNX real-time values from SSI Channel MI.

Stores latest index snapshot per index_id, computes breadth ratio,
and maintains intraday sparkline arrays for charting.
"""

from collections import deque
from datetime import datetime

from app.models.domain import IndexData, IntradayPoint
from app.models.ssi_messages import SSIIndexMessage

# Max intraday points (~6h of trading at 1 update/sec)
_INTRADAY_MAXLEN = 21600


class IndexTracker:
    """Real-time index tracking with breadth and intraday sparkline."""

    def __init__(self):
        self._indices: dict[str, IndexData] = {}
        self._intraday: dict[str, deque[IntradayPoint]] = {}

    def update(self, msg: SSIIndexMessage) -> IndexData:
        """Process a Channel MI message and return updated index data."""
        now = datetime.now()

        # Append to intraday sparkline
        if msg.index_id not in self._intraday:
            self._intraday[msg.index_id] = deque(maxlen=_INTRADAY_MAXLEN)
        if msg.index_value > 0:
            self._intraday[msg.index_id].append(
                IntradayPoint(timestamp=now, value=msg.index_value)
            )

        data = IndexData(
            index_id=msg.index_id,
            value=msg.index_value,
            prior_value=msg.prior_index_value,
            change=msg.change,
            ratio_change=msg.ratio_change,
            total_volume=msg.total_qtty,
            advances=msg.advances,
            declines=msg.declines,
            no_changes=msg.no_changes,
            intraday=list(self._intraday[msg.index_id]),
            last_updated=now,
        )
        self._indices[msg.index_id] = data
        return data

    def get(self, index_id: str) -> IndexData | None:
        """Get latest snapshot for an index. None if not yet received."""
        return self._indices.get(index_id)

    def get_vn30_value(self) -> float:
        """Shortcut for VN30 index value (used by DerivativesTracker)."""
        idx = self._indices.get("VN30")
        return idx.value if idx else 0.0

    def get_all(self) -> dict[str, IndexData]:
        """Return all tracked indices."""
        return dict(self._indices)

    def get_intraday(self, index_id: str) -> list[IntradayPoint]:
        """Return intraday sparkline points for an index."""
        points = self._intraday.get(index_id)
        return list(points) if points else []

    def reset(self):
        """Clear all index data. Called at 15:00 VN daily."""
        self._indices.clear()
        self._intraday.clear()

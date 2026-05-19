---
phase: 2
title: "Events pipeline + expand to all VN30"
status: pending
priority: P1
effort: "1.5w"
dependencies: [1]
---

# Phase 2: Events Pipeline + VN30 Daily Expansion

## Overview
Tất cả VN30 stocks có Daily chart. Events pipeline với 3 nguồn: vnstock corp actions + earnings, manual macro JSON. News (Vietstock RSS) defer Phase 3.

## Requirements

### Functional
- `events` hypertable schema final với `dedup_key`
- vnstock v4 corp actions + earnings cho 30 VN30 stocks
- Manual macro events JSON loader (FOMC, SBV, CPI, GDP)
- Per-source dedup strategy (no single url_hash)
- Backfill Daily candles cho 30 VN30 stocks (extend cron)
- API: `GET /api/events?symbol=&start=&end=&types=&min_importance=`
- Frontend: event markers on chart + filter checkboxes + click popover
- Marker aggregation: cùng ngày multiple events → 1 marker với badge "+N"

### Non-functional
- Same code quality + coverage standards as Phase 1
- Events table indexed cho fast range queries
- vnstock failures không block pipeline (fallback to manual seed)

## Architecture

```
Backend new components:
  app/services/events/
    __init__.py
    vnstock_source.py       (corp actions + earnings)
    macro_curator.py        (read backend/data/events-macro.json)
    events_pipeline.py      (orchestrator, dedup)
  app/routers/events_router.py
  backend/data/events-macro.json  (seed data 50-100 macro events)
  alembic/versions/005_create_events.py

Frontend new components:
  src/hooks/use-events.ts
  src/components/charts/events-overlay.tsx       (lightweight-charts setMarkers)
  src/components/charts/event-popover.tsx
  src/components/charts/event-filters.tsx
  src/utils/event-aggregator.ts                  (group by date)
```

## Related Code Files

### Modify
- `backend/app/main.py` — register events router
- `backend/app/scheduler.py` — add events refresh job (daily 6:00 — corp actions don't change intraday)
- `backend/scripts/backfill-daily-candles.py` — default `--symbols` VN30 list
- `frontend/src/pages/chart-page.tsx` — wire events hook + overlay

### Create
- `backend/alembic/versions/005_create_events.py`
- `backend/app/services/events/__init__.py`
- `backend/app/services/events/vnstock_source.py`
- `backend/app/services/events/macro_curator.py`
- `backend/app/services/events/events_pipeline.py`
- `backend/app/routers/events_router.py`
- `backend/data/events-macro.json`
- `backend/tests/test_events_pipeline.py`
- `backend/tests/test_events_router.py`
- `frontend/src/hooks/use-events.ts`
- `frontend/src/components/charts/events-overlay.tsx`
- `frontend/src/components/charts/event-popover.tsx`
- `frontend/src/components/charts/event-filters.tsx`
- `frontend/src/utils/event-aggregator.ts`
- `frontend/src/__tests__/use-events.test.ts`

## Implementation Steps

### Step 1: Migration `005_create_events.py`
```python
def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            ts           TIMESTAMPTZ NOT NULL,
            symbol       VARCHAR(10) NULL,             -- NULL for macro events
            event_type   VARCHAR(20) NOT NULL,         -- corp_action|earnings|news|macro
            title        TEXT NOT NULL,
            summary      TEXT NULL,
            url          TEXT NULL,
            source       VARCHAR(30) NOT NULL,         -- vnstock|vietstock|manual|...
            importance   SMALLINT NOT NULL DEFAULT 5,  -- 0-10
            dedup_key    TEXT NOT NULL UNIQUE,
            metadata     JSONB NULL,                   -- type-specific extras
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute(
        "SELECT create_hypertable('events', 'ts', "
        "chunk_time_interval => INTERVAL '6 months', if_not_exists => TRUE)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_events_symbol_ts "
        "ON events (symbol, ts DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_events_type_importance "
        "ON events (event_type, importance DESC, ts DESC)"
    )

def downgrade():
    op.execute("DROP TABLE IF EXISTS events")
```

### Step 2: Dedup key strategy
```python
# app/services/events/dedup.py
import hashlib

def make_dedup_key(event_type: str, **kwargs) -> str:
    """Generate stable dedup key per event type.

    corp_action / earnings: hash(symbol + type + date)
    macro: hash(title + date + source)
    news: hash(normalized_url) or hash(title + ts) fallback
    """
    if event_type in ("corp_action", "earnings"):
        raw = f"{kwargs['symbol']}|{event_type}|{kwargs['date'].isoformat()}"
    elif event_type == "macro":
        raw = f"macro|{kwargs['title']}|{kwargs['date'].isoformat()}|{kwargs['source']}"
    elif event_type == "news":
        url = kwargs.get("url")
        if url:
            from urllib.parse import urlparse
            p = urlparse(url)
            raw = f"news|{p.netloc}{p.path}"  # strip query params
        else:
            raw = f"news|{kwargs['title']}|{kwargs['ts'].isoformat()}"
    else:
        raise ValueError(f"Unknown event_type: {event_type}")
    return hashlib.sha256(raw.encode()).hexdigest()
```

### Step 3: `vnstock_source.py`
```python
"""Fetch corp actions + earnings từ vnstock v4."""
import asyncio
import logging
from datetime import date
from typing import Any

logger = logging.getLogger(__name__)


class VnstockEventSource:
    def __init__(self) -> None:
        from vnstock import Vnstock
        self._vn = Vnstock()

    async def fetch_corp_actions(self, symbol: str) -> list[dict[str, Any]]:
        """Returns parsed events. Empty list on failure."""
        try:
            stock = self._vn.stock(symbol=symbol, source="TCBS")
            df = await asyncio.to_thread(stock.company.events)
            return self._parse_events(df, symbol, "corp_action")
        except Exception as exc:
            logger.warning(f"vnstock corp actions failed for {symbol}: {exc}")
            return []

    async def fetch_earnings(self, symbol: str) -> list[dict[str, Any]]:
        try:
            stock = self._vn.stock(symbol=symbol, source="TCBS")
            df = await asyncio.to_thread(stock.finance.ratio, period="quarter")
            return self._parse_earnings(df, symbol)
        except Exception as exc:
            logger.warning(f"vnstock earnings failed for {symbol}: {exc}")
            return []

    def _parse_events(self, df, symbol: str, event_type: str) -> list[dict]:
        if df is None or df.empty:
            return []
        # Actual column names depend on Phase 0 spike findings — adjust here
        return [
            {
                "ts": row["date"],
                "symbol": symbol,
                "event_type": event_type,
                "title": row.get("title", ""),
                "summary": row.get("description", ""),
                "source": "vnstock-tcbs",
                "importance": 6,
            }
            for _, row in df.iterrows()
        ]
```

### Step 4: `macro_curator.py` + seed JSON
```python
# app/services/events/macro_curator.py
import json
from datetime import datetime
from pathlib import Path

DATA_FILE = Path(__file__).parent.parent.parent.parent / "data" / "events-macro.json"


def load_macro_events() -> list[dict]:
    if not DATA_FILE.exists():
        return []
    with DATA_FILE.open() as f:
        raw = json.load(f)
    return [
        {
            "ts": datetime.fromisoformat(item["date"]),
            "symbol": None,
            "event_type": "macro",
            "title": item["title"],
            "summary": item.get("summary", ""),
            "source": item.get("source", "manual"),
            "importance": item.get("importance", 7),
        }
        for item in raw
    ]
```

Seed `backend/data/events-macro.json`:
```json
[
  {"date": "2024-01-31T19:00:00+07:00", "title": "FOMC Jan 2024 — rates unchanged", "source": "fomc", "importance": 8, "summary": "..."},
  {"date": "2024-03-20T19:00:00+07:00", "title": "FOMC Mar 2024 — dot plot 3 cuts", "source": "fomc", "importance": 9},
  {"date": "2024-04-01T08:00:00+07:00", "title": "CPI VN March 2024: +3.97% YoY", "source": "gso", "importance": 7},
  {"date": "2024-07-01T08:00:00+07:00", "title": "SBV cuts policy rate 25bps", "source": "sbv", "importance": 9}
]
```
(User curates ~50-100 entries; this is initial template)

### Step 5: `events_pipeline.py`
```python
"""Orchestrator for events ingestion + dedup."""
import logging
from app.database.pool import db
from app.services.events.dedup import make_dedup_key
from app.services.events.vnstock_source import VnstockEventSource
from app.services.events.macro_curator import load_macro_events

logger = logging.getLogger(__name__)


class EventsPipeline:
    def __init__(self) -> None:
        self._vnstock = VnstockEventSource()

    async def run_full(self, symbols: list[str]) -> dict[str, int]:
        """Returns counts per source."""
        counts = {"corp_action": 0, "earnings": 0, "macro": 0}

        # vnstock corp + earnings per symbol
        for sym in symbols:
            corp = await self._vnstock.fetch_corp_actions(sym)
            earn = await self._vnstock.fetch_earnings(sym)
            counts["corp_action"] += await self._store(corp)
            counts["earnings"] += await self._store(earn)

        # Manual macro
        macro = load_macro_events()
        counts["macro"] = await self._store(macro)

        return counts

    async def _store(self, events: list[dict]) -> int:
        stored = 0
        async with db.pool.acquire() as conn:
            for e in events:
                key = make_dedup_key(
                    e["event_type"],
                    symbol=e.get("symbol", ""),
                    date=e["ts"].date() if hasattr(e["ts"], "date") else e["ts"],
                    title=e.get("title", ""),
                    source=e.get("source", ""),
                    url=e.get("url"),
                    ts=e["ts"],
                )
                result = await conn.execute(
                    """INSERT INTO events
                       (ts, symbol, event_type, title, summary, url, source, importance, dedup_key)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                       ON CONFLICT (dedup_key) DO NOTHING""",
                    e["ts"], e.get("symbol"), e["event_type"],
                    e["title"], e.get("summary"), e.get("url"),
                    e["source"], e.get("importance", 5), key,
                )
                if result.endswith("0"):
                    pass  # duplicate, skip
                else:
                    stored += 1
        return stored
```

### Step 6: Events router
```python
# app/routers/events_router.py
from datetime import date
from fastapi import APIRouter, Query, Request, HTTPException

from app.database.pool import db

router = APIRouter(prefix="/api/events", tags=["events"])

@router.get("")
async def get_events(
    request: Request,
    symbol: str | None = Query(None),
    start: date = Query(...),
    end: date = Query(...),
    types: str | None = Query(None, description="Comma-separated: corp_action,earnings,macro,news"),
    min_importance: int = Query(0, ge=0, le=10),
):
    if not getattr(request.app.state, "db_available", False):
        raise HTTPException(status_code=503, detail="Database unavailable")

    type_list = types.split(",") if types else None
    query = """
        SELECT id, ts, symbol, event_type, title, summary, url, source, importance
        FROM events
        WHERE ts >= $1 AND ts <= $2
          AND importance >= $3
    """
    params: list = [start, end, min_importance]
    if symbol:
        query += f" AND (symbol = ${len(params)+1} OR symbol IS NULL)"
        params.append(symbol.upper())
    if type_list:
        query += f" AND event_type = ANY(${len(params)+1})"
        params.append(type_list)
    query += " ORDER BY ts DESC LIMIT 1000"

    rows = await db.pool.fetch(query, *params)
    return [dict(r) for r in rows]
```

### Step 7: Expand Phase 1 backfill cho 30 VN30 stocks
- Update `scheduler.py` cron `_ingest_daily_eod`: symbols = VN30 list + indices
- Run backfill 1-time: `python backend/scripts/backfill-daily-candles.py --symbols VIC,VHM,VRE,VNM,...  --years 2`
- 30 calls × 200ms sleep = 6s total. Trivial.

### Step 8: Add events pipeline cron
```python
# scheduler.py — extend
async def _events_refresh():
    pipeline = EventsPipeline()
    counts = await pipeline.run_full(VN30_SYMBOLS)
    logger.info(f"Events refresh: {counts}")

scheduler.add_job(
    _events_refresh,
    CronTrigger(hour=6, minute=0, timezone="Asia/Saigon"),
    id="events_refresh_daily",
    replace_existing=True,
)
```

### Step 9: Frontend events overlay
```tsx
// src/utils/event-aggregator.ts
export function aggregateByDate(events: Event[]): Map<string, Event[]> {
  const map = new Map<string, Event[]>();
  for (const e of events) {
    const key = e.ts.split("T")[0];
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(e);
  }
  return map;
}

export function eventsToMarkers(events: Event[]) {
  const grouped = aggregateByDate(events);
  return [...grouped.entries()].map(([date, group]) => {
    const dominant = group.sort((a, b) => b.importance - a.importance)[0];
    return {
      time: Math.floor(new Date(date).getTime() / 1000),
      position: "aboveBar" as const,
      color: colorForType(dominant.event_type),
      shape: "circle" as const,
      text: group.length > 1 ? `${labelFor(dominant)} +${group.length - 1}` : labelFor(dominant),
    };
  });
}

function colorForType(type: string): string {
  return { corp_action: "#3b82f6", earnings: "#eab308", macro: "#ef4444", news: "#9ca3af" }[type] || "#888";
}
```

```tsx
// src/components/charts/events-overlay.tsx
import { useEffect } from "react";
import type { ISeriesApi } from "lightweight-charts";
import { eventsToMarkers } from "../../utils/event-aggregator";

export function useEventsOverlay(
  candleSeries: ISeriesApi<"Candlestick"> | null,
  events: Event[],
) {
  useEffect(() => {
    if (!candleSeries) return;
    candleSeries.setMarkers(eventsToMarkers(events));
  }, [candleSeries, events]);
}
```

### Step 10: Event filters component
```tsx
// src/components/charts/event-filters.tsx
const TYPES = [
  { id: "corp_action", label: "Cổ tức/Tách", color: "#3b82f6" },
  { id: "earnings", label: "Báo cáo TC", color: "#eab308" },
  { id: "macro", label: "Vĩ mô", color: "#ef4444" },
  { id: "news", label: "Tin tức", color: "#9ca3af", disabled: true },  // active in Phase 3
];

export function EventFilters({ value, onChange }) {
  // checkbox group
}
```

### Step 11: chart-page wiring
```tsx
const [enabledTypes, setEnabledTypes] = useState(["corp_action", "earnings", "macro"]);
const { events } = useEvents(symbol, startDate, endDate, enabledTypes);
useEventsOverlay(candleSeriesRef.current, events);
```

### Step 12: Docs sync
- Update `docs/api-reference.md` events endpoint
- Update `docs/system-architecture.md` events pipeline section

## Tests (TDD order)

1. **Unit (backend)**: `test_events_pipeline.py`
   - `make_dedup_key` produces same hash for same inputs (idempotent)
   - `make_dedup_key` different hashes for different event_types
   - vnstock source returns `[]` on exception
   - macro_curator loads valid JSON
2. **Integration (backend)**: `test_events_router.py`
   - GET với symbol filter
   - GET với types filter
   - GET với min_importance filter
   - Dedup: insert same event twice → 1 row
3. **Unit (frontend)**: `event-aggregator.test.ts`
   - `aggregateByDate` groups correctly
   - `eventsToMarkers` returns 1 marker per date với "+N" badge
4. **Manual E2E**: chọn VIC, see corp action markers blue + earnings yellow

## Success Criteria

- [ ] Migration applied, `events` hypertable + indexes exist
- [ ] vnstock spike successful (Phase 0) — corp actions backfill works
- [ ] Macro JSON seed file có ≥50 entries
- [ ] `GET /api/events?symbol=VIC&start=2024-01-01&end=2026-05-19` returns events
- [ ] All 30 VN30 stocks có Daily candles trong DB
- [ ] Chart marker rendering: corp/earnings/macro với 3 màu khác nhau
- [ ] Click marker → popover hiển thị
- [ ] Multiple events same date → "+N" badge
- [ ] Backend tests ≥8 new
- [ ] Frontend tests ≥3 new
- [ ] Docs updated

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| vnstock chỉ trả future events | Phase 0 spike confirms; fallback = manual JSON seed for backfill |
| vnstock API breaks v4→v4.x | Pin version, monitor, cache 24h results |
| Marker count >500 slow | Lazy load: only fetch events for visible date range |
| Multiple events same date overlap | Aggregator step 9 handles via "+N" badge |
| Macro JSON not maintained | Initial seed cover 2024-2026; user accepts monthly manual update or accepts staleness |

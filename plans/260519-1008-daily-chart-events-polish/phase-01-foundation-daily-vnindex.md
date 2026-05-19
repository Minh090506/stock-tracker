---
phase: 1
title: "Foundation + Daily chart cho VNINDEX (end-to-end)"
status: pending
priority: P1
effort: "1.5-2w"
dependencies: [0]
---

# Phase 1: Foundation + Daily Chart cho VNINDEX

## Overview
End-to-end Daily chart hoạt động cho 1 symbol (VNINDEX), lock kiến trúc trước khi expand. Tests-first để protect existing 1-minute chart behavior.

## Requirements

### Functional
- `candles_1d` hypertable lưu Daily OHLCV
- SSI DailyOhlc REST integration, idempotent upsert
- 2 năm backfill cho VNINDEX
- Cron job 17:30 VN weekdays append EOD candle
- API endpoint: `GET /api/history/index/{name}/daily-candles?start=&end=`
- Frontend: timeframe toggle (1m/1D) + time range selector (1M/3M/6M/1Y/2Y/All) trên chart-page
- Daily chart cho VNINDEX render <1s

### Non-functional
- TDD: tests pass cho existing 1m flow trước khi modify
- Backend coverage ≥80% cho new code
- No file >200 LOC (split if needed)

## Architecture

```
Backend new components:
  app/services/daily_ingestion_service.py
    └─ wraps ssi_fc_data.fc_md_client.daily_ohlc()
       (1 page/symbol, pageSize=1000 → no pagination loop for 2 years)
    └─ idempotent upsert via ON CONFLICT
  app/database/history_service.py (extend)
    └─ get_daily_candles(symbol, start, end)
  app/routers/history_router.py (extend)
    └─ GET /api/history/{symbol}/daily-candles
    └─ GET /api/history/index/{name}/daily-candles
  app/scheduler.py (add job)
    └─ CronTrigger hour=17 minute=30 day_of_week='mon-fri' → ingest_daily_for_all()
  backend/scripts/backfill-daily-candles.py
    └─ --symbols flag, default VNINDEX

Frontend new components:
  src/hooks/use-daily-candles.ts (REST only, no WS)
  src/components/charts/timeframe-toggle.tsx (1m / 1D buttons)
  src/components/charts/time-range-selector.tsx (1M/3M/6M/1Y/2Y/All)
  src/pages/chart-page.tsx (extend)
    └─ timeframe state
    └─ conditionally fetch daily vs 1m
```

## Related Code Files

### Modify (preserve behavior via TDD)
- `backend/app/database/history_service.py` — add `get_daily_candles()` mirroring `get_candles()` pattern
- `backend/app/routers/history_router.py` — add 2 daily endpoints (stock + index)
- `backend/app/main.py` — register scheduler job
- `frontend/src/pages/chart-page.tsx` — wire timeframe state; preserve 1m default
- `frontend/src/hooks/use-candle-data.ts` — refactor: accept `timeframe` param; skip WS when '1D'

### Create
- `backend/alembic/versions/004_create_candles_1d.py`
- `backend/app/services/daily_ingestion_service.py`
- `backend/scripts/backfill-daily-candles.py`
- `backend/tests/test_daily_ingestion_service.py`
- `backend/tests/test_history_router_daily.py`
- `frontend/src/hooks/use-daily-candles.ts`
- `frontend/src/components/charts/timeframe-toggle.tsx`
- `frontend/src/components/charts/time-range-selector.tsx`
- `frontend/src/__tests__/use-daily-candles.test.ts`

## Implementation Steps

### Step 1: Lock existing 1m behavior (TDD safety net)
1. Audit existing tests for `history_router`, `history_service`, `candlestick-chart`, `use-candle-data`
2. If gaps: add characterization tests trước modify code
3. Run full backend test suite — green baseline

### Step 2: Migration `004_create_candles_1d.py`
```python
"""Create candles_1d hypertable."""
from alembic import op

revision = "004"
down_revision = "003"

def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS candles_1d (
            symbol     VARCHAR(10) NOT NULL,
            date       DATE NOT NULL,
            open       NUMERIC(12, 2) NOT NULL,
            high       NUMERIC(12, 2) NOT NULL,
            low        NUMERIC(12, 2) NOT NULL,
            close      NUMERIC(12, 2) NOT NULL,
            volume     BIGINT NOT NULL DEFAULT 0,
            value      NUMERIC(20, 2) DEFAULT 0,
            PRIMARY KEY (symbol, date)
        )
    """)
    op.execute(
        "SELECT create_hypertable('candles_1d', 'date', "
        "chunk_time_interval => INTERVAL '1 year', if_not_exists => TRUE)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_candles_1d_symbol_date "
        "ON candles_1d (symbol, date DESC)"
    )

def downgrade():
    op.execute("DROP TABLE IF EXISTS candles_1d")
```
Run: `./backend/venv/bin/alembic upgrade head`

### Step 3: `daily_ingestion_service.py`
```python
"""Daily OHLCV ingestion from SSI FastConnect REST."""
import asyncio
import logging
from datetime import date
from types import SimpleNamespace

from ssi_fc_data.fc_md_client import MarketDataClient
from ssi_fc_data.model.model import daily_ohlc as DailyOhlcReq

from app.database.pool import db
from app.services.ssi_auth_service import SSIAuthService

logger = logging.getLogger(__name__)


class DailyIngestionService:
    def __init__(self, auth: SSIAuthService) -> None:
        self._auth = auth
        self._client = MarketDataClient(
            config=SimpleNamespace(
                consumerID=auth.consumer_id,
                consumerSecret=auth.consumer_secret,
                stream_url="",  # unused for REST
            )
        )

    async def fetch_and_store(
        self, symbol: str, start: date, end: date
    ) -> int:
        """Fetch daily OHLCV for symbol in date range, upsert into candles_1d.
        Returns count of rows upserted."""
        req = DailyOhlcReq()
        req.symbol = symbol
        req.fromDate = start.strftime("%d/%m/%Y")
        req.toDate = end.strftime("%d/%m/%Y")
        req.pageIndex = 1
        req.pageSize = 1000  # 2 years = ~500 days, fits in 1 page
        req.ascending = True

        config = SimpleNamespace(
            consumerID=self._auth.consumer_id,
            consumerSecret=self._auth.consumer_secret,
        )

        resp = await asyncio.wait_for(
            asyncio.to_thread(self._client.daily_ohlc, config, req),
            timeout=30.0,
        )
        rows = resp.get("data", [])
        if not rows:
            logger.warning(f"No daily candles returned for {symbol} {start}→{end}")
            return 0

        await self._upsert(symbol, rows)
        return len(rows)

    async def _upsert(self, symbol: str, rows: list[dict]) -> None:
        async with db.pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO candles_1d (symbol, date, open, high, low, close, volume, value)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (symbol, date) DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume,
                    value = EXCLUDED.value
                """,
                [self._parse_row(symbol, r) for r in rows],
            )

    @staticmethod
    def _parse_row(symbol: str, r: dict) -> tuple:
        # TradingDate format from SSI is DD/MM/YYYY
        from datetime import datetime
        d = datetime.strptime(r["TradingDate"], "%d/%m/%Y").date()
        return (
            symbol,
            d,
            float(r["Open"]),
            float(r["High"]),
            float(r["Low"]),
            float(r["Close"]),
            int(float(r["Volume"])),
            float(r.get("Value", 0)),
        )
```
**Test:**
```python
# tests/test_daily_ingestion_service.py
async def test_fetch_and_store_vnindex(mock_ssi):
    svc = DailyIngestionService(mock_auth)
    count = await svc.fetch_and_store("VNINDEX", date(2024, 1, 1), date(2026, 5, 19))
    assert count > 400  # ~500 trading days expected
    # Verify DB has rows
    rows = await db.pool.fetch("SELECT * FROM candles_1d WHERE symbol = 'VNINDEX'")
    assert len(rows) == count
```

### Step 4: Backfill script
```python
# backend/scripts/backfill-daily-candles.py
"""Backfill historical Daily OHLCV from SSI for VN30 + indices."""
import argparse
import asyncio
from datetime import date, timedelta

async def main(symbols: list[str], years: int):
    # ... init auth + service ...
    end = date.today()
    start = end - timedelta(days=years * 365)
    for sym in symbols:
        count = await svc.fetch_and_store(sym, start, end)
        print(f"{sym}: {count} candles stored")
        await asyncio.sleep(0.2)  # rate limit safety

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default="VNINDEX",
                        help="Comma-separated symbols (default: VNINDEX)")
    parser.add_argument("--years", type=int, default=2)
    args = parser.parse_args()
    asyncio.run(main(args.symbols.split(","), args.years))
```
Run: `./backend/venv/bin/python backend/scripts/backfill-daily-candles.py --symbols VNINDEX --years 2`

### Step 5: History service extension
```python
# history_service.py — add method
async def get_daily_candles(
    self, symbol: str, start: date, end: date
) -> list[dict]:
    rows = await self._pool.fetch(
        """SELECT symbol, date, open, high, low, close, volume, value
           FROM candles_1d
           WHERE symbol = $1 AND date >= $2 AND date <= $3
           ORDER BY date""",
        symbol, start, end,
    )
    return [dict(r) for r in rows]
```

### Step 6: Router endpoints
```python
# history_router.py — add
@router.get("/{symbol}/daily-candles")
async def get_daily_candles_stock(
    request: Request, symbol: str,
    start: date = Query(...), end: date = Query(...),
):
    return await _get_svc(request).get_daily_candles(symbol.upper(), start, end)

@router.get("/index/{index_name}/daily-candles")
async def get_daily_candles_index(
    request: Request, index_name: str,
    start: date = Query(...), end: date = Query(...),
):
    return await _get_svc(request).get_daily_candles(index_name.upper(), start, end)
```

### Step 7: Register cron job
```python
# app/scheduler.py — extend setup_jobs()
from apscheduler.triggers.cron import CronTrigger
from app.services.daily_ingestion_service import DailyIngestionService

async def _ingest_daily_eod():
    """Fetch today's EOD candle for all VN30 + indices."""
    # Run after ATC + buffer = 17:30 VN
    today = date.today()
    symbols = ["VNINDEX", "VN30"]  # extend in Phase 2
    for sym in symbols:
        try:
            await daily_service.fetch_and_store(sym, today, today)
        except Exception as exc:
            logger.error(f"Daily ingest failed for {sym}: {exc}")

scheduler.add_job(
    _ingest_daily_eod,
    CronTrigger(hour=17, minute=30, day_of_week="mon-fri", timezone="Asia/Saigon"),
    id="daily_candles_eod",
    replace_existing=True,
)
```

### Step 8: Frontend timeframe toggle
```tsx
// frontend/src/components/charts/timeframe-toggle.tsx
type Timeframe = "1m" | "1D";

export function TimeframeToggle({
  value, onChange,
}: { value: Timeframe; onChange: (t: Timeframe) => void }) {
  return (
    <div className="flex gap-1">
      {(["1m", "1D"] as Timeframe[]).map((tf) => (
        <button
          key={tf}
          onClick={() => onChange(tf)}
          className={`px-3 py-1.5 text-xs rounded-md ${
            value === tf
              ? "bg-gray-700 text-white"
              : "bg-gray-800/50 text-gray-400 hover:text-white"
          }`}
        >
          {tf}
        </button>
      ))}
    </div>
  );
}
```

### Step 9: Time range selector
```tsx
// frontend/src/components/charts/time-range-selector.tsx
const RANGES = [
  { label: "1M", days: 30 },
  { label: "3M", days: 90 },
  { label: "6M", days: 180 },
  { label: "1Y", days: 365 },
  { label: "2Y", days: 730 },
  { label: "All", days: null },
] as const;

export function TimeRangeSelector({
  value, onChange,
}: { value: string; onChange: (label: string) => void }) {
  // ... similar to TimeframeToggle
}
```

### Step 10: Daily candles hook
```ts
// frontend/src/hooks/use-daily-candles.ts
import { useState, useEffect } from "react";
import { apiFetch } from "../utils/api-client";

export function useDailyCandles(symbol: string, start: string, end: string, isIndex = false) {
  const [candles, setCandles] = useState<LWCandle[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!symbol) return;
    setLoading(true);
    const path = isIndex
      ? `/history/index/${symbol}/daily-candles?start=${start}&end=${end}`
      : `/history/${symbol}/daily-candles?start=${start}&end=${end}`;
    apiFetch<DailyCandleRow[]>(path)
      .then((rows) => {
        setCandles(rows.map((r) => ({
          time: Math.floor(new Date(r.date).getTime() / 1000),
          open: r.open, high: r.high, low: r.low, close: r.close,
        })));
        setError(null);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [symbol, start, end, isIndex]);

  return { candles, loading, error };
}
```

### Step 11: chart-page integration
```tsx
// chart-page.tsx — extend
const [timeframe, setTimeframe] = useState<"1m" | "1D">("1m");
const [rangeLabel, setRangeLabel] = useState("1Y");

const isDaily = timeframe === "1D";
const dailyData = useDailyCandles(symbol, startDate, endDate, /*isIndex=*/symbol === "VNINDEX");
const intradayData = useCandleData(symbol, "VN30");

const candles = isDaily ? dailyData.candles : intradayData.candles;
// ... render
```

### Step 12: Docs sync
- Update `docs/api-reference.md` với 2 endpoints mới
- Update `docs/system-architecture.md` thêm scheduler section
- Append `docs/development-roadmap.md`: "Phase 9: Daily charting + events + polish"

## Tests (TDD order)

1. **Unit (backend)**: `test_daily_ingestion_service.py`
   - `_parse_row` chuyển SSI response format đúng types
   - `fetch_and_store` mock SSI, verify upsert called với correct params
   - Idempotency: 2 calls cùng date không tạo duplicate
2. **Integration (backend)**: `test_history_router_daily.py`
   - `GET /api/history/index/VNINDEX/daily-candles?start=2024-01-01&end=2026-05-19` → 200 + array
   - Empty range → empty array (not 404)
   - Invalid date format → 422
3. **Unit (frontend)**: `use-daily-candles.test.ts`
   - Mock fetch, verify hook converts dates → unix seconds correctly
   - Loading/error states
4. **E2E manual**: Open `/chart`, toggle 1D, select VNINDEX, see 2 năm chart

## Success Criteria

- [ ] Migration applied, `candles_1d` exists, hypertable created
- [ ] Backfill script runs successfully cho VNINDEX, ≥400 rows inserted
- [ ] `GET /api/history/index/VNINDEX/daily-candles?start=2024-01-01&end=2026-05-19` returns ≥400 records
- [ ] Cron job registered, visible in scheduler logs
- [ ] Chart page Daily toggle works, render <1s
- [ ] Backend tests pass (≥5 new tests)
- [ ] Frontend smoke test passes (≥1 new test)
- [ ] No regression: existing 1m chart still works
- [ ] Docs updated

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| SSI rate limit hit during backfill | 200ms sleep between symbols (verified safe) |
| SSI returns unexpected field names | Phase 0 spike documented exact shape; parser robust to missing fields |
| Existing 1m chart breaks | TDD safety net step 1 |
| Cron job not firing | Manual trigger test before relying on schedule; APScheduler logs |
| `use-candle-data.ts` refactor breaks WS flow | Snapshot/integration test for intraday before refactor |

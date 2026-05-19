---
phase: 0
title: "Pre-flight: restore prod + dependencies + spikes"
status: pending
priority: P0
effort: "2-3d"
dependencies: []
---

# Phase 0: Pre-flight

## Overview
Blocking tasks trước khi Phase 1 start. Restore production health, install missing infra, run de-risking spikes.

## Requirements

### Functional
- Production backend health endpoint trả 200 (currently 502)
- `GEMINI_API_KEY` available trong env
- vnstock v4.0.3 installed + verified API shape
- APScheduler installed + scheduler module created
- vitest installed + 1 dummy test passes
- 7 untracked reports committed

### Non-functional
- Document findings inline trong này
- No code changes to feature files (chỉ infra setup)

## Architecture

```
Backend pre-flight:
  - VPS SSH → check container → restart
  - pip install: vnstock==4.0.3, apscheduler==3.10.4
  - app/scheduler.py (NEW skeleton, no jobs yet)
  - app/config.py: add gemini_api_key field

Frontend pre-flight:
  - npm install -D vitest @testing-library/react @testing-library/jest-dom happy-dom
  - vite.config.ts: add test section
  - src/test-setup.ts (NEW)
```

## Related Code Files

- **Modify**: `backend/requirements.txt`, `backend/app/config.py`, `backend/.env.example`, `frontend/package.json`, `frontend/vite.config.ts`
- **Create**: `backend/app/scheduler.py` (skeleton), `frontend/src/test-setup.ts`, `frontend/src/__tests__/smoke.test.ts`

## Implementation Steps

### Step 1: Restore production (P0 BLOCKER, ~30min)
1. SSH vào VPS: `ssh root@<hetzner-vps-ip>`
2. `cd /opt/stock-tracker` (or actual deploy dir)
3. `docker compose ps` — identify down container
4. `docker compose logs backend --tail=200` — root cause
5. Likely causes (check):
   - SSI auth failure: re-check `SSI_CONSUMER_ID/SECRET` in VPS `.env`
   - OOM: check `docker stats`, increase memory limit if needed
   - Code crash: roll back to last known-good commit (`5d9d307`)
6. `docker compose restart backend` (or `up -d --force-recreate backend`)
7. Verify: `curl https://stock.myvivatour.com/api/health` returns 200
8. Verify board loads data trong browser

### Step 2: Verify CORS prod (~5min)
1. Check VPS `.env` `CORS_ORIGINS` — confirm includes `https://stock.myvivatour.com`
2. If still `https://yourdomain.com` placeholder → update + restart backend
3. Test browser DevTools: no CORS errors on `/api/vn30-components`

### Step 3: Commit deferred reports (~5min)
```bash
git add plans/reports/Explore-260226-*.md \
        plans/reports/debugger-260225-*.md \
        plans/reports/code-reviewer-260225-*.md \
        plans/reports/docs-manager-260225-*.md \
        plans/reports/researcher-260225-*.md \
        plans/reports/tester-260225-*.md
git commit -m "docs(plans): commit deferred Feb 2026 reports

Reference material for plan V2 execution. Includes price-board debug,
Cloudflare SSL review, frontend exploration, contract naming research,
docs notes, and test suite snapshot."
```

### Step 4: Install backend dependencies (~15min)
1. Add to `backend/requirements.txt`:
   ```
   apscheduler==3.10.4
   vnstock==4.0.3
   ```
2. `./backend/venv/bin/pip install -r backend/requirements.txt`
3. Create skeleton `backend/app/scheduler.py`:
   ```python
   """Application scheduler (APScheduler AsyncIOScheduler)."""
   from apscheduler.schedulers.asyncio import AsyncIOScheduler

   scheduler = AsyncIOScheduler(timezone="Asia/Saigon")


   def setup_jobs() -> None:
       """Register cron jobs. Called during FastAPI lifespan startup."""
       # Jobs added in later phases
       scheduler.start()


   def shutdown_scheduler() -> None:
       """Stop scheduler. Called during FastAPI lifespan shutdown."""
       if scheduler.running:
           scheduler.shutdown(wait=False)
   ```
4. Wire into `backend/app/main.py` lifespan:
   ```python
   from app.scheduler import setup_jobs, shutdown_scheduler

   async def lifespan(app):
       setup_jobs()
       yield
       shutdown_scheduler()
   ```
5. Add to `backend/app/config.py`:
   ```python
   gemini_api_key: str = ""  # Set in .env for Phase 3
   ```
6. Add to `backend/.env.example`:
   ```
   GEMINI_API_KEY=
   ```
7. Verify: `./backend/venv/bin/uvicorn app.main:app` starts cleanly, logs "Scheduler started"

### Step 5: vnstock v4 events spike (~30min)
1. `./backend/venv/bin/python -c "from vnstock import Vnstock; v = Vnstock().stock(symbol='FPT', source='TCBS'); print(dir(v.company))"`
2. Test `company.events()` with FPT — capture actual response shape
3. **Critical question**: does response include past events or only future?
4. Document in this file (append to "Spike Results" section below):
   - Returned columns
   - Date range coverage (oldest event year?)
   - Pagination support?
5. **Decision tree:**
   - Past events supported (>1 year back) → Phase 2 uses vnstock for backfill
   - Only future events → Phase 2 uses manual JSON seed for 2-year backfill + vnstock for going-forward only

### Step 6: Install frontend dependencies (~30min)
1. `cd frontend && npm install -D vitest @testing-library/react @testing-library/jest-dom happy-dom @vitest/coverage-v8`
2. Update `frontend/vite.config.ts`:
   ```ts
   /// <reference types="vitest" />
   import { defineConfig } from "vite";
   // ... existing imports

   export default defineConfig({
     // ... existing config
     test: {
       environment: "happy-dom",
       globals: true,
       setupFiles: ["./src/test-setup.ts"],
     },
   });
   ```
3. Create `frontend/src/test-setup.ts`:
   ```ts
   import "@testing-library/jest-dom/vitest";
   ```
4. Create smoke test `frontend/src/__tests__/smoke.test.ts`:
   ```ts
   import { test, expect } from "vitest";

   test("smoke", () => {
     expect(1 + 1).toBe(2);
   });
   ```
5. Add to `frontend/package.json` scripts: `"test": "vitest run"`
6. Verify: `npm test` passes

### Step 7: SSI DailyOhlc smoke test (~15min)
Spike: call SSI DailyOhlc once với VNINDEX để verify response format trước Phase 1.
```python
from datetime import date
from types import SimpleNamespace
from ssi_fc_data.fc_md_client import MarketDataClient
from ssi_fc_data.model.model import daily_ohlc as DailyOhlcReq

from app.config import settings
from app.services.ssi_auth_service import SSIAuthService

# Use existing auth pattern
auth = SSIAuthService(...)
client = MarketDataClient(config=SimpleNamespace(consumerID=..., consumerSecret=...))
req = DailyOhlcReq()
req.symbol = "VNINDEX"
req.fromDate = "01/01/2024"
req.toDate = "19/05/2026"
req.pageIndex = 1
req.pageSize = 1000
req.ascending = True

resp = client.daily_ohlc(config, req)
print(f"records: {len(resp.get('data', []))}")
print(f"first: {resp['data'][0]}")
print(f"last: {resp['data'][-1]}")
```
Document actual record count + field names in spike findings.

### Step 8: Update memory note (~5min)
Update `/Users/minh/.claude/projects/-Users-minh-Projects-stock-tracker/memory/MEMORY.md`:
- Change: "SSI-only data source (no vnstock, no TCBS)"
- To: "SSI FastConnect for OHLCV + realtime; vnstock v4 for corp events; Vietstock RSS for news (CafeF blocked); Gemini Flash for sentiment scoring"

## Tests
N/A — infrastructure only. Verification via smoke runs of Step 4-7.

## Success Criteria

- [ ] Production `/api/health` returns 200, board loads data
- [ ] `GEMINI_API_KEY` set in local `.env` (value can be placeholder until Phase 3)
- [ ] vnstock 4.0.3 installed, events() call returns parseable result, past-event support documented
- [ ] APScheduler installed, `app/scheduler.py` skeleton wired in lifespan, app starts clean
- [ ] vitest installed, smoke test passes
- [ ] SSI DailyOhlc smoke call succeeds for VNINDEX, response format documented
- [ ] 7 deferred reports committed
- [ ] Memory note updated

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| VPS access not available | User provides SSH credentials OR commits to fix manually before Phase 1 |
| GEMINI_API_KEY not obtainable | Phase 3 falls back to rule-based importance scoring |
| vnstock v4 only returns future events | Plan v2 already has fallback: manual seed JSON for backfill |
| SSI DailyOhlc unexpected response shape | Document actual format; adjust Phase 1 parser accordingly |

## Spike Results (append after execution)

### vnstock events() actual response
```
(populate after Step 5 spike)
```

### SSI DailyOhlc actual response
```
(populate after Step 7 spike)
```

### Production restore root cause
```
(populate after Step 1)
```

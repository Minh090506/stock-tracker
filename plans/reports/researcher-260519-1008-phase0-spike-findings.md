# Phase 0 Spike Findings — Pre-Plan-V2 Investigation

**Date:** 2026-05-19
**Scope:** Verify assumptions trong plan v1, resolve open questions, de-risk Phase 1
**Verdict:** **Plan v2 cần revision lớn**. Phát hiện 1 P0 emergency, 2 data sources không khả thi, 1 finding tích cực (SSI pagination đơn giản hơn nghĩ).

---

## 🚨 P0 EMERGENCY — Production backend DOWN

```bash
$ curl https://stock.myvivatour.com/       → HTTP 200 (nginx up)
$ curl https://stock.myvivatour.com/api/health → HTTP 502 (backend DOWN)
```

**Diagnosis:** Nginx reverse proxy hoạt động, nhưng backend container không respond. Có thể:
- Container crashed (SSI auth fail, OOM)
- Backend service stopped
- Internal network broken
- VPS deploy rollback chưa hoàn tất

**Action required (PRE-PLAN):** SSH vào Hetzner VPS, check `docker compose ps` + logs:
```bash
ssh root@<vps-ip>
cd /opt/stock-tracker  # or deploy dir
docker compose ps
docker compose logs backend --tail=200
docker compose restart backend  # if needed
```

**Block plan execution** cho đến khi prod backend lên lại. Hoặc accept rằng plan này build trên dev/staging trước, deploy prod sau khi Phase 1 stable.

---

## ✅ SSI DailyOhlc — verified, simpler than expected

Từ docs SSI FastConnect chính thức (`guide.ssi.com.vn/.../api-specs`):

| Param | Format | Note |
|-------|--------|------|
| `symbol` | string | **Optional** — empty returns all securities |
| `fromDate` | DD/MM/YYYY | Required |
| `toDate` | DD/MM/YYYY | Required |
| `pageIndex` | 1-10 | Default 1 |
| `pageSize` | 10/20/50/100/**1000** | Default 10 |
| `ascending` | bool | Optional |

**Max records per query: 10 × 1000 = 10,000.**
**2 năm = ~500 trading days per symbol = 1 PAGE với pageSize=1000.**

→ Plan v1 estimated 150 calls (30 symbols × 5 pages). **Realistic: 30 calls (1 page/symbol).** Backfill nhanh hơn nhiều.

**Response fields:** `Symbol, Market, TradingDate, Time, Open, High, Low, Close, Volume, Value`

**Rate limit:** không documented. Cần test 30 calls liên tiếp xem có throttle không. Suggest 200ms sleep between calls để safe.

**Max history depth:** không documented. Test với fromDate=2020-01-01 xem trả được không.

---

## ❌ CafeF RSS — KHÔNG khả thi, drop khỏi plan

Tested 4 URL variants:
```
https://cafef.vn/thi-truong-chung-khoan.rss       → HTTP 000 (timeout)
https://cafef.vn/rss/thi-truong-chung-khoan.rss   → timeout
https://cafef.vn/rss/thi-truong-chung-khoan.chn   → timeout
https://cafef.vn/rss/home.rss                     → timeout
```

Test cả với browser User-Agent → vẫn 000. **CafeF block development IPs hoặc đã remove RSS feeds**. Không scrape được.

**Action:** Drop CafeF khỏi Phase 3. News chỉ Vietstock + (optional) FireAnt API.

---

## ✅ Vietstock RSS — works perfectly

URL: `https://vietstock.vn/830/chung-khoan/co-phieu.rss` → HTTP 200, 17KB XML.

Sample item structure (clean, parseable):
```xml
<item>
  <guid isPermaLink="true">http://vietstock.vn/2026/05/...htm</guid>
  <link>http://vietstock.vn/2026/05/...htm</link>
  <title>Ngày 19/05/2026: 10 cổ phiếu nóng dưới góc nhìn PTKT</title>
  <description>Các cổ phiếu... gồm: BID, HDB, MSN, MBB, NLG, OCB, TPB, TCB, VPB, VNM.</description>
  <pubDate>Tue, 19 May 2026 10:00:00 +0700</pubDate>
</item>
```

**Symbol extraction:** Description chứa danh sách ticker (ALL CAPS, 3-4 chars). Regex `\b[A-Z]{3,4}\b` với whitelist VN30 → khả thi.

**Multiple feed URLs possible** cho coverage: stock news (830), index analysis, sector reports. Cần map ra Phase 3.

**Action:** Vietstock = primary news source. Plan v2 dùng `vietstock-rss` cụ thể, drop "cafef" mọi nơi.

---

## ⚠️ vnstock v4 — risk: historical events có thể không support

- **Latest version**: v4.0.3 (released 16/05/2026 — chỉ 3 ngày trước)
- **API**: `Reference().company.events(symbol='FPT')`
- **Description** trong docs: **"Upcoming corporate events"** — wording suggest CHỈ future events
- vnstocks.com/docs link migration v3→v4 → 404. Documentation gaps.

**Risk:** Nếu vnstock chỉ trả future events, backfill 2 năm corp actions/earnings **không khả thi** từ vnstock alone.

**Mitigations:**
1. **Test bằng install + call**: `pip install vnstock==4.0.3 && python -c "from vnstock import Reference; print(Reference().company.events('FPT'))"` — verify shape thực tế
2. **Fallback sources** nếu vnstock chỉ future:
   - HOSE/HNX corporate disclosure pages (scrape)
   - SSI iBoard company info API (auth required)
   - VSD (Vietnam Securities Depository) website
3. **Scope reduction**: chỉ ingest FUTURE events từ vnstock; cho backfill 2 năm corp/earnings, dùng manual curated JSON (initial seed 30 stocks × ~10 events = 300 entries)

**Action Phase 0:** Spike: install vnstock 4.0.3, test events() với 1 symbol, document actual response shape + date range.

---

## 📋 Untracked reports triage (7 files)

| File | Status | Action |
|------|--------|--------|
| `debugger-260225-1343-price-board-no-data.md` | Identified 5 issues; #1 CORS critical | **Reference** — commit hoặc keep untracked làm reference. Plan v2 phải address all 5 issues. |
| `code-reviewer-260225-1008-phase2-domain-cloudflare-ssl.md` | Cloudflare config review | Issues: (1) `/metrics` public — fix in Phase 5 hardening; (2) Missing IPv6 ranges — low priority |
| `Explore-260226-1030-price-board-components.md` | Frontend component map | **Reference** — useful for Phase 1 chart-page refactor |
| `Explore-260226-0903-derivatives-websocket-candle-pipeline.md` | WS pipeline notes | Reference for Phase 1 if touch WS code |
| `researcher-260225-1223-vn30f-contract-naming-convention.md` | KRX naming research | Already addressed in commit `e4cb682`. Archive. |
| `tester-260225-1319-full-test-suite-results.md` | Test snapshot | Stale (3 months old). Re-run in Phase 1 to get current baseline. |
| `docs-manager-260225-1445-documentation-update.md` | Docs review notes | Reference for Phase 5 docs sync |

**Recommend:** `git add` tất cả 7 files vào 1 commit "docs(plans): commit deferred Feb 2026 reports". Giữ history.

---

## 🔧 Infrastructure decisions

### Scheduler approach (was open)
**Recommend: APScheduler in-process** với AsyncIOScheduler, registered in FastAPI lifespan.

Lý do:
- Existing app đã async. APScheduler.AsyncIOScheduler native fit.
- Single process, single dependency (`apscheduler` package, ~50KB).
- Persistent jobstore không cần (jobs are idempotent — re-run safe).
- Docker cron sidecar phức tạp hơn (cần exec vào backend container hoặc tách network).

```python
# backend/app/scheduler.py (NEW)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = AsyncIOScheduler(timezone="Asia/Saigon")

def setup_jobs():
    scheduler.add_job(
        ingest_daily_candles,
        CronTrigger(hour=17, minute=30, day_of_week='mon-fri'),
        id='daily_candles_eod',
        replace_existing=True,
    )
    scheduler.add_job(
        events_pipeline_run,
        CronTrigger(hour='*/6'),
        id='events_pipeline_6h',
        replace_existing=True,
    )
    scheduler.start()

# main.py lifespan startup
async def lifespan(app):
    setup_jobs()
    yield
    scheduler.shutdown()
```

### Frontend test framework
**Recommend: vitest + @testing-library/react + happy-dom** (~3 deps, native Vite integration).

```bash
cd frontend
npm install -D vitest @testing-library/react @testing-library/jest-dom happy-dom @vitest/coverage-v8
```

Add `vite.config.ts`:
```ts
test: {
  environment: 'happy-dom',
  globals: true,
  setupFiles: ['./src/test-setup.ts'],
},
```

Setup time: ~0.5 ngày. Add to Phase 1 prep tasks.

### Gemini scoring
**Recommend: gemini-2.5-flash** (cheapest, fastest).

- Cost: ~$0.075/1M input tokens. Avg news article = 500 tokens. Score prompt = 200 tokens. Total ~700 tokens/article.
- 100 articles/day × 365 = 36,500/year × 700 tokens = 25M tokens ≈ **$1.9/year**. Cheap.
- Batch via Gemini Batch API (50% discount): cost halved.
- Hard limit 1000 calls/month = trivial.

**Risk:** Need `GEMINI_API_KEY` env var. **User must provide.**

---

## 📊 Decisions summary

| Item | Decision | Confidence |
|------|----------|------------|
| Migrations | Alembic Python files (not SQL) | ✓ verified |
| Schema types | `VARCHAR(10)`, `NUMERIC(12,2)` match existing | ✓ verified |
| CORS | Local fix in `.env` exists; production backend DOWN (P0) | ✓ verified |
| Scheduler | APScheduler in-process | recommended |
| Frontend tests | vitest + RTL + happy-dom | recommended |
| SSI DailyOhlc | Pagination simple (1 page/symbol for 2 years) | ✓ verified |
| vnstock historical events | **RISK — may not support past events** | ⚠️ needs in-code test |
| News source — CafeF | **DROP entirely** | ✓ verified blocked |
| News source — Vietstock | Primary RSS source | ✓ verified working |
| Gemini model | gemini-2.5-flash | recommended |
| Tailwind dark mode | v4 CSS-first (no config file) | ✓ verified |

---

## 🎯 Plan V2 — Revisions needed

### Phase 0 (PRE-PLAN, blocking)
- [ ] **P0**: SSH VPS, restart backend, restore prod health
- [ ] **P0**: User provide `GEMINI_API_KEY`
- [ ] In-code spike: vnstock 4.0.3 events() shape test
- [ ] Commit 7 untracked reports
- [ ] Update memory note: "SSI for OHLCV. vnstock for events. Vietstock RSS for news. CafeF blocked."

### Phase 1 (revised, 1.5-2 tuần)
**Pre-flight:**
- [ ] Verify prod backend up (curl health)
- [ ] Install vitest in frontend (0.5d)
- [ ] Install APScheduler in backend (1h)

**Implementation:**
- [ ] Alembic migration `004_create_candles_1d.py` (VARCHAR(10), NUMERIC(12,2), BIGINT volume)
- [ ] `backend/app/scheduler.py` — AsyncIOScheduler setup in lifespan
- [ ] `backend/app/services/daily_ingestion_service.py` — SSI DailyOhlc wrapper
  - 1 call/symbol (pageSize=1000), no pagination loop needed
  - 200ms sleep between symbols
  - Idempotent upsert `ON CONFLICT (symbol, date) DO UPDATE`
- [ ] `backend/scripts/backfill-daily-candles.py --symbols VNINDEX[,VIC,...]` (one script, --symbols flag)
- [ ] Extend `history_service.get_daily_candles(symbol, start, end)`
- [ ] Extend `history_router` daily endpoints
- [ ] Register cron job 17:30 weekdays
- [ ] Frontend: refactor `use-candle-data.ts` → accept `timeframe` param, skip WS when '1D'
- [ ] Frontend: `timeframe-toggle.tsx` + `time-range-selector.tsx` components
- [ ] Frontend: `chart-page.tsx` wire toggle + range
- [ ] Tests: backend unit (pytest), backend integration, frontend hook (vitest)

### Phase 2 (revised, 1.5 tuần)
**Pre-flight:**
- [ ] `pip install vnstock==4.0.3` + add to requirements.txt
- [ ] In-code spike confirm events() returns past data; if NOT → use manual JSON seed

**Implementation changes vs v1:**
- Events table: column `dedup_key TEXT UNIQUE` (not `url_hash`)
- Per-source dedup strategy:
  - Corp/earnings: `hash(symbol + event_type + date)`
  - Macro: `hash(title + date + source)`
  - News (phase 3): `hash(normalized_url) || hash(title + ts)` fallback
- Marker aggregation rule: same-date multiple events → single marker với badge "+N"
- Lazy load events: chỉ fetch visible range, không 2 năm 1 lần

### Phase 3 (revised, 1.5 tuần)
**Changes vs v1:**
- DROP CafeF entirely. Vietstock-only RSS scraper (`vietstock-rss-scraper.py`).
- ADD FireAnt API as optional fallback (test first).
- Gemini model = `gemini-2.5-flash` (not generic "Gemini")
- Cost ceiling: $5/month hard limit via API monitoring
- Symbol extraction from description: regex `\b[A-Z]{3,4}\b` + filter against VN30 whitelist
- Default min_importance = 7/10; user toggle để show all

### Phase 4 & 5 (revised)
- Phase 4: drawing tools = lightweight-charts v4 Primitives API (verified installed)
- Phase 5: dark mode via Tailwind v4 `@variant dark` in `index.css` (CSS-first, no config file)
- Phase 5: expand scope to **all 8 pages** mobile responsive (not 4)
- Phase 5: Tailwind dark mode conversion estimate +0.5w

### Realistic total: **8 tuần** (was 5.5w v1, was 7.5-9w in review)

---

## 🔓 Resolved open questions

| Question (from brainstorm) | Answer |
|---------------------------|--------|
| Production domain | `stock.myvivatour.com` ✓ — but backend currently DOWN |
| Gemini API key | **Not in env. User must provide before Phase 3** |
| Macro events curation | **Open** — recommend monthly manual update; user accept? |
| Memory note "SSI-only" update | Recommended new wording: "SSI for OHLCV/realtime. vnstock + Vietstock RSS for events. CafeF blocked." |
| Phase 3 risk gate fail → drop news | Auto-recommended: if Gemini cost > $10/mo OR Vietstock blocked → drop news, ship Phase 4 sớm |

---

## ❓ Remaining unresolved (need user)

1. **VPS access**: ai có SSH key vào Hetzner để restart backend? Plan blocked until prod healthy.
2. **Gemini API key**: tạo mới hoặc dùng existing? Where to store (`.env`, Doppler, secrets manager)?
3. **Manual macro curation**: bạn (user) update JSON file monthly? Hoặc tự động fetch từ source nào?
4. **vnstock event support**: chấp nhận manual seed JSON cho backfill nếu vnstock chỉ trả future?
5. **Phase 3 drop policy**: nếu RSS hoặc Gemini fail, chấp nhận skip news entirely OR delay phase?

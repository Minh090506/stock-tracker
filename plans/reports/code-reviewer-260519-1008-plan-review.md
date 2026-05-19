# Plan Review: Daily Chart + Events Timeline + Polish

**Reviewed plan:** `/Users/minh/.claude/plans/dreamy-wibbling-fern.md`
**Date:** 2026-05-19
**Verdict:** **NEEDS REVISION before execution** — 5 critical wrong assumptions, 8 high-priority gaps, time estimate underestimated ~40%.

---

## 1. CRITICAL — Wrong Assumptions (must fix before phase 1)

### C1. Alembic migration pattern — plan dùng sai
**Plan said:** "Migration files: `candles_1d.sql`, `events.sql`"
**Reality:** `backend/alembic/versions/` đã có `001_create_hypertables.py`, `003_order_velocity_aggregate.py`. Migrations là Python files với `revision`/`down_revision`, NOT raw SQL.
**Impact:** Migration approach hoàn toàn sai.
**Fix:** Phase 1 migration = `backend/alembic/versions/004_create_candles_1d.py`. Phase 2 = `005_create_events.py`. Follow existing pattern.

### C2. Schema types inconsistent với existing
**Plan said:** `(symbol TEXT, date DATE, open NUMERIC, ..., volume BIGINT)`
**Reality (existing):** `symbol VARCHAR(10)`, `price NUMERIC(12,2)`, `volume INTEGER`.
**Impact:** New table inconsistent với codebase; queries với JOIN sẽ implicit-cast.
**Fix:** Match existing types: `symbol VARCHAR(10) NOT NULL`, `open NUMERIC(12,2)`, `volume BIGINT` (Daily volume có thể vượt INTEGER max).

### C3. CORS prod có thể ĐÃ FIXED — verify trước khi waste time
**Plan said:** "Fix CORS prod bug (BLOCKING). Add `https://stock.myvivatour.com` to `backend/.env`"
**Reality:** Root `/Users/minh/Projects/stock-tracker/.env` (untracked) ĐÃ có `CORS_ORIGINS=http://localhost,https://stock.myvivatour.com`. Local `backend/.env` chỉ có localhost — nhưng deployment thực có thể dùng root `.env`.
**Impact:** Có thể đã fix rồi, plan đang outdated. Hoặc chưa deploy lên VPS.
**Fix:** Step 1 thay vì "fix CORS" = "VERIFY prod CORS status: curl https://stock.myvivatour.com/api/vn30-components từ browser console. Nếu OK → skip. Nếu fail → SSH VPS check `.env` đang load file nào, update đúng nguồn."

### C4. No backend scheduler infrastructure
**Plan said:** "Cron job daily 17:30 VN. Use FastAPI BackgroundTasks hoặc APScheduler"
**Reality:** Grep `APScheduler|BackgroundTasks` trong `backend/app/` → **không match**. Không có scheduler nào setup. `BackgroundTasks` chỉ chạy 1 lần sau request, không phải scheduled.
**Impact:** Plan assume infra tồn tại, nhưng cần build từ đầu. Phase 1 estimate sai 1-2 ngày.
**Fix:** Phase 1 thêm task: install APScheduler + AsyncIOScheduler + register vào lifespan. HOẶC dùng external Docker cron sidecar (đơn giản hơn). Decide trước khi start.

### C5. No frontend test framework
**Plan said:** "Write frontend test: `<ChartPage>` with `timeframe='1D'` calls daily endpoint" + "Tests pass: ... frontend hook (≥1)"
**Reality:** `frontend/package.json` không có vitest/jest/@testing-library. Memory note Feb 2026 còn ghi "Phase 2: Consider Jest/Vitest for React components" — chưa làm.
**Impact:** Frontend TDD tests **không chạy được**. Tất cả frontend acceptance criteria liên quan tests fail.
**Fix:** Phase 1 prep step: install vitest + @testing-library/react + happy-dom. ~0.5 ngày. HOẶC drop frontend TDD, rely on manual smoke test + type checking.

---

## 2. HIGH PRIORITY — Plan Gaps (address in revision)

### H1. SSI DailyOhlc — chưa verify request shape + pagination
Plan assumes `daily_ohlc()` "just works". Chưa verify:
- Tham số input (Symbol, FromDate, ToDate, PageIndex, PageSize)? Format date?
- Pagination: SSI thường return 100 records/page. 2 năm = 500 trading days = 5 pages/symbol. 30 symbols × 5 pages = 150 calls. Plan estimate "30 calls" SAI.
- Rate limit: unknown, cần backoff.
- Token refresh: daily run sau 24h, access token expire — verify auth_service auto-refresh.

**Fix:** Phase 1 thêm task spike (~2h): test SSI DailyOhlc tay với 1 symbol, document request/response shape, build pagination loop.

### H2. Tailwind v4 dark mode setup khác v3
**Plan said:** "Update `tailwind.config` to support `dark:` classes properly"
**Reality:** Project dùng Tailwind v4 (per README) — KHÔNG có `tailwind.config.js` file. v4 dùng CSS-first config via `@theme` directive trong `index.css`. Dark mode setup khác hoàn toàn v3.
**Fix:** Phase 5 task đổi thành: "Add `@variant dark` vào `index.css` + `darkMode: 'class'` strategy. Convert hardcoded `bg-gray-*` → `bg-gray-100 dark:bg-gray-900` pattern across ~50+ files."
**Impact estimate:** Phase 5 từ 1 tuần → 1.5-2 tuần (dark mode conversion là grep+replace lớn).

### H3. `use-candle-data.ts` đã wire WebSocket — không phải reuse trivial
Existing hook dùng REST historical + **WebSocket realtime updates** cho 1m candles. Daily candles không có WS (EOD only). Plan nói "reuse existing hook" thiếu detail.
**Fix:** Phase 1 refactor: tách `use-candle-data.ts` thành `use-intraday-candles.ts` (1m + WS) + `use-daily-candles.ts` (REST only). HOẶC parameterize hook với `timeframe` + skip WS subscription khi `timeframe='1D'`. Pick approach trong design step.

### H4. lightweight-charts setMarkers() — chiến lược marker chưa rõ
Markers tied to candle timestamps. Plan không address:
- Event vào weekend/holiday → marker attach vào candle nào? (next trading day)
- Multiple events cùng ngày → 1 marker "+N" hay nhiều markers chồng? (lightweight-charts không hỗ trợ multiple markers cùng time → cần aggregate)
- Marker giới hạn: ~500 markers/series là hợp lý. 30 stocks × 2 năm × multiple events/day → cần lazy-load chỉ visible range.
**Fix:** Phase 2 design step trước implement: marker aggregation rule + lazy load strategy.

### H5. Events dedup — hash strategy đơn nhất không hoạt động
Plan nói `url_hash = sha256(source + url)`. Nhưng:
- **Corp actions** không có URL (structured data từ vnstock). Cần `hash(symbol + event_type + ex_date)`.
- **News** có URL nhưng URL có thể đổi (redirect, tracking params). Cần `hash(normalize_url) + title_fingerprint`.
- **Macro** từ curated JSON cũng không URL. Cần `hash(title + ts + source)`.
**Fix:** Phase 2 events table thêm column `dedup_key TEXT UNIQUE` (không phải `url_hash`); pipeline mỗi source generate dedup_key riêng.

### H6. vnstock dependency chưa add
`requirements.txt` không có `vnstock`. Plan assume sẵn có.
**Fix:** Phase 2 prep step: `./venv/bin/pip install vnstock` + add vào requirements.txt + spike test fetch corp actions cho 1 symbol.
**Risk:** vnstock v3+ có breaking changes vs v2; API surface khác (`Vnstock().stock('VIC').company.events()` v3 vs `corporate_actions('VIC')` v2). Verify version compatibility.

### H7. Gemini importance scoring — design chưa đủ
Plan nói "Gemini API batch, cache by hash, hard limit 1000 calls/tháng". Thiếu:
- Model nào? `gemini-2.0-flash` (~$0.075/1M input tokens) vs `gemini-2.5-pro` ($1.25/1M)? Plan default Flash.
- Prompt template: chấm 0-10 dựa trên gì? (impact on stock price? company materiality?) Cần prompt eng + golden set.
- Batch size: 10 articles/call? 50? Trade-off latency vs cost.
- Fallback rule-based scoring khi Gemini fail: rule là gì? (length + keywords?) — undefined.
**Fix:** Phase 3 design step viết prompt + golden test set 20 articles + define fallback rules trước implement.

### H8. Docs sync thiếu trong mọi phase
Project rule (CLAUDE.md): "Documentation Triggers: project-manager agent MUST update docs khi major features implemented". Plan không có task update `docs/api-reference.md`, `docs/system-architecture.md`, `docs/development-roadmap.md`.
**Fix:** Mỗi phase end thêm task: docs sync (delegate docs-manager agent). Append section to roadmap "Phase 9: Daily + Events + Polish".

---

## 3. MEDIUM PRIORITY — Concerns

### M1. Time estimate underestimated ~40%

| Phase | Plan estimate | Realistic | Lý do |
|-------|---------------|-----------|-------|
| 1 | 1.5w | 1.5-2w | Scheduler infra + SSI spike + frontend test setup added |
| 2 | 1w | 1.5w | vnstock spike + dedup strategy + marker aggregation design |
| 3 | 1w | 1.5-2w | RSS verification + Gemini prompt eng + golden set |
| 4 | 1w | 1.5w | Custom drawing tools với lightweight-charts Primitives (complex) |
| 5 | 1w | 1.5-2w | Dark mode conversion (~50 files) + responsive sweep + watchlist sync |
| **Total** | **5.5w** | **7.5-9w** | Add testing infra + docs sync |

### M2. Phase 2 events router `min_importance` filter chưa coherent
Corp actions + earnings + macro chưa có AI scoring (Phase 3 mới có). Phase 2 dùng `min_importance` filter thế nào?
**Fix:** Hard-code importance defaults: corp=6, earnings=8, macro=7, news=N/A. Hoặc skip filter cho đến Phase 3.

### M3. Backfill script naming
Plan có `scripts/backfill_daily_vnindex.py` (Phase 1) + extend Phase 2 backfill cho 30 stocks. Tạo 2 scripts riêng = DRY violation.
**Fix:** 1 script duy nhất `backend/scripts/backfill-daily-candles.py` với `--symbols VNINDEX,VIC,...` flag. Phase 1 chạy với `VNINDEX` only.

### M4. Existing untracked work — chưa triage
6 untracked reports từ 25-26/02, plus 2 pending phase (VPS deploy CI/CD + backup). Plan không address:
- Commit/triage uncommitted reports?
- Phase 3-4 VPS deployment có conflict với scheduler infrastructure?
**Fix:** Phase 1 prep: triage 6 reports (commit/delete), decide VPS plan integration.

### M5. Monitoring/observability thiếu
Plan thêm 4 new cron pipelines (daily ingestion, vnstock events, RSS scraping, Gemini scoring). Không có metrics/alerts. Existing project có Prometheus + Grafana.
**Fix:** Phase 1-3 mỗi pipeline expose Prometheus counter (fetch_success, fetch_failure, items_stored, score_latency). Add Grafana panel.

### M6. No rollback / down migrations
Plan không mention `downgrade()` cho migrations. Alembic best practice cần. Existing 001 migration có downgrade.
**Fix:** Mỗi migration include downgrade.

### M7. Mobile responsive scope
Plan nói "4 pages chính". Project có 8 pages (backtest, signals, velocity, volume-analysis cũng nên responsive). Plan chỉ cover 4.
**Fix:** Phase 5 task expand: all 8 pages responsive, không chỉ 4.

### M8. Watchlist tab sync giữa browser tabs
localStorage không trigger event trong same tab. Cross-tab sync cần `window.addEventListener('storage', ...)`.
**Fix:** Phase 5 `use-watchlist.ts` implement storage event listener.

---

## 4. LOW PRIORITY — Nice to Have

- **L1.** CSV export: UTF-8 BOM cho Excel Windows compatibility
- **L2.** Watchlist limit: max 50 symbols (prevent localStorage abuse)
- **L3.** Theme: lightweight-charts cần separate config update (background color khi toggle)
- **L4.** Bundle size: Phase 4 indicators + drawing tools có thể tăng bundle 30-50KB. Code-splitting cho Phase 5.
- **L5.** Indicator type: MA = SMA hay EMA? Spec rõ. Default SMA + EMA option toggle.
- **L6.** Fibonacci retracement: anchor points spec (high-to-low vs low-to-high)?

---

## 5. Sequencing Issues

### S1. Phase 1 TDD test ordering wrong
Plan list: integration test → unit test → frontend test → implement.
Correct TDD: **unit test → implement unit → integration test → implement integration → frontend test → implement frontend**. Outside-in vs inside-out chọn nhất quán.

### S2. CORS verify phải là Step 0, không phải Step 1
Plan đặt CORS fix làm task đầu Phase 1. Thực ra verify CORS = Phase 0 (pre-flight check). Nếu prod đã work → 0 effort. Nếu chưa → 30 phút fix. Không nên block Phase 1 design work.

### S3. Phase 2 `events` table tạo trước Phase 2 vnstock fetch
Sequence: design schema → migration → implement ingestion → test. Plan checklist liệt kê đúng order nhưng không emphasize. OK.

### S4. Phase 3 risk gate "review at start of phase" — có thể quá muộn
Nếu phase 3 không khả thi (RSS blocked + Gemini quá đắt), waste 1 tuần Phase 4 work because indicators có thể làm SONG SONG với Phase 3 polish.
**Fix:** Run Phase 3 risk gate sau Phase 2 (1 ngày spike: test RSS + Gemini cost estimate). Pivot quyết định sớm.

---

## 6. Recommendation

**DO NOT START phase 1 ngay.** Cần plan revision với:

### Must address (blocking):
- [C1] Migration → Alembic Python files, KHÔNG raw SQL
- [C2] Schema types match existing (VARCHAR(10), NUMERIC(12,2))
- [C3] Step 0: verify CORS prod đã fix chưa (curl test trước commit code)
- [C4] Decide scheduler approach (APScheduler vs Docker cron) trước Phase 1
- [C5] Decide frontend test framework (vitest setup) hoặc drop frontend TDD

### Should address (significant gaps):
- [H1] SSI DailyOhlc spike task trong Phase 1
- [H2] Tailwind v4 dark mode strategy (CSS-first, not config file)
- [H3] Refactor `use-candle-data.ts` design quyết định
- [H4] Marker aggregation strategy spec
- [H5] Dedup key per source type
- [H6] vnstock dependency add + version pin
- [H7] Gemini prompt + golden set design Phase 3
- [H8] Docs sync task mỗi phase

### Realistic timeline: 7.5-9 tuần (không phải 5.5 tuần)

### Open Questions (chưa được trả lời từ brainstorm, cần làm rõ trước Phase 1):
1. Production CORS: confirm verified working at https://stock.myvivatour.com?
2. Gemini API key: env var name, who provides?
3. Macro events curation: ai update? Quarterly OK không?
4. Memory note "SSI-only" update wording chính thức?
5. Phase 3 risk gate fail → drop hay defer?

---

## Final Assessment

**Plan structure (vertical slice + TDD)** = đúng approach.
**Plan content** = nhiều assumption sai về codebase + missing infrastructure work.
**Estimate** = optimistic ~40%.

**Verdict:** Plan v1 OK as starting framework, nhưng cần revision pass để:
1. Fix Alembic + schema type mismatches (C1, C2)
2. Add scheduler + test framework infrastructure tasks
3. Add spike tasks cho SSI + vnstock + Gemini trước implement
4. Realistic estimate 7.5-9 tuần
5. Address 5 open questions từ brainstorm

Recommend: **revise plan** (15-30 min work) trước khi `/ck:cook` execute, hoặc execute với understanding gaps sẽ surface trong Phase 1 spike steps.

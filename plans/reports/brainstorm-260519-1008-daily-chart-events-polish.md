# Brainstorm: Daily Chart + Events Timeline + Polish (Vertical Slice)

**Date:** 2026-05-19
**Approach approved:** Vertical slice MVP-first (Approach 3)
**Estimated total:** 5.5 tuần (mỗi slice ship-able độc lập)

---

## 1. Problem Statement

Dự án VN Stock Tracker hiện tại real-time only, intraday focus (1-minute candles), không có chart Daily lịch sử và không có context về sự kiện thị trường. User yêu cầu:

1. **Daily chart price+volume** cho từng cổ phiếu VN30 + VNINDEX, full TA (TradingView-like)
2. **Events timeline** đa nguồn (corp actions, earnings, news, macro)
3. **Hoàn thiện feature sẵn có** — fix bugs treo, mobile responsive, theme toggle, watchlist, export

Codebase đã có nền tốt: `history_router.py` + `history_service.py` + TimescaleDB + `candlestick-chart.tsx` (lightweight-charts) → extend được, không phá kiến trúc.

---

## 2. Confirmed Requirements (5 mandatory items)

| # | Item | Concrete answer |
|---|------|-----------------|
| 1 | **Expected output** | (a) Daily chart page TradingView-like cho VN30+VNINDEX; (b) events pipeline 4 sources + chart overlay; (c) CORS bug fix, mobile responsive, theme toggle, watchlist+filter+CSV export |
| 2 | **Acceptance criteria** | Xem chi tiết §6 per slice |
| 3 | **Scope OUT** | User auth/backend state (localStorage only); real-time merge vào Daily; i18n; mobile native; fine-tuned sentiment models |
| 4 | **Constraints** | SSI-only cho OHLCV; vnstock+RSS cho events (relax constraint); Python 3.12+FastAPI+React19+TimescaleDB; 2-3 năm history |
| 5 | **Touchpoints** | Backend: `history_router.py`, `history_service.py`, NEW `daily_ingestion_service.py`, NEW `events/` module, NEW migrations. Frontend: `chart-page.tsx`, `candlestick-chart.tsx`, NEW `events-overlay.tsx`, NEW `indicators/` dir, NEW `watchlist/` hook |

---

## 3. Approaches Evaluated

### Approach 1: Sequential MVP-first
- W1: Fix bugs + Daily ingestion + chart basic
- W2-3: Indicators + events + scraping
- W4-5: Polish
- ✅ Clear progression, easy to stop
- ❌ No working chart until W1 end

### Approach 2: Parallel tracks (multi-agent)
- 4 tracks chạy song song
- ✅ Fastest wall-clock
- ❌ High conflict risk, hard review

### Approach 3 (CHOSEN): Vertical slice — END-TO-END from start
- Slice 1: 1 symbol end-to-end (VNINDEX)
- Slice 2: expand VN30 + vnstock events
- Slice 3: news RSS + sentiment
- Slice 4: TA indicators + drawing tools
- Slice 5: Polish (mobile, theme, watchlist, export)
- ✅ Integration risk minimal, demo ready sau 1.5 tuần
- ✅ Có thể stop tại slice nào cũng ship được
- ❌ Có thể cần refactor giữa chừng

---

## 4. Recommended Solution: Approach 3

### Architectural overview

```
┌─────────────────────────────────────────────────────────────────┐
│                          FRONTEND (React)                        │
│                                                                  │
│  chart-page.tsx ──┬── candlestick-chart.tsx (lightweight-charts) │
│                   ├── indicators/{ma,rsi,macd,bb}.ts             │
│                   ├── drawing-tools.tsx                          │
│                   ├── events-overlay.tsx (markers + popover)     │
│                   ├── time-range-selector.tsx                    │
│                   └── timeframe-toggle.tsx (1m / 1D)             │
│                                                                  │
│  hooks/use-daily-candles.ts, use-events.ts, use-watchlist.ts    │
│  store/theme.ts, store/watchlist.ts (localStorage)               │
└─────────────────────────────────────────────────────────────────┘
                                │
                                │ REST: /api/history/*, /api/events
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                       BACKEND (FastAPI)                         │
│                                                                  │
│  routers/history_router.py → +daily-candles endpoint            │
│  routers/events_router.py (NEW)                                  │
│                                                                  │
│  services/daily_ingestion_service.py (NEW)                       │
│    └── SSI ssi_market_service.daily_ohlc() → candles_1d         │
│                                                                  │
│  services/events/ (NEW)                                          │
│    ├── vnstock_source.py (corp actions + earnings)              │
│    ├── rss_scraper.py (CafeF + Vietstock)                       │
│    ├── macro_curator.py (FOMC/SBV/CPI manual JSON)              │
│    ├── importance_scorer.py (Gemini API)                        │
│    └── events_pipeline.py (cron 6h orchestrator)                │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                  TimescaleDB (PostgreSQL 16)                    │
│                                                                  │
│  candles_1d hypertable (symbol, date, OHLCV)                    │
│  events hypertable (id, ts, symbol, type, title, url, source,   │
│                     importance, summary)                         │
│  -- existing: candles_1m, foreign_flow, index_candles_1m, ...   │
└─────────────────────────────────────────────────────────────────┘
```

### Key design decisions

1. **Daily candles reuse existing pattern**: extend `history_service.py` thay vì NEW service. `candles_1d` là plain hypertable (không phải continuous aggregate vì source khác — SSI REST batch, không phải tick stream).
2. **Events table single hypertable**: tất cả nguồn vào 1 bảng với `type` enum. Đơn giản query, dễ filter.
3. **Importance scoring**: Gemini batch process, cache by content hash. Default threshold = 7/10 để hide noise.
4. **Drawing tools**: dùng `lightweight-charts` built-in support (`addLineSeries` + custom plugin), không bring TradingView Charting Library (license).
5. **Watchlist + theme localStorage**: simple Zustand store hoặc plain `useState` + `useEffect(JSON.stringify)`. No backend state.
6. **Mobile responsive**: TailwindCSS breakpoint pass; chart-page dùng smaller default time range + hide drawing toolbar trên mobile.

---

## 5. Implementation Slices (5.5 tuần)

### Slice 1: Foundation + Daily chart cho VNINDEX (1.5 tuần)
**Goal:** End-to-end Daily chart hoạt động cho 1 symbol duy nhất, lock kiến trúc.

- Backend:
  - Fix CORS prod bug (add `stock.myvivatour.com` to `.env`) — **trước hết**
  - Migration: `candles_1d` hypertable
  - `daily_ingestion_service.py`: SSI `DailyOhlc` REST integration, backfill 2 năm cho VNINDEX
  - Endpoint `GET /api/history/index/{name}/daily-candles?start=&end=`
  - Daily cron 17:00 VN time (sau ATC) để fetch EOD
- Frontend:
  - Toggle timeframe 1m/1D trên `chart-page.tsx`
  - Hook `use-daily-candles.ts`
  - Render Daily candle + volume (reuse `candlestick-chart.tsx`)
  - Time range selector (1M/3M/6M/1Y/2Y/All)
- Out of slice: indicators, events, drawing tools

**Definition of done:**
- Mở `/chart`, chọn timeframe Daily + symbol VNINDEX → thấy 2 năm Daily candle + volume
- Cron chạy mỗi ngày sau 17:00, candles_1d được append
- CORS prod fixed, board hiện data

---

### Slice 2: Expand VN30 + corp actions + earnings (1 tuần)
**Goal:** Tất cả VN30 stocks có Daily chart + events bắt đầu xuất hiện.

- Backend:
  - Migration: `events` hypertable
  - `vnstock_source.py`: fetch corp actions + earnings dates cho 30 stocks
  - `events_pipeline.py`: orchestrator, dedupe by `(symbol, type, date, source)`
  - `macro_curator.py`: load curated `events_macro_2024_2026.json` (50-100 events)
  - Endpoint `GET /api/events?symbol=&start=&end=&types=&min_importance=`
  - Daily backfill cho 30 VN30 stocks via SSI DailyOhlc
- Frontend:
  - Symbol selector mở rộng (VN30 dropdown đã có sẵn, chỉ wire vào Daily mode)
  - Hook `use-events.ts`
  - Render event markers trên chart (lightweight-charts `setMarkers()`)
  - Popover khi click marker

**Definition of done:**
- Chọn bất kỳ VN30 stock → Daily chart hiển thị + event pins (corp actions, earnings, macro)
- Click pin → popover với title + date + link
- 4 filter checkbox event types (chỉ active 3 loại trong slice này)

---

### Slice 3: News RSS + sentiment scoring (1 tuần)
**Goal:** Tin tức công ty + macro hoàn thiện.

- Backend:
  - `rss_scraper.py`: CafeF + Vietstock RSS feeds, parse, extract symbols mentioned
  - `importance_scorer.py`: Gemini API batch, score 0-10 + brief summary
  - Cron 6h pipeline run
  - Cache by URL hash (skip re-scoring)
- Frontend:
  - News type filter checkbox active
  - Sort/group events by importance trong popover
  - Default hide news < 7/10 importance

**Definition of done:**
- Cron 6h pull news, dedup, score, store
- Chart hiển thị news markers với color khác corp/earnings
- Slider/toggle min importance threshold

**Risk gate:** Nếu RSS scraping vướng block hoặc Gemini cost cao, fallback: chỉ FireAnt API hoặc skip news entirely.

---

### Slice 4: TA indicators + drawing tools (1 tuần)
**Goal:** Chart đạt mức "professional".

- Frontend:
  - `indicators/ma.ts`: MA20, MA50, MA200 (configurable periods)
  - `indicators/bollinger.ts`: BB(20, 2)
  - `indicators/rsi.ts`: RSI(14) trên sub-panel
  - `indicators/macd.ts`: MACD(12,26,9) trên sub-panel
  - Indicator settings panel (collapsible)
  - Drawing tools: trendline, horizontal line, fibonacci retracement
  - Persist drawings per-symbol trong localStorage

**Definition of done:**
- Toggle indicators on/off, period configurable
- Vẽ trendline, hline, fib, persist sau refresh
- Mobile: drawing tools hidden (chỉ desktop)

---

### Slice 5: Polish & convenience (1 tuần)
**Goal:** UX hoàn thiện cho daily use.

- Mobile responsive sweep: price-board, chart, derivatives, foreign-flow (TailwindCSS breakpoints `sm`/`md`)
- Dark/light theme toggle (TailwindCSS `dark:` classes + localStorage persist)
- Watchlist: star icon trên price-board rows + dedicated "Watchlist" filter tab
- Quick search/filter trên price-board (Cmd+K palette)
- CSV export button trên all data tables (price-board, volume, foreign-flow, events)

**Definition of done:**
- Test trên iPhone width 375px — không broken layout
- Theme toggle giữ sau refresh
- Star symbol → xuất hiện trong watchlist tab
- Export CSV cho 5 tables

---

## 6. Acceptance Criteria (overall)

- [ ] CORS prod fix verified: `stock.myvivatour.com` load data
- [ ] Daily chart: 2 năm history cho VN30 + VNINDEX, render <1s
- [ ] Events pipeline: 4 sources, cron 6h, dedup hoạt động
- [ ] Indicators: 4 indicators render đúng (so sánh với TradingView)
- [ ] Drawing tools: vẽ + persist + clear
- [ ] Mobile: 4 pages chính responsive 375px width
- [ ] Theme: dark/light toggle, persist
- [ ] Watchlist + CSV export functional

---

## 7. Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| vnstock API instability (TCBS/VCI hay đổi) | High | Cache aggressive 24h, fallback manual data, monitor failures |
| CafeF/Vietstock chặn scraping | Medium | User-Agent rotation, RSS chính thống trước, FireAnt API backup |
| Gemini cost runaway | Medium | Batch + cache by hash, hard limit 1000 calls/tháng, fallback rule-based scoring |
| News noise nhấn chìm chart | High | Default threshold 7/10, user toggle, max 3 markers/day per symbol |
| Daily TA chart code bloat | Medium | Plugin pattern `indicators/*.ts`, mỗi indicator <100 LOC |
| SSI DailyOhlc rate limit | Low | Batch 30 symbols × 1 day = 30 calls, không vấn đề |
| Drawing tools regression sau refactor | Low | Snapshot test cho persisted shapes |
| Mobile chart UX (drawing/indicators) | Medium | Hide tools <md breakpoint, chỉ chart+events |

---

## 8. Success Metrics

- **Functional**: tất cả acceptance criteria checked
- **Performance**: Daily chart load <1s, event pipeline cron <60s
- **Code quality**: backend test coverage ≥ 80%, no file >200 LOC ngoại lệ
- **UX**: lighthouse mobile score >85 cho chart page
- **Cost**: Gemini API <$5/tháng

---

## 9. Next Steps

1. **NOW**: User confirm proposal → tôi chuyển sang `/ck:plan` để tạo plan chi tiết với phase-XX files
2. **Plan output**: 5 phase files trong `plans/260519-1008-daily-chart-events-polish/`
3. **Execute Slice 1 first** (fix CORS bug + Daily ingestion + chart UI for VNINDEX)
4. **Review checkpoint** sau mỗi slice với code-reviewer agent
5. **Docs sync**: update `docs/development-roadmap.md` reflect Phase 9 (new scope)

---

## 10. Open Questions

1. **Domain CORS**: production domain chính xác là gì? `stock.myvivatour.com` từ debugger report, confirm?
2. **Gemini API key**: đã có `GEMINI_API_KEY` trong env chưa? Hay dùng key cá nhân?
3. **Macro events**: ai curate JSON file? Manual update mỗi tháng OK không?
4. **Watchlist sync giữa devices**: chấp nhận mất khi clear cache (localStorage only)?
5. **vnstock library**: relax constraint chính thức, hay vẫn coi là "external/optional"? Cần update memory.

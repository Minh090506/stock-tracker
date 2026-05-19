---
title: "Daily Chart + Events Timeline + Polish (V2, post-spike)"
status: pending
priority: P1
created: 2026-05-19
estimate: 8 weeks
approach: Vertical slice + TDD
brainstorm: ../reports/brainstorm-260519-1008-daily-chart-events-polish.md
review: ../reports/code-reviewer-260519-1008-plan-review.md
spike: ../reports/researcher-260519-1008-phase0-spike-findings.md
---

# Daily Chart + Events Timeline + Polish — Plan V2

## Context

Scope expansion từ real-time only → real-time + historical analytics. 3 sub-projects:
1. **Daily chart (TradingView-like)** cho VN30 + VNINDEX với full TA
2. **Events timeline đa nguồn** (vnstock + Vietstock RSS + manual macro; CafeF DROPPED)
3. **Polish features cũ** (mobile + theme + watchlist + CSV export)

V2 differs from V1: applied 14 corrections từ review + spike findings. Production backend currently 502 — must restore before execution.

## Phase Overview

| # | Phase | Status | Priority | Estimate | Key deliverables |
|---|-------|--------|----------|----------|-----------------|
| 0 | [Pre-flight](./phase-00-preflight.md) | pending | P0 | 2-3d | Prod restored, GEMINI_API_KEY, vnstock spike, infra installs |
| 1 | [Foundation + VNINDEX Daily](./phase-01-foundation-daily-vnindex.md) | pending | P1 | 1.5-2w | End-to-end Daily chart cho 1 symbol, lock architecture |
| 2 | [Events + VN30 expand](./phase-02-events-vn30.md) | pending | P1 | 1.5w | Events table + corp/earnings/macro, all VN30 Daily |
| 3 | [News + sentiment](./phase-03-news-sentiment.md) | pending | P2 | 1.5w | Vietstock RSS + Gemini scoring (drop if blocked) |
| 4 | [TA indicators + drawing](./phase-04-ta-indicators-drawing.md) | pending | P2 | 1.5w | MA/BB/RSI/MACD + trendline/hline/fib |
| 5 | [Polish + convenience](./phase-05-polish-convenience.md) | pending | P2 | 1.5-2w | Dark mode + mobile + watchlist + CSV export |

**Total: 8 weeks** (5.5w V1 was optimistic; review identified ~40% underestimate)

## Key constraints

- SSI DailyOhlc for OHLCV (verified: 1 page/symbol for 2 years, pageSize=1000)
- Vietstock RSS for news (verified working), CafeF dropped (blocked)
- vnstock v4 for corp actions (RISK: may only return future events; fallback = manual seed)
- localStorage for user state (no auth)
- Alembic Python migrations (not raw SQL)
- Schema match existing: `VARCHAR(10)`, `NUMERIC(12,2)`
- APScheduler in-process (no external cron sidecar)
- Tailwind v4 CSS-first dark mode

## Out of scope

User auth/backend state, intraday merge into Daily, i18n, mobile native, TradingView Charting Library, advanced sentiment models.

## Dependencies

Each phase blocks the next (no parallelism within plan). Phase 0 blocks all.

## Risks (top-3)

1. **vnstock historical events** — may not support past data. Mitigation: Phase 0 spike test; fallback manual JSON seed.
2. **Gemini API cost / availability** — needs key. Mitigation: hard $5/mo limit + cache + fallback rule-based.
3. **Production backend instability** — currently 502. Mitigation: Phase 0 restore + add health check + alerts.

## Success Criteria (whole plan)

- [ ] All VN30 stocks + VNINDEX có 2 năm Daily chart load <1s
- [ ] Event timeline 3-4 nguồn, dedup hoạt động, cron 6h
- [ ] 4 TA indicators + 3 drawing tools functional, persist
- [ ] All 8 pages mobile responsive ở 375px
- [ ] Theme toggle, watchlist, CSV export functional
- [ ] Production backend healthy 99%+ uptime
- [ ] Backend test coverage ≥80%, no file >200 LOC

---
title: "VN30 Price Board"
description: "Real-time 30-stock price board with sparklines, sorting, and flash animation via WebSocket"
status: complete
priority: P1
effort: 3h
branch: master
tags: [frontend, backend, websocket, price-board]
created: 2026-02-09
---

# VN30 Price Board

## Problem
MarketSnapshot has volume/foreign/index/derivatives data but **no stock prices**. SSI sends prices via TradeMessage and QuoteMessage but they are not cached or exposed. Users need a primary price board showing all 30 VN30 stocks with real-time prices.

## Solution
1. **Backend**: Add `PriceData` model, cache last trade prices in `MarketDataProcessor`, include in `MarketSnapshot`
2. **Frontend**: New price board page with sortable table, inline SVG sparklines, flash animation, loading skeleton

## Architecture
```
SSITradeMessage.last_price ──→ price_cache dict ──→ MarketSnapshot.prices
SSIQuoteMessage.ref/ceil/floor ──→ QuoteCache ──────┘ (merged at snapshot time)
                                                     │
MarketSnapshot ──→ WS /ws/market ──→ useWebSocket<MarketSnapshot>("market")
                                      └──→ PriceBoardPage → table + sparklines
```

## Phases

| # | Phase | Files | Status |
|---|-------|-------|--------|
| 1 | [Backend: Price Data](./phase-01-backend-price-data.md) | 3 modified | ✅ complete |
| 2 | [Frontend: Price Board](./phase-02-frontend-price-board.md) | 2 modified, 5 new | ✅ complete |

## Key Decisions
- Sparklines: frontend-only accumulation (last 50 ticks from WS updates, no backend storage)
- Inline SVG for sparklines (no charting library needed for simple 50-point line)
- Color: green=up, red=down, yellow=ceiling/floor (user-specified, differs from VN convention)
- VN30 symbol filtering done in frontend via `/api/vn30-components`
- Flash animation via CSS transition tracking previous price per row
- All files under 200 lines

## Dependencies
- `useWebSocket` hook (exists, not yet used by any page)
- `/api/vn30-components` endpoint (exists)
- `/ws/market` channel (exists, broadcasts `MarketSnapshot`)

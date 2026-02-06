---
title: "Vietnamese Stock Market Tracker (Revised)"
description: "Real-time VN30 stock tracking with foreign investor monitoring, derivatives/basis analysis, active buy/sell classification, and analytics alerts"
status: pending
priority: P1
effort: 38h
branch: main
tags: [fullstack, websocket, finance, realtime, analytics]
created: 2026-02-06
---

# Vietnamese Stock Market Tracker - Revised Implementation Plan

## Overview
Web app for Vietnamese stock market with 5 core features:
1. **Bang gia VN30** - Real-time stock price board (30 VN30 stocks)
2. **Chi so** - VN30 + VNINDEX real-time index tracking
3. **Phai sinh** - VN30F 1M futures price, basis (futures - spot), NN on derivatives
4. **Theo doi NDTNN** - Foreign investor tracking (volume + speed + acceleration)
5. **Mua/Ban chu dong** - Active buy/sell volume classification
6. **Analytics** - NN alerts, NN vs price correlation, futures-spot divergence

## What Changed from Old Plan
Previous plan: `/Users/minh/plans/260206-1341-stock-tracker-system/`

| Issue | Old Plan | New Plan |
|-------|----------|----------|
| Trade classification volume | TotalVol (CUMULATIVE - WRONG) | LastVol (PER-TRADE - CORRECT) |
| Foreign investor source | vnstock polling every 30s | SSI Channel R (native, real-time) |
| Channel format | `HOSE.VNM` (WRONG) | `X:VNM`, `R:ALL`, `MI:VN30` |
| Derivatives | Missing entirely | VN30F{YYMM} via Channel X |
| Index tracking | Missing entirely | Channel MI: VN30, VNINDEX |
| Analytics/Alerts | Missing entirely | NN alerts, correlation, basis analysis |
| TCBS backup | Planned as foreign data source | Removed (deprecated Dec 2024) |
| vnstock dependency | Required for foreign data | Removed (SSI has all data) |

## Tech Stack
- **Backend:** Python 3.12+, FastAPI, uvicorn, pydantic, ssi-fc-data, asyncpg
- **Frontend:** React 19, TypeScript, Vite, TailwindCSS v4, TradingView Lightweight Charts
- **Database:** PostgreSQL
- **Deployment:** Docker Compose (team <5 people)
- **Data Source:** SSI FastConnect WebSocket ONLY (no vnstock, no TCBS)

## Project Location
`~/projects/stock-tracker/` (monorepo: `backend/` + `frontend/`)

## Phases

| # | Phase | Est. | Status | Deps |
|---|-------|------|--------|------|
| 1 | [Project Scaffolding](./phase-01-project-scaffolding.md) | 3h | pending | - |
| 2 | [SSI Integration & Stream Demux](./phase-02-ssi-integration-stream-demux.md) | 5h | pending | P1 |
| 3 | [Data Processing Core](./phase-03-data-processing-core.md) | 6h | pending | P2 |
| 4 | [Backend WS Server + REST API](./phase-04-backend-websocket-rest-api.md) | 4h | pending | P3 |
| 5 | [Frontend Dashboard](./phase-05-frontend-dashboard.md) | 6h | pending | P4 |
| 6 | [Analytics Engine](./phase-06-analytics-engine.md) | 5h | pending | P3,P4 |
| 7 | [Database Persistence](./phase-07-database-persistence.md) | 5h | pending | P1 |
| 8 | [Testing & Deployment](./phase-08-testing-deployment.md) | 4h | pending | All |

## Architecture
```
SSI WebSocket (SignalR)
├── X-TRADE:ALL  → Trade events (LastPrice, LastVol per-trade)
├── X-Quote:ALL  → Order book (BidPrice1-10, AskPrice1-10)
├── R:ALL        → Foreign investor (FBuyVol, FSellVol cumulative)
├── MI:VN30      → VN30 index value
├── MI:VNINDEX   → VNINDEX value
├── X:VN30F{YYMM}→ Derivatives futures
└── B:ALL        → OHLC bars for charting
        │
   FastAPI Backend
   ├── QuoteCache ──► TradeClassifier ──► SessionAggregator
   ├── ForeignTracker (delta + speed)
   ├── IndexTracker (VN30/VNINDEX)
   ├── DerivativesTracker (basis = futures - spot)
   ├── AnalyticsEngine (alerts, correlation, divergence)
   ├── WS Server → React clients
   └── PostgreSQL (history)
        │
   React Frontend (single WS connection)
```

## Key Dependencies
- SSI iBoard API credentials (Consumer ID + Secret) - user HAS credentials
- Node.js 20+ / Python 3.12+
- Vietnamese market hours: 09:00-11:30, 13:00-14:45 (continuous), 14:45-15:00 (ATC)

## Research Reports
- [SSI WebSocket Data Format](../reports/researcher-260206-1423-ssi-fastconnect-websocket-data-format.md)
- [TCBS API Status (Deprecated)](../reports/researcher-260206-1423-tcbs-api-endpoints.md)
- [Old Plan SSI API Report](../260206-1341-stock-tracker-system/research/researcher-01-ssi-api-report.md)
- [Old Plan Architecture Report](../260206-1341-stock-tracker-system/research/researcher-02-architecture-report.md)

## Key Decisions
- **SSI as single data source** - Channel X (trades), R (foreign), MI (indices), B (OHLC bars)
- **No vnstock, no TCBS** - both unnecessary since SSI has all data
- **LastVol for trade classification** - per-trade volume, NOT TotalVol (cumulative)
- **Foreign delta tracking** - Channel R sends cumulative; compute deltas for speed/acceleration
- **Full backend proxy** - SSI→FastAPI→React (centralized processing, secure credentials, DB persistence)
- **PostgreSQL** - trade history, foreign snapshots, analytics data
- **Batch DB writes** - every 1s, not per-trade, to reduce load

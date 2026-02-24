---
title: "Order Velocity vs VN30F Price Correlation"
description: "Real-time velocity tracking with correlation analysis for VN30F derivatives"
status: in-progress
priority: P1
effort: 24h
branch: master
tags: [velocity, correlation, derivatives, analytics, timescaledb]
created: 2026-02-24
---

# Order Velocity vs VN30F Price Correlation

## Objective

Track buy/sell order velocity (volume/time, count/time, value/time) for VN30F and VN30 basket, compute rolling Pearson correlation with VN30F price changes, display on real-time dashboard with automated divergence alerts. Includes historical backtest engine for lead-lag discovery, threshold optimization, and time-of-day pattern analysis.

## Architecture

```
tick_data (hypertable)
    |
    +---> order_velocity_1m (continuous aggregate) ---> REST history endpoint
    |                                                      |
    +---> VelocityTracker (Python, real-time deque)        +---> BacktestEngine
    |         |                                                   (cross-corr, threshold, patterns)
    |         +---> CorrelationEngine (rolling Pearson)           |
    |         |         |                                         +---> REST /api/backtest/*
    |         |         +---> MarketSnapshot WS                   +---> Frontend Dashboard
    |         |
    |         +---> PriceTracker (alert rules) ---> /ws/alerts
    |
    +---> candles_1m (existing) ---> BacktestEngine (VN30F price data)
```

## Phases

| # | Phase | Effort | Status |
|---|-------|--------|--------|
| 1 | [Data Layer](./phase-01-data-layer-velocity-aggregate.md) | 2h | pending |
| 2 | [Backend Services](./phase-02-backend-velocity-and-correlation-services.md) | 5h | complete |
| 3 | [API Layer](./phase-03-api-velocity-endpoints.md) | 2h | complete |
| 4 | [Frontend Dashboard](./phase-04-frontend-velocity-dashboard.md) | 5h | complete |
| 5 | [Alert Signals](./phase-05-alert-velocity-signals.md) | 2h | complete |
| 6 | [Backtest Engine](./phase-06-backtest-analysis-engine.md) | 4h | pending |
| 7 | [Backtest Dashboard](./phase-07-frontend-backtest-dashboard.md) | 4h | pending |

## Key Decisions

- **Granularity**: 1-minute buckets (matches existing candles_1m pattern)
- **VN30 basket**: Equal-weight SUM across 30 stocks (no cap-weight)
- **Correlation**: Pure Python Pearson (no numpy dependency)
- **Delivery**: Extend existing `MarketSnapshot` with optional `velocity` field
- **Backtest**: 3 analysis types (cross-correlation, threshold, patterns); hybrid pre-computed daily + on-demand
- **Min data**: 5 trading days for basic, 20 for statistically significant results

## Dependencies

- `tick_data` hypertable (exists)
- `vn30_symbols` list (cached at startup in `main.py`)
- `DerivativesTracker` for VN30F price data (exists)

## Risks

- Correlation != causation -- UI disclaimer required
- 1-min aggregate lag -- supplemented by real-time Python tracker
- Low VN30F volume -- min sample filter (>10 trades/min)
- Insufficient backtest data -- graceful "collecting data" message, show progress (X/5 days)

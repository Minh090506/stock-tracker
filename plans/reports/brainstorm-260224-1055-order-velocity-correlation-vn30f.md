# Brainstorm: Order Velocity vs VN30F Price Correlation

**Date**: 2026-02-24
**Status**: Agreed — Hybrid Approach (TimescaleDB + Python)

## Problem Statement

Theo dõi và tìm mối tương quan giữa tốc độ lệnh mua/bán chủ động với biến động giá VN30F phái sinh.

## Requirements

- **Metrics**: volume/time, count/time, value/time, imbalance ratio, acceleration
- **Scope**: VN30F tự thân + VN30 basket (30 cổ phiếu, equal weight)
- **Goal**: Dashboard real-time + Alert tự động (backtest lịch sử → làm sau)
- **Granularity**: 1 phút
- **Basket weighting**: Equal weight (SUM)

## Agreed Solution: Hybrid (TimescaleDB + Python)

### Data Layer
- New `order_velocity_1m` continuous aggregate from `tick_data`
- Fields: buy_vol, sell_vol, buy_count, sell_count, buy_value, sell_value
- `vn30_basket_velocity_1m` view aggregating 30 VN30 stocks

### Compute Layer
- Python `VelocityTracker`: rolling deque, speed/acceleration per symbol
- Python `CorrelationEngine`: rolling Pearson correlation (velocity vs VN30F price change)
- Pattern: same as `ForeignInvestorTracker` (deque + speed + acceleration)

### API Layer
- REST endpoints for velocity data
- WebSocket channel for real-time velocity + correlation push

### Frontend
- Dual-axis chart: velocity bars + VN30F price line overlay
- Correlation coefficient display
- Real-time velocity meter

### Alerts
- `VELOCITY_DIVERGENCE`: buy velocity surging, price flat
- `IMBALANCE_EXTREME`: buy/sell ratio > 3x or < 0.33x

## Phases

1. **Data**: `order_velocity_1m` aggregate + migration
2. **Backend**: `VelocityTracker` + `CorrelationEngine` services
3. **API**: REST + WebSocket endpoints
4. **Frontend**: Charts + correlation display
5. **Alerts**: New signal types in PriceTracker
6. **Backtest Engine**: Cross-correlation lead-lag, threshold discovery, time-of-day patterns (pure SQL+Python)
7. **Backtest Dashboard**: Interactive UI with correlation heatmap, probability table, pattern chart

## Risks

- Correlation ≠ causation → disclaimer on UI
- 1-min lag from aggregate refresh → supplement with real-time Python
- Low VN30F volume → min sample filter (>10 trades/min)

## Unresolved

1. VN30 component list source — need SSI REST `IndexComponents` call
2. Open Interest availability from SSI
3. B:ALL channel data — currently discarded, potential alternative to self-aggregation

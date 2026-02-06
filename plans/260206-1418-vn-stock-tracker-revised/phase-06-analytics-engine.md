# Phase 06: Analytics Engine

## Context Links
- [Plan Overview](./plan.md)
- [Phase 03: Data Processing](./phase-03-data-processing-core.md)
- [Phase 04: Backend WS](./phase-04-backend-websocket-rest-api.md)

## Overview
- **Priority:** P1
- **Status:** pending
- **Effort:** 5h
- Server-side analytics: foreign investor alert system (threshold + acceleration), NN vs price correlation/divergence detection, futures-spot basis trend analysis.

## Requirements

### Functional
- **NN Alerts**: Trigger when foreign net buy/sell exceeds threshold per symbol, or when buying/selling speed accelerates (doubles within 5 min)
- **NN vs Price Correlation**: Detect divergence - price up but NN selling (bearish), price down but NN buying (bullish)
- **Basis Analysis**: Track basis trend (narrowing/widening), alert on premium/discount flip
- Alerts broadcast to all WS clients in real-time
- Alert history stored for review

### Non-Functional
- Alert generation <10ms
- No false positives from initialization (ignore first 5 min of session)
- Configurable thresholds via settings

## Architecture
```
MarketDataProcessor
    │
    ├── on_trade_classified ──→ PriceTracker (track price movement per symbol)
    ├── on_foreign_updated ──→ AlertService.check_foreign_alerts()
    │                              ├── Threshold check (net vol > 50K)
    │                              ├── Acceleration check (speed doubles)
    │                              └── Divergence check (NN vs Price)
    └── on_basis_updated ──→ AlertService.check_basis_alerts()
                                   ├── Premium/discount flip
                                   └── Basis widening/narrowing
              │
              ▼
         WS broadcast to all clients: {"type": "alert", ...}
```

## Related Code Files
- `~/projects/stock-tracker/backend/app/services/analytics_engine.py` - Core orchestrator
- `~/projects/stock-tracker/backend/app/services/alert_service.py` - Alert rules + dispatch
- `~/projects/stock-tracker/backend/app/services/price_tracker.py` - Track price movement per symbol
- `~/projects/stock-tracker/backend/app/models/schemas.py` - Alert model

## Implementation Steps

### 1. Add Alert model to schemas.py
```python
class AlertSeverity(str, Enum):
    INFO = "info"
    HIGH = "high"
    CRITICAL = "critical"

class Alert(BaseModel):
    symbol: str
    alert_type: str       # foreign_threshold, foreign_acceleration, nn_divergence, basis_flip
    message: str
    severity: AlertSeverity
    timestamp: datetime
```

### 2. Create PriceTracker (`services/price_tracker.py`)
```python
"""Track price movement per symbol for divergence detection."""
from collections import deque

class PriceTracker:
    def __init__(self):
        self._prices: dict[str, deque[tuple[datetime, float]]] = {}

    def update(self, symbol: str, price: float):
        if symbol not in self._prices:
            self._prices[symbol] = deque(maxlen=300)  # ~5 min
        self._prices[symbol].append((datetime.now(), price))

    def get_price_change(self, symbol: str, window_minutes: int = 5) -> float:
        """Returns price change % over window. Positive = price up."""
        history = self._prices.get(symbol)
        if not history or len(history) < 2:
            return 0.0
        cutoff = datetime.now() - timedelta(minutes=window_minutes)
        old = next((p for t, p in history if t >= cutoff), history[0][1])
        current = history[-1][1]
        return ((current - old) / old) * 100 if old > 0 else 0.0
```

### 3. Create AlertService (`services/alert_service.py`)
```python
"""Alert generation: NN threshold, acceleration, divergence, basis."""

class AlertService:
    def __init__(self, foreign_tracker, price_tracker, derivatives_tracker, ws_manager):
        self._foreign = foreign_tracker
        self._prices = price_tracker
        self._derivatives = derivatives_tracker
        self._ws = ws_manager
        self._cooldowns: dict[str, datetime] = {}  # prevent alert spam

        # Configurable thresholds
        self.net_volume_threshold = 50_000    # shares
        self.speed_threshold_per_min = 10_000  # shares/min
        self.acceleration_factor = 2.0         # speed doubles
        self.divergence_threshold = 1.0        # % price change
        self.basis_flip_cooldown_min = 5
        self._prev_speeds: dict[str, float] = {}
        self._prev_basis_sign: bool | None = None
        self._session_start = datetime.now()

    async def check_foreign_alerts(self, symbol: str):
        # Skip first 5 min (initialization noise)
        if (datetime.now() - self._session_start).total_seconds() < 300:
            return

        data = self._foreign.get(symbol)
        alerts = []

        # 1. Threshold alert
        if abs(data.net_volume) > self.net_volume_threshold:
            direction = "mua rong" if data.net_volume > 0 else "ban rong"
            alerts.append(Alert(
                symbol=symbol,
                alert_type="foreign_threshold",
                message=f"NN {direction} {abs(data.net_volume):,} CP",
                severity=AlertSeverity.HIGH,
                timestamp=datetime.now(),
            ))

        # 2. Acceleration alert
        current_speed = abs(data.buy_speed_per_min - data.sell_speed_per_min)
        prev = self._prev_speeds.get(symbol, 0)
        if prev > 0 and current_speed > prev * self.acceleration_factor:
            alerts.append(Alert(
                symbol=symbol,
                alert_type="foreign_acceleration",
                message=f"NN tang toc: {current_speed:.0f}/phut (truoc: {prev:.0f})",
                severity=AlertSeverity.CRITICAL,
                timestamp=datetime.now(),
            ))
        self._prev_speeds[symbol] = current_speed

        # 3. NN vs Price divergence
        price_change = self._prices.get_price_change(symbol)
        if abs(price_change) > self.divergence_threshold:
            if price_change > 0 and data.net_volume < -self.net_volume_threshold:
                alerts.append(Alert(
                    symbol=symbol,
                    alert_type="nn_divergence_bearish",
                    message=f"Gia tang {price_change:.1f}% nhung NN ban rong {abs(data.net_volume):,}",
                    severity=AlertSeverity.HIGH,
                    timestamp=datetime.now(),
                ))
            elif price_change < 0 and data.net_volume > self.net_volume_threshold:
                alerts.append(Alert(
                    symbol=symbol,
                    alert_type="nn_divergence_bullish",
                    message=f"Gia giam {abs(price_change):.1f}% nhung NN mua rong {data.net_volume:,}",
                    severity=AlertSeverity.HIGH,
                    timestamp=datetime.now(),
                ))

        # Broadcast with cooldown (max 1 alert per type per symbol per 2 min)
        for alert in alerts:
            key = f"{alert.symbol}:{alert.alert_type}"
            last = self._cooldowns.get(key)
            if last and (datetime.now() - last).total_seconds() < 120:
                continue
            self._cooldowns[key] = datetime.now()
            await self._ws.broadcast_to_all({
                "type": "alert",
                "data": alert.model_dump(mode="json"),
            })

    async def check_basis_alerts(self, basis_point: BasisPoint):
        if self._prev_basis_sign is not None:
            if basis_point.is_premium != self._prev_basis_sign:
                label = "Premium" if basis_point.is_premium else "Discount"
                await self._ws.broadcast_to_all({
                    "type": "alert",
                    "data": Alert(
                        symbol=basis_point.futures_symbol,
                        alert_type="basis_flip",
                        message=f"Basis chuyen sang {label}: {basis_point.basis:+.2f}",
                        severity=AlertSeverity.CRITICAL,
                        timestamp=datetime.now(),
                    ).model_dump(mode="json"),
                })
        self._prev_basis_sign = basis_point.is_premium
```

### 4. Wire into processor pipeline
```python
# In main.py or processor
async def handle_trade(msg):
    classified, stats = await processor.handle_trade(msg)
    if classified:
        price_tracker.update(classified.symbol, classified.price)
        # broadcast trade...

async def handle_foreign(msg):
    data = await processor.handle_foreign(msg)
    await alert_service.check_foreign_alerts(msg.symbol)
    # broadcast foreign...

async def handle_basis(bp):
    if bp:
        await alert_service.check_basis_alerts(bp)
```

## Todo List
- [ ] Add Alert/AlertSeverity models to schemas.py
- [ ] Create PriceTracker (rolling price history per symbol)
- [ ] Create AlertService with configurable thresholds
- [ ] Implement NN threshold alert
- [ ] Implement NN acceleration alert
- [ ] Implement NN vs Price divergence alert
- [ ] Implement basis premium/discount flip alert
- [ ] Add alert cooldown (prevent spam)
- [ ] Skip alerts during first 5 min of session
- [ ] Wire alerts into processor pipeline
- [ ] Test: mock foreign surge → alert generated
- [ ] Test: mock divergence → bearish/bullish alert
- [ ] Test: cooldown prevents duplicate alerts

## Success Criteria
- Foreign net buy > 50K → "foreign_threshold" alert broadcasts
- Speed doubles → "foreign_acceleration" alert
- Price up + NN selling → "nn_divergence_bearish" alert
- Basis flips premium↔discount → "basis_flip" alert
- No alerts during first 5 min (initialization)
- Max 1 alert per type/symbol per 2 min (cooldown)
- Alerts appear in frontend AlertFeed panel

## Risk Assessment
- **False positives:** Thresholds may need tuning per market conditions. Make configurable.
- **Cooldown too aggressive:** 2 min may miss rapid changes. Adjust if needed.
- **Divergence detection lag:** Price change computed over 5 min window. May miss intraday spikes.
- **Data gaps:** If Channel R updates infrequently, speed calculation may be inaccurate.

## Next Steps
- Phase 07: Database persistence for trade history and alert storage

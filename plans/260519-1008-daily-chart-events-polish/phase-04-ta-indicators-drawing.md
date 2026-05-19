---
phase: 4
title: "TA indicators + drawing tools"
status: pending
priority: P2
effort: "1.5w"
dependencies: [2]
note: "Can run parallel to Phase 3 if news pipeline drops"
---

# Phase 4: TA Indicators + Drawing Tools

## Overview
Chart đạt mức "professional" với 4 chuẩn indicators + 3 drawing tools. Pure frontend work, không phụ thuộc Phase 3 news.

## Requirements

### Functional
- MA (configurable periods, default MA20/50/200) — SMA primary, EMA toggle
- Bollinger Bands BB(20, 2)
- RSI(14) trên sub-panel below main chart
- MACD(12, 26, 9) trên sub-panel
- Indicator settings panel collapsible
- Drawing tools: trendline, horizontal line, fibonacci retracement
- Drawing persistence per-symbol trong localStorage
- Mobile: drawing tools hidden (<md breakpoint)

### Non-functional
- Indicator values match TradingView reference (sanity test on VNINDEX)
- No file >200 LOC (split indicators each in own file)
- Bundle size impact <30KB gzipped

## Architecture

```
Frontend new components:
  src/components/charts/indicators/
    sma.ts                 (Simple Moving Average)
    ema.ts                 (Exponential Moving Average)
    bollinger.ts           (BB(20, 2))
    rsi.ts                 (RSI Wilder smoothing)
    macd.ts                (MACD with signal + histogram)
    index.ts               (registry)
  src/components/charts/indicators-panel.tsx
  src/components/charts/drawing-tools.tsx
  src/components/charts/drawings/
    trendline.ts
    horizontal-line.ts
    fibonacci-retracement.ts
  src/hooks/use-chart-drawings.ts        (localStorage persist)
```

lightweight-charts v4.2.0 supports Custom Primitives API for drawing tools. No license cost.

## Related Code Files

### Modify
- `frontend/src/pages/chart-page.tsx` — add indicators panel + drawing tools wiring
- `frontend/src/components/charts/candlestick-chart.tsx` — expose chart instance ref to parent (drawing tools need it)

### Create
- `frontend/src/components/charts/indicators/sma.ts`
- `frontend/src/components/charts/indicators/ema.ts`
- `frontend/src/components/charts/indicators/bollinger.ts`
- `frontend/src/components/charts/indicators/rsi.ts`
- `frontend/src/components/charts/indicators/macd.ts`
- `frontend/src/components/charts/indicators/index.ts` (registry)
- `frontend/src/components/charts/indicators-panel.tsx`
- `frontend/src/components/charts/drawing-tools.tsx`
- `frontend/src/components/charts/drawings/trendline.ts`
- `frontend/src/components/charts/drawings/horizontal-line.ts`
- `frontend/src/components/charts/drawings/fibonacci-retracement.ts`
- `frontend/src/hooks/use-chart-drawings.ts`
- `frontend/src/__tests__/indicators-sma.test.ts`
- `frontend/src/__tests__/indicators-rsi.test.ts`
- `frontend/src/__tests__/indicators-macd.test.ts`
- `frontend/src/__tests__/indicators-bollinger.test.ts`

## Implementation Steps

### Step 1: SMA indicator
```ts
// indicators/sma.ts
import type { LWCandle } from "../../../types";

export function calculateSMA(candles: LWCandle[], period: number): { time: number; value: number }[] {
  if (period < 1) throw new Error("Period must be ≥ 1");
  const out: { time: number; value: number }[] = [];
  for (let i = period - 1; i < candles.length; i++) {
    let sum = 0;
    for (let j = i - period + 1; j <= i; j++) sum += candles[j].close;
    out.push({ time: candles[i].time, value: sum / period });
  }
  return out;
}
```

### Step 2: EMA indicator
```ts
// indicators/ema.ts
export function calculateEMA(candles: LWCandle[], period: number): { time: number; value: number }[] {
  const k = 2 / (period + 1);
  const out: { time: number; value: number }[] = [];
  let ema = candles[0]?.close;
  for (let i = 0; i < candles.length; i++) {
    if (i === 0) {
      ema = candles[i].close;
    } else {
      ema = candles[i].close * k + ema! * (1 - k);
    }
    if (i >= period - 1) out.push({ time: candles[i].time, value: ema });
  }
  return out;
}
```

### Step 3: Bollinger Bands
```ts
// indicators/bollinger.ts
import { calculateSMA } from "./sma";

export interface BBPoint { time: number; upper: number; middle: number; lower: number; }

export function calculateBB(candles: LWCandle[], period = 20, stdMul = 2): BBPoint[] {
  const sma = calculateSMA(candles, period);
  const out: BBPoint[] = [];
  for (let i = period - 1; i < candles.length; i++) {
    const window = candles.slice(i - period + 1, i + 1);
    const mean = sma[i - (period - 1)].value;
    const variance = window.reduce((s, c) => s + (c.close - mean) ** 2, 0) / period;
    const sd = Math.sqrt(variance);
    out.push({
      time: candles[i].time,
      middle: mean,
      upper: mean + stdMul * sd,
      lower: mean - stdMul * sd,
    });
  }
  return out;
}
```

### Step 4: RSI (Wilder smoothing)
```ts
// indicators/rsi.ts
export function calculateRSI(candles: LWCandle[], period = 14): { time: number; value: number }[] {
  if (candles.length < period + 1) return [];
  let avgGain = 0, avgLoss = 0;
  // Seed with simple averages
  for (let i = 1; i <= period; i++) {
    const diff = candles[i].close - candles[i - 1].close;
    if (diff > 0) avgGain += diff; else avgLoss += -diff;
  }
  avgGain /= period;
  avgLoss /= period;

  const out: { time: number; value: number }[] = [];
  let rs = avgLoss === 0 ? Infinity : avgGain / avgLoss;
  out.push({ time: candles[period].time, value: 100 - 100 / (1 + rs) });

  // Wilder smoothing for subsequent
  for (let i = period + 1; i < candles.length; i++) {
    const diff = candles[i].close - candles[i - 1].close;
    const gain = diff > 0 ? diff : 0;
    const loss = diff < 0 ? -diff : 0;
    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;
    rs = avgLoss === 0 ? Infinity : avgGain / avgLoss;
    out.push({ time: candles[i].time, value: 100 - 100 / (1 + rs) });
  }
  return out;
}
```

### Step 5: MACD
```ts
// indicators/macd.ts
import { calculateEMA } from "./ema";

export interface MACDPoint { time: number; macd: number; signal: number; histogram: number; }

export function calculateMACD(
  candles: LWCandle[], fast = 12, slow = 26, signalPeriod = 9
): MACDPoint[] {
  const fastEMA = calculateEMA(candles, fast);
  const slowEMA = calculateEMA(candles, slow);

  // Align by time (slow starts later)
  const fastMap = new Map(fastEMA.map((p) => [p.time, p.value]));
  const macdLine: { time: number; value: number }[] = slowEMA
    .filter((p) => fastMap.has(p.time))
    .map((p) => ({ time: p.time, value: fastMap.get(p.time)! - p.value }));

  // Signal = EMA of macdLine
  const synthetic = macdLine.map((p) => ({
    time: p.time, open: p.value, high: p.value, low: p.value, close: p.value,
  })) as any[];
  const signalLine = calculateEMA(synthetic, signalPeriod);
  const signalMap = new Map(signalLine.map((p) => [p.time, p.value]));

  return macdLine
    .filter((p) => signalMap.has(p.time))
    .map((p) => ({
      time: p.time,
      macd: p.value,
      signal: signalMap.get(p.time)!,
      histogram: p.value - signalMap.get(p.time)!,
    }));
}
```

### Step 6: Indicators registry + panel
```ts
// indicators/index.ts
export { calculateSMA } from "./sma";
export { calculateEMA } from "./ema";
export { calculateBB } from "./bollinger";
export { calculateRSI } from "./rsi";
export { calculateMACD } from "./macd";

export interface IndicatorConfig {
  id: string;
  enabled: boolean;
  period?: number;
  color?: string;
}
```

```tsx
// indicators-panel.tsx
export function IndicatorsPanel({ configs, onChange }) {
  return (
    <div className="bg-gray-800 p-3 rounded-md">
      {INDICATORS.map((ind) => (
        <div key={ind.id} className="flex items-center gap-2 mb-2">
          <input type="checkbox" ... />
          <span>{ind.label}</span>
          {ind.hasPeriod && <input type="number" ... />}
        </div>
      ))}
    </div>
  );
}
```

### Step 7: Wire indicators to chart
```tsx
// chart-page.tsx — extend
const [indicatorConfigs, setIndicatorConfigs] = useState<IndicatorConfig[]>([
  { id: "ma20", enabled: true, period: 20, color: "#3b82f6" },
  { id: "ma50", enabled: false, period: 50, color: "#eab308" },
  { id: "ma200", enabled: false, period: 200, color: "#ef4444" },
  { id: "bb", enabled: false, period: 20 },
  { id: "rsi", enabled: false, period: 14 },
  { id: "macd", enabled: false },
]);

// In candlestick-chart.tsx accept indicatorConfigs prop; add line series for each enabled
```

### Step 8: Drawing tools — base class + plugin
lightweight-charts v4 Custom Primitives API:
```ts
// drawings/horizontal-line.ts
import type { ISeriesPrimitive } from "lightweight-charts";

export class HorizontalLineDrawing implements ISeriesPrimitive<"Candlestick"> {
  constructor(private price: number, private color: string) {}
  // implement paneViews(), priceAxisViews(), etc
  // Reference: lightweight-charts v4 Primitives docs
}
```

### Step 9: Trendline drawing
Trendline = 2 anchor points. User clicks 2 points on chart, line drawn through.
```ts
// drawings/trendline.ts
export class TrendlineDrawing {
  constructor(public p1: {time: number; price: number}, public p2: {time: number; price: number}) {}
  // Implement primitive paint method
}
```

### Step 10: Fibonacci retracement
2 anchor points (high & low) → draw horizontal lines at 0%, 23.6%, 38.2%, 50%, 61.8%, 78.6%, 100%:
```ts
// drawings/fibonacci-retracement.ts
export class FibRetracementDrawing {
  static readonly LEVELS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0];
  constructor(public high: number, public low: number, public startTime: number, public endTime: number) {}
}
```

### Step 11: Drawing persistence
```ts
// hooks/use-chart-drawings.ts
const STORAGE_KEY = "chart-drawings";

interface PersistedDrawing { symbol: string; type: string; data: unknown; }

export function useChartDrawings(symbol: string) {
  const [drawings, setDrawings] = useState<PersistedDrawing[]>([]);

  // Load from localStorage on mount
  useEffect(() => {
    const all: PersistedDrawing[] = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    setDrawings(all.filter((d) => d.symbol === symbol));
  }, [symbol]);

  const add = (drawing: PersistedDrawing) => {
    const all: PersistedDrawing[] = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    all.push(drawing);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(all));
    setDrawings(all.filter((d) => d.symbol === symbol));
  };

  const clear = () => {
    const all: PersistedDrawing[] = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    const kept = all.filter((d) => d.symbol !== symbol);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(kept));
    setDrawings([]);
  };

  return { drawings, add, clear };
}
```

### Step 12: Mobile detection — hide drawing tools
```tsx
// drawing-tools.tsx
const isDesktop = useMediaQuery("(min-width: 768px)");  // md breakpoint
if (!isDesktop) return null;
```

### Step 13: Docs sync
- Update `docs/user-guide.md` — chart indicators + drawing usage
- Update `docs/system-architecture.md` — frontend indicators module

## Tests (TDD order)

1. **indicators-sma.test.ts**: SMA period 3 of [1, 2, 3, 4, 5] = [2, 3, 4] starting at index 2
2. **indicators-bollinger.test.ts**: Known input → known upper/middle/lower
3. **indicators-rsi.test.ts**: Wilder RSI of canonical 14-period input matches reference (TradingView sample: AAPL daily close, period 14)
4. **indicators-macd.test.ts**: MACD line + signal line + histogram for known input
5. **Manual cross-check**: Load VNINDEX 2y daily, calculate MA200, eyeball-match TradingView VNINDEX MA200 (within 0.1% tolerance)

## Success Criteria

- [ ] 4 indicators implemented, unit tests pass
- [ ] Toggle indicators on/off works
- [ ] Indicator values within 0.5% of TradingView reference for 5 sample symbols
- [ ] Drawing tools: trendline, hline, fib functional on desktop
- [ ] Drawings persist after page refresh
- [ ] Drawings cleared when switching symbol (display only that symbol's drawings)
- [ ] Mobile (<768px): drawing tools hidden
- [ ] Bundle size delta <30KB gzipped
- [ ] Frontend tests ≥8 new

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Indicator math off vs TradingView | Reference test cases with known I/O. Wilder vs simple smoothing documented |
| lightweight-charts v4 Primitives API change | Pin version `^4.2.0`; lock in package.json |
| Drawing tools complex to implement | Start with simplest (horizontal line), iterate. Trendline + fib later if time tight |
| localStorage drawing data corruption | Schema versioning: `{ version: 1, drawings: [...] }` |
| Mobile UX (drawing on touchscreen unusable) | Already hidden on mobile. Add tablet detection later if needed |
| Bundle bloat | Code-split: drawing tools lazy-load on first activate |

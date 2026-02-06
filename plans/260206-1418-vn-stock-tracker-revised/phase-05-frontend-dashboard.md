# Phase 05: Frontend Dashboard

## Context Links
- [Plan Overview](./plan.md)
- [Phase 04: Backend WS + REST](./phase-04-backend-websocket-rest-api.md)
- [Old plan Phase 05](../260206-1341-stock-tracker-system/phase-05-frontend-core-ui.md)
- [Old plan Phase 06](../260206-1341-stock-tracker-system/phase-06-frontend-realtime-features.md)

## Overview
- **Priority:** P0
- **Status:** pending
- **Effort:** 6h
- Complete React dashboard: stock board (VN30), index bar, derivatives/basis panel, foreign investor panel, active buy/sell panel, alert feed, candlestick chart, WebSocket connection + state management.
- Merges old plan Phase 05 + Phase 06 into single phase.

## Key Changes from Old Plan
- **Index bar** in header (VN30, VNINDEX) - was missing
- **Derivatives panel** (VN30F price, basis, premium/discount) - was missing
- **Alert feed** panel - was missing
- **Foreign investor panel** enhanced with speed indicator
- **Default watchlist** = VN30 (30 stocks loaded from `/api/vn30-components`)
- **WS message types** extended: `index`, `derivatives`, `alert`

## Requirements

### Functional
- App shell with header (title, market status, index values)
- Stock board table: VN30 stocks, sortable, color-coded (VN conventions)
- Index bar: VN30 + VNINDEX with change/percent
- Derivatives panel: VN30F price, basis, premium/discount indicator
- Foreign investor panel: buy/sell/net per symbol + speed (vol/min)
- Active buy/sell panel: mua/ban proportion bars per symbol
- Alert feed: real-time alert stream with severity coloring
- Candlestick chart for selected symbol (click row → chart)
- WebSocket auto-connect + reconnect with exponential backoff
- Connection status indicator in footer

### Non-Functional
- Initial render <1s
- Table handles 30 rows without jank (VN30 only, no virtualization needed)
- Smooth real-time updates (no full re-render per tick)

## Dashboard Layout
```
┌─────────────────────────────────┬──────────────────────┐
│ Header: VN Stock Tracker        │ VN30: 1238 +1.03%    │
│ [Phien chieu] 14:23:45         │ VNINDEX: 1285 +0.8%  │
├─────────────────────────────────┼──────────────────────┤
│                                 │ Phai sinh            │
│   Stock Board (VN30 x 30)      │ VN30F2602: 1242.3    │
│   Ma | TC | Tran | San | Gia   │ Basis: +3.54 (P)     │
│   +/- | % | KL | Mua CD       ├──────────────────────┤
│   | Ban CD | NN Rong           │ Canh bao             │
│                                 │ [!] VCB: NN mua bat  │
│                                 │     thuong +50K/min   │
├─────────────────────────────────┤ [i] HPG: NN ban rong │
│  Candlestick Chart              ├──────────────────────┤
│  (selected symbol)              │ Mua/Ban Chu Dong     │
│  TradingView Lightweight Charts │ VNM ████ 60%/40%     │
│  Red=up, Green=down (VN)        │ FPT ██████ 70%/30%  │
│                                 ├──────────────────────┤
│                                 │ Khoi Ngoai (NN)      │
│                                 │ Ma  | Mua | Ban | Net│
│                                 │ VNM | 50K | 30K | +20│
│                                 │ Speed: 5K/min        │
├─────────────────────────────────┴──────────────────────┤
│ Footer: [●] Da ket noi | Phien chieu                   │
└────────────────────────────────────────────────────────┘
```

## Related Code Files

### Hooks
- `frontend/src/hooks/use-websocket.ts` - WS connection + reconnect
- `frontend/src/hooks/use-market-data.ts` - Reducer-based state from WS messages

### Components
- `frontend/src/App.tsx` - Dashboard layout
- `frontend/src/components/header.tsx` - App header + market status
- `frontend/src/components/index-bar.tsx` - **NEW**: VN30 + VNINDEX
- `frontend/src/components/stock-board.tsx` - Price table (sortable, filterable)
- `frontend/src/components/stock-board-row.tsx` - Individual stock row
- `frontend/src/components/stock-chart.tsx` - TradingView candlestick
- `frontend/src/components/derivatives-panel.tsx` - **NEW**: Futures + basis
- `frontend/src/components/foreign-investor-panel.tsx` - Enhanced with speed
- `frontend/src/components/active-buy-sell-panel.tsx` - Mua/Ban bars
- `frontend/src/components/alert-feed.tsx` - **NEW**: Alert stream
- `frontend/src/components/market-status.tsx` - Market phase indicator
- `frontend/src/components/connection-status.tsx` - WS status

### Utilities
- `frontend/src/types/index.ts` - All TypeScript types
- `frontend/src/utils/price-color.ts` - VN color conventions
- `frontend/src/utils/format.ts` - Number/price formatters

## Implementation Steps

### 1. TypeScript types (`types/index.ts`)
Extended from old plan with: `IndexData`, `BasisPoint`, `Alert`, `DerivativesData`.

```typescript
// WS message types
export type WSMessage =
  | { type: 'trade'; data: TradeUpdate }
  | { type: 'snapshot'; data: SnapshotData }
  | { type: 'foreign'; data: ForeignInvestorData }
  | { type: 'index'; data: IndexData }
  | { type: 'derivatives'; data: DerivativesData }
  | { type: 'alert'; data: Alert }
  | { type: 'ping' }
  | { type: 'error'; message: string };

export interface IndexData {
  indexId: string;
  value: number;
  priorValue: number;
  change: number;
  ratioChange: number;
  advances: number;
  declines: number;
}

export interface DerivativesData {
  futuresSymbol: string;
  futuresPrice: number;
  spotValue: number;
  basis: number;
  isPremium: boolean;
}

export interface Alert {
  symbol: string;
  alertType: string;
  message: string;
  severity: 'info' | 'high' | 'critical';
  timestamp: string;
}
```

### 2. useWebSocket hook with reconnect reconciliation
```typescript
// Extended from old plan with reconnect data reconciliation.
// On reconnect: fetch full snapshot from REST API before resuming stream updates.
// Show "Reconnecting..." status during the process.

type ConnectionStatus = 'connecting' | 'connected' | 'reconnecting' | 'disconnected';

function useWebSocket(url: string, symbols: string[]) {
  const [status, setStatus] = useState<ConnectionStatus>('connecting');
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempt = useRef(0);
  const onMessage = useRef<((msg: WSMessage) => void) | null>(null);

  const connect = useCallback(() => {
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = async () => {
      const wasReconnecting = reconnectAttempt.current > 0;
      reconnectAttempt.current = 0;

      if (wasReconnecting) {
        // RECONNECT RECONCILIATION: fetch fresh snapshot from REST API
        // before processing any new stream messages
        setStatus('reconnecting');
        try {
          const [statsRes, foreignRes, indicesRes, basisRes] = await Promise.all([
            fetch('/api/session-stats').then(r => r.json()),
            fetch('/api/foreign').then(r => r.json()),
            fetch('/api/indices').then(r => r.json()),
            fetch('/api/derivatives/basis').then(r => r.json()),
          ]);
          // Dispatch snapshot to reset state with current data
          onMessage.current?.({
            type: 'snapshot',
            data: { stats: statsRes, foreign: foreignRes,
                    indices: indicesRes, basis: basisRes },
          });
        } catch (err) {
          console.error('Reconnect snapshot fetch failed:', err);
          // Continue anyway — stream will fill in data
        }
      }

      setStatus('connected');
      // Re-subscribe to symbols
      ws.send(JSON.stringify({ action: 'subscribe', symbols }));
    };

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data) as WSMessage;
      onMessage.current?.(msg);
    };

    ws.onclose = () => {
      setStatus('disconnected');
      // Exponential backoff reconnect: 1s, 2s, 4s, max 30s
      const delay = Math.min(1000 * 2 ** reconnectAttempt.current, 30000);
      reconnectAttempt.current++;
      setTimeout(connect, delay);
    };

    ws.onerror = () => ws.close();
  }, [url, symbols]);

  useEffect(() => { connect(); return () => wsRef.current?.close(); }, [connect]);

  return { status, onMessage };
}
```

**Reconnect reconciliation key points:**
- On reconnect (not first connect), status transitions: `disconnected → reconnecting → connected`
- During `reconnecting`, fetch all current state from REST API (`/api/session-stats`, `/api/foreign`, `/api/indices`, `/api/derivatives/basis`)
- Dispatch as snapshot to reset stale state before resuming stream updates
- If REST fetch fails, continue anyway — stream will gradually fill in correct data
- "Reconnecting..." banner shown via `status === 'reconnecting'`

### 3. useMarketData hook
Reducer extended with `INDEX`, `DERIVATIVES`, `ALERT` actions.

```typescript
interface MarketState {
  quotes: Record<string, StockQuote>;
  stats: Record<string, SessionStats>;
  foreign: Record<string, ForeignInvestorData>;
  indices: Record<string, IndexData>;     // NEW
  derivatives: DerivativesData | null;     // NEW
  alerts: Alert[];                         // NEW (keep last 50)
}
```

### 4. Price color utility
Same as old plan (fuchsia=ceiling, cyan=floor, red=up, green=down, yellow=ref).

### 5. Index bar component (`components/index-bar.tsx`)
```tsx
// Shows VN30 and VNINDEX side by side in header
// Color: green if positive, red if negative
// Format: "VN30: 1,238.76 +12.6 (+1.03%)"
```

### 6. Derivatives panel (`components/derivatives-panel.tsx`)
```tsx
// Shows: VN30F2602 price, basis value, premium/discount indicator
// Color: basis > 0 (premium) = amber, basis < 0 (discount) = blue
```

### 7. Alert feed (`components/alert-feed.tsx`)
```tsx
// Scrollable list of recent alerts (max 50)
// Color by severity: critical=red, high=amber, info=blue
// Format: "[!] VCB: NN mua rong 100K co phieu" with timestamp
```

### 8. Enhanced foreign investor panel
Add speed column: "Toc do: 5K/phut"

### 9. Stock board, chart, active buy/sell, market status
Largely same as old plan but default watchlist from `/api/vn30-components`.

### 10. App.tsx wiring
```tsx
export default function App() {
  const [watchlist, setWatchlist] = useState<string[]>([]);
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const { quotes, stats, foreign, indices, derivatives, alerts, status } = useMarketData(watchlist);

  // Load VN30 on mount
  useEffect(() => {
    fetch('/api/vn30-components')
      .then(r => r.json())
      .then(symbols => setWatchlist(symbols));
  }, []);

  return (
    <div className="flex flex-col h-screen bg-gray-950 text-white">
      <Header indices={indices} />
      {/* Reconnecting banner - shown during WS reconnect reconciliation */}
      {status === 'reconnecting' && (
        <div className="bg-amber-600 text-white text-center py-1 text-sm animate-pulse">
          Dang ket noi lai... (Reconnecting...)
        </div>
      )}
      <div className="flex flex-1 overflow-hidden">
        <div className="flex-1 flex flex-col overflow-hidden">
          {selectedSymbol && <StockChart symbol={selectedSymbol} />}
          <StockBoard quotes={quotes} stats={stats} foreign={foreign}
            onSelectSymbol={setSelectedSymbol} />
        </div>
        <div className="w-72 flex flex-col border-l border-gray-700 overflow-y-auto">
          <DerivativesPanel data={derivatives} />
          <AlertFeed alerts={alerts} />
          <ActiveBuySellPanel stats={stats} symbols={watchlist} />
          <ForeignInvestorPanel foreign={foreign} symbols={watchlist} />
        </div>
      </div>
      <ConnectionStatus status={status} />
    </div>
  );
}
```

## Todo List
- [ ] Create TypeScript types (extended with Index, Derivatives, Alert)
- [ ] Create useWebSocket hook with reconnection + REST reconciliation on reconnect
- [ ] Create useMarketData hook with extended reducer
- [ ] Create "Reconnecting..." banner (shown during reconnect reconciliation)
- [ ] Create price-color and format utilities
- [ ] Create Header with MarketStatus component
- [ ] Create IndexBar component (VN30, VNINDEX)
- [ ] Create StockBoard with sortable columns
- [ ] Create StockBoardRow with VN color conventions
- [ ] Create StockChart (TradingView Lightweight Charts, red=up)
- [ ] Create DerivativesPanel (futures price, basis)
- [ ] Create AlertFeed (scrollable alert list)
- [ ] Create ActiveBuySellPanel (proportion bars)
- [ ] Create ForeignInvestorPanel (with speed column)
- [ ] Create ConnectionStatus
- [ ] Wire App.tsx with all components
- [ ] Load VN30 watchlist from /api/vn30-components on mount
- [ ] Test WS connection + snapshot delivery
- [ ] Test real-time updates render correctly

## Success Criteria
- Dashboard renders dark theme with all 7 panels
- VN30 stock board shows 30 rows with correct Vietnamese color coding
- Index bar shows VN30 + VNINDEX with live updates
- Derivatives panel shows VN30F price + basis
- Alert feed shows incoming alerts with severity colors
- Foreign panel shows buy/sell/net + speed per symbol
- Chart renders candlesticks (red=up, green=down VN convention)
- Auto-reconnect within 5s of disconnect

## Risk Assessment
- **Vite proxy WS upgrade:** Ensure `ws: true` in vite.config.ts proxy
- **TradingView Charts v5 API:** Verify candlestick series API matches code
- **High-frequency re-renders:** Use useRef for hot path, React.memo for rows

## Next Steps
- Phase 06: Analytics engine (server-side alerts, correlation, divergence)

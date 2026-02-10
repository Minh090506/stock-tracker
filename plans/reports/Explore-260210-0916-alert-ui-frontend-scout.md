# Frontend Alert UI Scout Report

**Date:** 2026-02-10 09:16  
**Scope:** Codebase analysis for implementing alerts page UI  
**Status:** Complete

---

## 1. Current Signals Page Structure

**File:** `/Users/minh/Projects/stock-tracker/frontend/src/pages/signals-page.tsx` (28 lines)

**Current Implementation:**
- Uses mock hook `useSignals()` (returns static MOCK_SIGNALS array)
- Displays signal feed with severity filtering
- Not yet connected to backend APIs or WebSocket

**Key Components Used:**
- `SignalFilterChips` (type/severity filter)
- `SignalFeedList` (card-based reverse chronological list)

**Import Pattern:**
```tsx
import type { SignalType, Signal } from "../types";
import { useSignals } from "../hooks/use-signals-mock";
```

---

## 2. WebSocket Hook Patterns

**File:** `/Users/minh/Projects/stock-tracker/frontend/src/hooks/use-websocket.ts` (202 lines)

**Public API:**
```typescript
export interface WebSocketResult<T> {
  data: T | null;
  status: ConnectionStatus; // "connecting" | "connected" | "disconnected"
  error: Error | null;
  isLive: boolean;
  reconnect: () => void;
}

export function useWebSocket<T>(
  channel: WebSocketChannel,
  options?: UseWebSocketOptions<T>
): WebSocketResult<T>
```

**Channel Types:**
- `"market"` — full MarketSnapshot
- `"foreign"` — ForeignSummary only
- `"index"` — IndexData only
- **`"alerts"` — real-time analytics alerts** ✓ EXISTS

**Key Features:**
- Auto-reconnect with exponential backoff (1s → 30s)
- REST polling fallback after 3 failed attempts
- Auth token via query param (`?token=`)
- Heartbeat ping/pong with configurable timeout
- Rate limiting on frontend lifecycle

**Example Usage Pattern** (from `use-price-board-data.ts`):
```typescript
const { data: snapshot, status, error, isLive, reconnect } =
  useWebSocket<MarketSnapshot>("market", {
    fallbackFetcher: () => apiFetch<MarketSnapshot>("/market/snapshot"),
    fallbackIntervalMs: 3000,
  });
```

---

## 3. UI Components — Available for Reuse

### Core UI Components

| Component | File | Exports | Purpose |
|-----------|------|---------|---------|
| **ErrorBoundary** | `ui/error-boundary.tsx` (59 lines) | Class component + handleRetry | Catches render errors with retry button |
| **ErrorBanner** | `ui/error-banner.tsx` (23 lines) | `ErrorBanner(message, onRetry?)` | Inline error message with optional retry |
| **PageLoadingSkeleton** | `ui/page-loading-skeleton.tsx` (17 lines) | `PageLoadingSkeleton()` | Generic animated skeleton matching standard page layout |
| **SignalsSkeleton** | `ui/signals-skeleton.tsx` (30 lines) | `SignalsSkeleton()` | Signals-specific skeleton (title + filters + 6 card placeholders) |

### Signal Components

| Component | File | Exports | Purpose |
|-----------|------|---------|---------|
| **SignalFilterChips** | `signals/signal-filter-chips.tsx` (44 lines) | `SignalFilterChips(active, onChange)` | Filter buttons for signal types |
| **SignalFeedList** | `signals/signal-feed-list.tsx` (76 lines) | `SignalFeedList(signals)` + `SignalCard(signal)` | Card list with severity color coding |

**Severity Color Mapping:**
```typescript
const SEVERITY_STYLES = {
  info: { bg: "bg-blue-900/50", text: "text-blue-300", border: "border-blue-700" },
  warning: { bg: "bg-yellow-900/50", text: "text-yellow-300", border: "border-yellow-700" },
  critical: { bg: "bg-red-900/50", text: "text-red-300", border: "border-red-700" },
}
```

**Signal Card Layout:**
```
[HH:MM:SS] [SEVERITY BADGE] [SYMBOL] [MESSAGE]
```

### Other Reusable Components

| Component | File | Usage |
|-----------|------|-------|
| **AppLayoutShell** | `layout/app-layout-shell.tsx` | Root layout (sidebar + Outlet) |
| **AppSidebarNavigation** | `layout/app-sidebar-navigation.tsx` | Responsive sidebar with nav items |

---

## 4. Type Definitions

**File:** `/Users/minh/Projects/stock-tracker/frontend/src/types/index.ts` (150 lines)

**Current Signal Types:**
```typescript
export type SignalType = "foreign" | "volume" | "divergence";
export type SignalSeverity = "info" | "warning" | "critical";

export interface Signal {
  id: string;
  type: SignalType;
  severity: SignalSeverity;
  symbol: string;
  message: string;
  value: number;
  timestamp: string;
}
```

**Need to Update to Backend Alert Types:**

Backend defines `AlertType`:
```python
class AlertType(str, Enum):
    FOREIGN_ACCELERATION = "foreign_acceleration"
    BASIS_DIVERGENCE = "basis_divergence"
    VOLUME_SPIKE = "volume_spike"
    PRICE_BREAKOUT = "price_breakout"

class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
```

**⚠️ Action:** Update frontend `SignalType` to match backend `AlertType` enum values.

---

## 5. API Client & Utilities

### API Client
**File:** `/Users/minh/Projects/stock-tracker/frontend/src/utils/api-client.ts` (10 lines)

```typescript
const BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";

export async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`);
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json() as Promise<T>;
}
```

### Polling Hook
**File:** `/Users/minh/Projects/stock-tracker/frontend/src/hooks/use-polling.ts` (47 lines)

```typescript
export function usePolling<T>(
  fetcher: () => Promise<T>,
  intervalMs: number = 5000,
): PollingResult<T> {
  // data, loading, error, refresh
}
```

---

## 6. Backend Alert Endpoints — Ready to Consume

### REST Endpoint (GET)
**File:** `/Users/minh/Projects/stock-tracker/backend/app/routers/market_router.py`

```python
@router.get("/alerts")
async def get_alerts(
    limit: int = Query(50, ge=1, le=200),
    type: AlertType | None = Query(None),
    severity: AlertSeverity | None = Query(None),
):
    """Recent analytics alerts, newest first."""
    from app.main import alert_service
    alerts = alert_service.get_recent_alerts(limit, type, severity)
    return [a.model_dump() for a in alerts]
```

**Endpoint:** `GET /api/market/alerts?limit=50&type=foreign_acceleration&severity=critical`

**Response:** List of Alert objects (JSON):
```json
[
  {
    "id": "abc12345",
    "alert_type": "foreign_acceleration",
    "severity": "critical",
    "symbol": "VNM",
    "message": "Foreign buy acceleration 3.2x above normal",
    "timestamp": "2026-02-10T09:15:30",
    "data": { "acceleration_ratio": 3.2 }
  }
]
```

### WebSocket Endpoint (Real-time)
**File:** `/Users/minh/Projects/stock-tracker/backend/app/websocket/router.py` (line 141-146)

```python
@router.websocket("/ws/alerts")
async def alerts_websocket(ws: WebSocket) -> None:
    """Alerts channel: real-time analytics alerts."""
    from app.main import alerts_ws_manager
    await _ws_lifecycle(ws, alerts_ws_manager)
```

**Channel:** `ws://localhost/ws/alerts?token=<WS_AUTH_TOKEN>`

**WS Message Format:** JSON alert object (same as REST response)

**Connection Features:**
- Auth token validation via query param
- Rate limiting (configurable per IP)
- Heartbeat ping every 30s (configurable)
- Auto-reconnect on disconnect (client-side via `useWebSocket` hook)

---

## 7. Backend Alert Models & Service

### Alert Models
**File:** `/Users/minh/Projects/stock-tracker/backend/app/analytics/alert_models.py` (39 lines)

```python
class AlertType(str, Enum):
    FOREIGN_ACCELERATION = "foreign_acceleration"
    BASIS_DIVERGENCE = "basis_divergence"
    VOLUME_SPIKE = "volume_spike"
    PRICE_BREAKOUT = "price_breakout"

class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

class Alert(BaseModel):
    id: str
    alert_type: AlertType
    severity: AlertSeverity
    symbol: str
    message: str
    timestamp: datetime
    data: dict[str, Any]
```

### Alert Service
**File:** `/Users/minh/Projects/stock-tracker/backend/app/analytics/alert_service.py` (104 lines)

**Key Features:**
- **Alert Buffer:** deque(maxlen=500) — keeps last 500 alerts
- **Deduplication:** 60s cooldown per (alert_type, symbol) pair
- **Subscribers:** Observer pattern for broadcasting new alerts
- **Daily Reset:** Clears buffer & cooldowns at 15:05 VN time

**Public API:**
```python
def register_alert(alert: Alert) -> bool: # Returns True if accepted (not deduped)
def get_recent_alerts(limit=50, type_filter=None, severity_filter=None) -> list[Alert]
def subscribe(callback: AlertSubscriber): # callback(alert: Alert) called on new alert
def unsubscribe(callback: AlertSubscriber)
def reset_daily()
```

### Backend Wiring
**File:** `/Users/minh/Projects/stock-tracker/backend/app/main.py` (lines 68-124)

Alert service already:
1. ✓ Instantiated: `alert_service = AlertService()` (line 36)
2. ✓ Subscribed to /ws/alerts broadcast: `alert_service.subscribe(_on_new_alert)` (line 124)
3. ✓ Connected to REST endpoint: `GET /api/market/alerts`
4. ✓ Wired to WS endpoint: `/ws/alerts`
5. ✓ Daily reset scheduled: 15:05 VN time (line 64)

---

## 8. Frontend Configuration

**Tailwind & Build:**
- **No tailwind.config.ts found** — using Tailwind v4 with @tailwindcss/vite (auto-config)
- Uses CSS variables + Tailwind v4 defaults for dark theme (bg-gray-950, etc.)

**Frontend Dependencies:**
```json
{
  "react": "^19.0.0",
  "react-dom": "^19.0.0",
  "react-router-dom": "^7.13.0",
  "recharts": "^3.7.0",
  "lightweight-charts": "^4.2.0"
}
```

**No external UI component library** — all components built from scratch with Tailwind.

---

## 9. App Routing & Navigation

**Router Structure** (`App.tsx`):
```
/ (redirect to /price-board)
├─ /price-board
├─ /foreign-flow
├─ /volume
├─ /derivatives
└─ /signals ← Already routed, currently showing mock data
```

**Sidebar Navigation** (`app-sidebar-navigation.tsx`, line 11-17):
```typescript
const NAV_ITEMS = [
  { to: "/price-board", label: "Price Board" },
  { to: "/foreign-flow", label: "Foreign Flow" },
  { to: "/volume", label: "Volume Analysis" },
  { to: "/derivatives", label: "Derivatives" },
  { to: "/signals", label: "Signals" },
];
```

**⚠️ Note:** Signals page already exists and is routed. Can rename to "Alerts" and update page accordingly.

---

## 10. Styling System

**Design System:**
- **Color Palette:** Dark theme (bg-gray-950 primary, bg-gray-900 surfaces, gray-800 borders)
- **Red Accent:** Hover states, critical badges (#dc2626 range)
- **Severity Colors:** Blue (info), Yellow (warning), Red (critical)
- **Spacing:** Tailwind default (p-6, space-y-6, gap-4)
- **Animations:** `animate-pulse` for skeletons, `transition-colors` for buttons
- **Cards:** Border gray-800, rounded-lg, bg-gray-900 background

**Existing Responsive Patterns:**
- `md:hidden` for mobile-only hamburger
- `fixed md:static` for sidebar
- `grid grid-cols-1 lg:grid-cols-3` for desktop layouts
- `max-h-[calc(100vh-200px)] overflow-y-auto` for scrollable lists

---

## Summary: Ready for Implementation

### ✅ What Already Exists

1. **Mock Signals Page** → `/pages/signals-page.tsx` (can be renamed to alerts-page.tsx)
2. **Signal Components** → `SignalFilterChips`, `SignalFeedList`, `SignalCard`
3. **WebSocket Hook** → `useWebSocket("alerts", ...)` with auto-reconnect
4. **REST Endpoint** → `GET /api/market/alerts?limit=&type=&severity=`
5. **WS Endpoint** → `ws://localhost/ws/alerts`
6. **Backend Alert Service** → Fully implemented, deduped, subscribed to WS broadcast
7. **UI Patterns** → ErrorBoundary, ErrorBanner, Skeletons, Color system
8. **Routing & Navigation** → Already in place, just needs UI update
9. **Polishing Hooks** → `usePolling`, `useWebSocket` with fallback patterns

### 📋 Required Implementation Steps

1. **Update Frontend Types** — Rename `SignalType` to match backend `AlertType` enum
2. **Create `use-alerts-data.ts` Hook** — Combines WS (real-time) + REST (recent on page load)
3. **Update `signals-page.tsx`** → Replace mock with real hook, add filter UI
4. **Add Alert Detail Panel** (optional) — Click alert → show expanded data payload
5. **Add Connection Status Indicator** — Show if WS live or falling back to polling
6. **Update Navigation Label** — "Signals" → "Alerts" (or keep as is)
7. **Test E2E** — Verify WS broadcasts, REST fallback, dedup behavior

### 🎨 Design Notes for Alert UI

- **Layout:** Title + Filter Chips + Alert Feed (match current signals-page structure)
- **Card Layout:** Compact horizontal: [Time] [Severity Badge] [Symbol] [Message]
- **Scrollable List:** `max-h-[calc(100vh-200px)] overflow-y-auto`
- **Empty State:** "No alerts yet. Monitoring market..."
- **Loading:** Use `SignalsSkeleton` for skeleton screen
- **Error Handling:** ErrorBoundary + ErrorBanner with reconnect button

### 📝 Unresolved Questions

1. Should alert page have expandable detail rows showing `data` payload?
2. Should alerts auto-scroll to top (newest first) or sticky at bottom?
3. Should UI auto-clear old alerts after N hours, or keep in buffer until reset?
4. Any alert acknowledgment/dismissal feature needed, or just display?

---

**Report Generated:** 2026-02-10 09:16  
**Scout:** Frontend Codebase Explorer

# Phase 6: Signals Page

## Context

- Route: `/signals`
- No analytics engine yet (Phase 6 of roadmap)
- Use mock signal data initially; wire to real backend when analytics engine lands
- Signal types: foreign (acceleration spikes), volume (buy/sell ratio extremes), divergence (basis)

## Overview

- **Priority**: P2 (depends on Phase 6 analytics engine for real data)
- **Status**: pending
- **Effort**: 45m

## Page Layout

```
┌──────────────────────────────────────────────────────┐
│  Signals   [Auto-refresh: ON]                        │
├──────────────────────────────────────────────────────┤
│  Filter Chips: [All] [Foreign] [Volume] [Divergence] │
├──────────────────────────────────────────────────────┤
│  Signal Feed (reverse chronological)                 │
│  ┌────────────────────────────────────────────────┐  │
│  │ 14:32:15  CRITICAL  VNM  Foreign buy accel 3x │  │
│  │ 14:30:02  WARNING   HPG  Buy ratio >70%       │  │
│  │ 14:28:45  INFO      VN30F Basis premium >1%   │  │
│  │ ...                                            │  │
│  └────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
```

## Components

### Page: `frontend/src/pages/signals-page.tsx` (~55 lines)

```tsx
export function SignalsPage() {
  const [activeFilter, setActiveFilter] = useState<SignalType | "all">("all");
  const { signals } = useSignals();  // mock for now

  const filtered = activeFilter === "all"
    ? signals
    : signals.filter(s => s.type === activeFilter);

  return (
    <div className="space-y-6 p-6">
      <SignalFilterChips active={activeFilter} onChange={setActiveFilter} />
      <SignalFeed signals={filtered} />
    </div>
  );
}
```

### `frontend/src/components/signals/signal-filter-chips.tsx` (~35 lines)

Row of clickable chips: All | Foreign | Volume | Divergence.
Active chip has solid background, others outlined.

### `frontend/src/components/signals/signal-feed.tsx` (~60 lines)

Scrollable list of signal cards:
- Each card shows: timestamp | severity badge | symbol | message
- Severity colors: info=blue, warning=yellow, critical=red
- Reverse chronological order (newest first)
- Empty state: "No signals yet. Monitoring market..."

### `frontend/src/hooks/use-signals.ts` (~40 lines)

Mock hook that generates sample signals. Structure:

```typescript
export function useSignals() {
  // Return static mock data for now
  // When analytics engine (Phase 6) is ready:
  //   -> poll GET /api/signals or subscribe via WebSocket
  const signals: Signal[] = [
    {
      id: "1",
      type: "foreign",
      severity: "critical",
      symbol: "VNM",
      message: "Foreign buy acceleration 3.2x above normal",
      value: 3.2,
      timestamp: new Date().toISOString(),
    },
    // ... more mock signals
  ];
  return { signals };
}
```

## Files Summary

| Action | File | Lines |
|--------|------|-------|
| Rewrite | `frontend/src/pages/signals-page.tsx` | ~55 |
| Create | `frontend/src/components/signals/signal-filter-chips.tsx` | ~35 |
| Create | `frontend/src/components/signals/signal-feed.tsx` | ~60 |
| Create | `frontend/src/hooks/use-signals.ts` | ~40 |

## Todo

- [ ] Create mock `use-signals.ts` hook with sample data
- [ ] Build filter chips component
- [ ] Build signal feed (scrollable card list)
- [ ] Compose in `signals-page.tsx`
- [ ] Verify `npm run build` compiles

## Success Criteria

- Filter chips toggle between All/Foreign/Volume/Divergence
- Signal feed renders mock signals in reverse chronological order
- Severity badges use correct colors (info=blue, warning=yellow, critical=red)
- Empty state message when no signals match filter
- All components <200 lines

## Future Integration (when Phase 6 analytics engine lands)

1. Replace mock data in `use-signals.ts` with `usePolling(() => apiFetch('/api/signals'), 5000)`
2. Add backend endpoint `GET /api/signals` returning `Signal[]`
3. Later: switch to WebSocket push for real-time signal delivery

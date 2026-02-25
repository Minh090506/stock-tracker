# Code Review: Phase 4 — Velocity Dashboard Frontend

**Date:** 2026-02-24
**Reviewer:** code-reviewer agent
**Build:** PASS (tsc 0 errors, vite build clean)

---

## Scope

- Files reviewed: 9 (6 new, 3 modified)
- Lines analyzed: ~400
- Review focus: Phase 4 new velocity dashboard components

| File | Type |
|---|---|
| `frontend/src/hooks/use-velocity-data.ts` | New |
| `frontend/src/components/velocity/velocity-summary-cards.tsx` | New |
| `frontend/src/components/velocity/velocity-price-overlay-chart.tsx` | New |
| `frontend/src/components/velocity/velocity-imbalance-gauge.tsx` | New |
| `frontend/src/components/ui/velocity-skeleton.tsx` | New |
| `frontend/src/pages/velocity-page.tsx` | New |
| `frontend/src/types/index.ts` | Modified |
| `frontend/src/App.tsx` | Modified |
| `frontend/src/components/layout/app-sidebar-navigation.tsx` | Modified |

---

## Overall Assessment

Solid implementation. Pattern consistency with derivatives page is excellent — identical hook structure, identical page composition pattern, identical error/loading flow. Build is clean, 0 TS errors. Two medium issues found: an unused prop and an `as any` cast that can be removed.

---

## Critical Issues

None.

---

## High Priority Findings

None.

---

## Medium Priority Improvements

### 1. Unused `velocity` prop in `VelocityPriceOverlayChart`

**File:** `frontend/src/components/velocity/velocity-price-overlay-chart.tsx` line 32

The component signature accepts `velocity: VelocitySnapshot | null` but the body only uses `history`. The prop is destructured but not read.

```tsx
// Current — velocity is declared but never used
export function VelocityPriceOverlayChart({ history }: VelocityPriceOverlayChartProps) {
```

The interface also declares it:
```tsx
interface VelocityPriceOverlayChartProps {
  velocity: VelocitySnapshot | null;  // unused
  history: VelocityHistoryPoint[];
}
```

This was likely intended for a future "current price" overlay line on the chart (the component is named "price overlay"). Two options:

**Option A** — Remove it now (YAGNI): drop `velocity` from interface and call site in `velocity-page.tsx`.

**Option B** — Use it: add the current price as a reference line or annotation on the chart if that was the intent.

Currently the chart renders `netVelocity`, `buyVol`, `sellVol` — no price. The name `VelocityPriceOverlayChart` implies a price line should be there. Recommend either rename to `VelocityHistoryChart` or add the price line.

### 2. `as any` cast on Tooltip `formatter`

**File:** `frontend/src/components/velocity/velocity-price-overlay-chart.tsx` lines 85–94

```tsx
formatter={((value: number, name: string) => {
  // ...
  return [formatted, label];
}) as any}
```

Recharts `formatter` type accepts `(value, name, props) => ReactNode | [ReactNode, ReactNode]`. The cast is used because Recharts types are loose. This is acceptable but can be improved:

```tsx
import type { Formatter } from "recharts/types/component/DefaultTooltipContent";

formatter={((value: number, name: string): [string, string] => {
  // ...
}) as Formatter<number, string>}
```

Or simply suppress with `// eslint-disable-next-line @typescript-eslint/no-explicit-any` on the one line (which is already done above). The existing eslint comment approach is fine — low priority.

---

## Low Priority Suggestions

### 3. `ChartRow` interface exported from module but not reused

**File:** `frontend/src/components/velocity/velocity-price-overlay-chart.tsx` lines 25–30

`ChartRow` is a local-only interface used for `chartData`. Not exported and not needed elsewhere. Fine as-is; just noting it's internal scaffolding.

### 4. Loading logic in `useVelocityData` — edge case

**File:** `frontend/src/hooks/use-velocity-data.ts` line 34

```ts
loading: !ws.data && !history.data && history.loading,
```

Identical pattern to `useDerivativesData`. Behavior: loading is `false` once either WS or history data arrives. This means if WS connects instantly (within first poll cycle), the page renders with an empty `history` array and shows "No velocity history available yet" in the chart — which is correct UX. No bug, but worth noting the deliberate early-exit from loading state.

### 5. `VelocityImbalanceGauge` — mixed language labels

**File:** `frontend/src/components/velocity/velocity-imbalance-gauge.tsx` lines 14, 22–23

Labels use Vietnamese ("Mua", "Bán") in the gauge but English ("Strong Buy", "Neutral", "Strong Sell") in the footer labels. Inconsistent. Other pages (derivatives, foreign flow) use full English. Recommend either all Vietnamese or all English for consistency. The derivatives page uses all English.

---

## Positive Observations

- **Exact pattern mirroring** of `useDerivativesData` / `DerivativesPage` — same hook structure, same loading/error guards, same page layout, same Suspense fallback wiring in `App.tsx`.
- **Type safety**: `VelocityData`, `CorrelationData`, `VelocitySnapshot`, `VelocityHistoryPoint` are clean, nullable fields use `| null`, no `any` in types file.
- **VN color convention** correctly applied: red=buy, green=sell throughout cards and gauge.
- **`VelocitySummaryCards`** gracefully handles `null` correlation (shows "N/A" / "Collecting...") and null `vn30f`.
- **Skeleton** matches actual layout precisely (5 cards, chart h-80, gauge h-6).
- **Lazy loading** correctly applied with `VelocitySkeleton` as Suspense fallback.
- **ErrorBoundary** wrapping on route is consistent with all other routes.
- **`formatVolume`** reused from existing utility — no duplication.
- **History URL** hardcodes `symbol=VN30F` which is correct per current scope.

---

## Recommended Actions

1. **[Medium]** Either remove `velocity` prop from `VelocityPriceOverlayChartProps` + call site, or implement the price overlay line it implies. The name "price overlay" is misleading if the price is never shown.

2. **[Low]** Unify gauge labels to all-English: replace `"Mua"` → `"Buy"`, `"Bán"` → `"Sell"` to match rest of app.

3. **[Low]** The `as any` tooltip formatter cast is acceptable but could be typed as `Formatter<number, string>` from recharts if desired.

---

## Metrics

- TypeScript errors: 0
- Build: PASS (vite, 971ms)
- Linting: no lint script configured (no ESLint setup in project)
- Test coverage: N/A (no tests for frontend components)
- File sizes: all new files well under 200-line limit (largest: 114 lines)

---

## Unresolved Questions

- Was the `velocity` prop in `VelocityPriceOverlayChart` intentionally kept for a future "current price" overlay line, or is it leftover from an earlier design? This determines whether to remove or implement it.
- Is mixed Vietnamese/English labeling intentional for the Vietnamese market audience, or an oversight?

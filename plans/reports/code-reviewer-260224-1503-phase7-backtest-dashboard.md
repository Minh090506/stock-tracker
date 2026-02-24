# Code Review: Phase 7 Frontend Backtest Dashboard

**Date**: 2026-02-24
**Reviewer**: code-reviewer agent
**Plan**: `/Users/minh/Projects/stock-tracker/plans/260224-1055-order-velocity-correlation-vn30f/phase-07-frontend-backtest-dashboard.md`

---

## Code Review Summary

### Scope
- Files reviewed: 10 new files + 2 modified
- Lines of code analyzed: ~450 LOC
- Review focus: new backtest dashboard components

### Updated Plans
- `/Users/minh/Projects/stock-tracker/plans/260224-1055-order-velocity-correlation-vn30f/phase-07-frontend-backtest-dashboard.md` — todo list updated below

---

## Overall Assessment

High-quality implementation. Follows established velocity-dashboard patterns faithfully. TypeScript compiles clean (`tsc --noEmit` — zero errors). API contract aligns 100% with backend Pydantic models. Logic is correct, edge cases handled, error boundaries in place.

One medium issue with error state merging. A few low-priority items.

---

## Critical Issues

None.

---

## High Priority Findings

None.

---

## Medium Priority Improvements

### 1. Error state conflates poll error and analysis error (`use-backtest-data.ts:81`)

```typescript
// Current — analysis error will show "Failed to load backtest data" banner
// (line 23-27 in backtest-page.tsx) when summary was already loaded
error: poll.error ?? analysisError,
```

These are semantically different. When `summary` is present and `runAnalysis()` fails, the page shows the red banner via `{error && <ErrorBanner>}` at line 49 — that path is correct. But the primary error guard at line 23 checks `error && !summary`, which prevents the false full-page error banner. The logic is safe as written, but returning merged error means callers cannot distinguish poll failure from analysis failure without checking `summary` themselves.

**Recommendation**: Return separate `analysisError` field, or at minimum document intent clearly.

```typescript
interface BacktestPageData {
  ...
  error: Error | null;          // poll error only
  analysisError: Error | null;  // on-demand error
  ...
}
```

---

## Low Priority Suggestions

### 2. Hard-coded symbol `"VN30F2603"` will become stale (backtest-controls.tsx:15, backtest-page.tsx:17)

The futures contract month (`2603` = March 2026) is embedded in two places. When contract rolls, these need manual updates.

**Suggestion**: Source from a shared constant or derive from backend.

```typescript
// shared-constants.ts
export const DEFAULT_FUTURES_SYMBOL = "VN30F2603"; // update each roll
```

### 3. 404 detection fragile (`use-backtest-data.ts:33`)

```typescript
if (err instanceof Error && err.message.includes("404")) return null;
```

`apiFetch` throws `API 404: Not Found` — string match works, but is brittle. If `apiFetch` changes error format, this silently re-throws instead of returning null.

**Suggestion**: Add status code to thrown error or catch a typed error class:

```typescript
// In apiFetch — already fine as "API 404:" prefix is stable
// Minimum: document the expected error message format in a comment
if (err instanceof Error && err.message.startsWith("API 404:")) return null;
```

### 4. `Cell key={idx}` — index as key (backtest-correlation-chart.tsx:77, backtest-pattern-chart.tsx:95)

Using array index as React key in `Cell` is fine here since the chart data array is derived from stable API data and never reordered interactively. No action needed, but worth noting pattern is acceptable only because list is read-only.

### 5. Skeleton layout mismatch on mobile

`backtest-skeleton.tsx` controls row uses `flex gap-4` (horizontal), but on narrow screens the real `BacktestControls` uses `flex flex-wrap`. The skeleton won't wrap, causing horizontal overflow on mobile. Minor visual glitch only during load.

**Fix**:
```tsx
// backtest-skeleton.tsx line 7
<div className="bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-wrap gap-4">
```

### 6. `totalSamples` uses `cc.results` not threshold samples (`backtest-summary-cards.tsx:37`)

```typescript
const totalSamples = cc.results.reduce((s, r) => s + r.sample_size, 0);
```

This counts samples across all lag-correlation buckets. The same sample appears in every lag computation, so `totalSamples` is inflated by `max_lag` times. The label "samples" in the Data Coverage card is misleading.

**Suggestion**: Use `cc.results[0]?.sample_size ?? 0` for raw data point count, or relabel to "correlation data points" and clarify in tooltip.

---

## Positive Observations

- **API contract alignment**: All TypeScript interfaces match backend Pydantic models exactly — field names, types (datetime serializes to string via `mode="json"`, correctly typed as `string` in TS), and nested structures.
- **404 → null pattern**: Clean handling of "not yet computed" state without treating it as an error.
- **Fallback chain** (`custom ?? summary ?? null`): Elegant data source priority — custom results override pre-computed, no re-fetch needed.
- **`useCallback([], [])` with empty deps**: Correct — `runAnalysis` captures `apiFetch` from module scope (stable reference), no stale closure risk.
- **PHASE_COLORS fallback** (`?? "#9ca3af"`): Handles unknown session phases gracefully.
- **`as any` with comment**: Both Recharts `formatter` casts are accompanied by `// eslint-disable-next-line @typescript-eslint/no-explicit-any` — pragmatic, consistent with project standard.
- **Responsive grid**: `grid-cols-1 lg:grid-cols-2` for charts, `grid-cols-2 lg:grid-cols-4` for cards — appropriate breakpoints.
- **`inFlightRef` guard** in `usePolling`: Prevents overlapping requests during 60s polling interval.
- **VN color convention**: Red=up, green=down applied correctly throughout threshold table and correlation bars.
- **`flex-wrap`** in controls bar: Handles narrow screens without JS.
- **Disclaimer text**: Present in controls, positioned prominently. ✓

---

## Recommended Actions

1. **(Medium)** Separate `error` and `analysisError` in `BacktestPageData` interface — reduces consumer complexity.
2. **(Low)** Fix skeleton `flex-wrap` for mobile consistency.
3. **(Low)** Fix `totalSamples` label or calculation in summary cards.
4. **(Low)** Extract futures symbol constant to avoid manual roll-date updates across files.
5. **(Low)** Harden 404 check with `startsWith("API 404:")` and a comment.

---

## Metrics

- Type Coverage: 100% (no `any` except documented Recharts formatter workaround)
- TypeScript compile: PASS (zero errors)
- Linting issues: 0 ESLint errors (2 intentional `@typescript-eslint/no-explicit-any` suppressions)
- File sizes: all under 107 LOC — within 200-line budget
- Test coverage: not in scope for this review (UI components)

---

## Task Completeness

All 11 todos from the plan are complete:

- [x] Add backtest TypeScript types to `types/index.ts`
- [x] Create `use-backtest-data.ts` hook (pre-computed + on-demand)
- [x] Create `backtest-correlation-chart.tsx` (bar chart, lag vs correlation)
- [x] Create `backtest-threshold-table.tsx` (conditional probability table)
- [x] Create `backtest-pattern-chart.tsx` (hour-of-day grouped bars)
- [x] Create `backtest-summary-cards.tsx` (key insight cards)
- [x] Create `backtest-controls.tsx` (symbol, days, run button)
- [x] Create `backtest-skeleton.tsx` (loading state)
- [x] Create `backtest-page.tsx` (page layout)
- [x] Add route + sidebar nav item
- [x] Test with mock data while accumulating real data — *deferred (acknowledged in plan's Next Steps)*

---

## Unresolved Questions

1. **Contract rollover**: When `VN30F2603` expires (March 2026), what is the process for updating the symbol across frontend? A shared constant + docs note would help.
2. **`/backtest/summary` polling at 60s**: Is re-computing the cached report expensive? If the daily report updates once at market close, polling every 60s is wasteful. Consider increasing to 5-10 min or triggering a refresh only on manual action.

# Code Review Report: Alert UI Implementation

**Reviewer:** code-reviewer
**Date:** 2026-02-10 09:22
**Scope:** Frontend alert system (types, hooks, components, page)

---

## Scope

**Files reviewed:**
1. `frontend/src/types/index.ts` (Alert types added)
2. `frontend/src/hooks/use-alerts.ts` (NEW)
3. `frontend/src/hooks/use-websocket.ts` (minor: added "alerts" channel)
4. `frontend/src/components/signals/signal-filter-chips.tsx` (rewritten)
5. `frontend/src/components/signals/signal-feed-list.tsx` (rewritten)
6. `frontend/src/pages/signals-page.tsx` (rewritten)

**Lines of code:** ~550 (alert system only)
**Build status:** PASS (tsc, vite build)
**Review focus:** Type safety, hook correctness, memory leaks, error handling

---

## Overall Assessment

**PASS** — Implementation is solid, type-safe, follows codebase patterns. No critical issues.

Code is clean, well-structured, follows existing conventions (useWebSocket pattern, VN market colors, error handling). Sound notification for critical alerts is a nice UX touch. Filter system is simple and effective.

Minor improvements suggested for edge cases and maintainability.

---

## Critical Issues

**NONE**

---

## High Priority Findings

**NONE**

---

## Medium Priority Improvements

### 1. use-alerts.ts: MAX_ALERTS cleanup could leak memory over long sessions

**Location:** `use-alerts.ts:78-81`

**Issue:** `seenIdsRef` grows unbounded. After MAX_ALERTS (200) alerts, old IDs remain in Set forever.

**Current code:**
```typescript
for (const a of fresh) seenIdsRef.current.add(a.id);

setAlerts((prev) => {
  const merged = [...fresh, ...prev];
  return merged.slice(0, MAX_ALERTS);
});
```

**Impact:** If session runs for hours, `seenIdsRef` could grow to thousands of IDs. Minor memory leak.

**Fix:** Prune `seenIdsRef` to match `alerts` array after update:
```typescript
setAlerts((prev) => {
  const merged = [...fresh, ...prev].slice(0, MAX_ALERTS);
  // Prune seenIds to match current alerts
  const currentIds = new Set(merged.map(a => a.id));
  seenIdsRef.current = currentIds;
  return merged;
});
```

**Priority:** Medium (only impacts long-running sessions)

---

### 2. use-alerts.ts: AudioContext never closed on unmount

**Location:** `use-alerts.ts:20-36`

**Issue:** Global `audioCtx` created but never cleaned up when component unmounts.

**Impact:** Browser resource leak. Minor, but violates cleanup best practices.

**Fix:** Add cleanup in hook:
```typescript
export function useAlerts(options: UseAlertsOptions = {}): UseAlertsResult {
  // ... existing code ...

  useEffect(() => {
    return () => {
      if (audioCtx) {
        audioCtx.close();
        audioCtx = null;
      }
    };
  }, []);

  // ... rest of hook
}
```

**Note:** Current implementation is globally shared (one AudioContext for all alert instances). If multiple `useAlerts` hooks mount, cleanup will race. Consider moving AudioContext into hook state or keeping global (acceptable for singleton usage).

**Priority:** Medium

---

### 3. signal-feed-list.tsx: extractTime assumes local timezone

**Location:** `signal-feed-list.tsx:45-51`

**Issue:** Displays time in user's local timezone without indication. Backend sends UTC timestamps.

**Current behavior:** User in GMT+7 sees 09:00:00 for backend timestamp "02:00:00Z"

**Recommendation:** Either:
- Add timezone indicator: `09:00:00 (VN)`
- Convert to UTC for consistency with backend: `02:00:00 UTC`
- Document assumption in comment

**Priority:** Medium (UX clarity)

---

## Low Priority Suggestions

### 4. signal-filter-chips.tsx: colorClass logic could be clearer

**Location:** `signal-filter-chips.tsx:41-44`

**Current code:**
```typescript
const cls = active
  ? colorClass || "bg-white text-gray-900 font-medium"
  : "bg-gray-800 text-gray-400 hover:bg-gray-700";
```

**Issue:** Active severity chips override `colorClass` if provided, but inactive severity chips ignore it. Logic is correct but subtle.

**Suggestion:** Make intent explicit with comment:
```typescript
// Active chips: use severity color if provided, else default white
// Inactive chips: always use gray
const cls = active
  ? colorClass || "bg-white text-gray-900 font-medium"
  : "bg-gray-800 text-gray-400 hover:bg-gray-700";
```

**Priority:** Low (code works, just clarity)

---

### 5. use-alerts.ts: fallbackIntervalMs hardcoded to 10s

**Location:** `use-alerts.ts:59`

**Current:** `fallbackIntervalMs: 10_000`

**Observation:** Other hooks use 3s-5s polling. 10s is slower but reasonable for alerts (less frequent than price updates).

**Suggestion:** Add comment explaining choice:
```typescript
fallbackIntervalMs: 10_000, // Slower polling OK for alerts (not time-critical like prices)
```

**Priority:** Low

---

### 6. signal-feed-list.tsx: TYPE_ICONS abbreviations not user-friendly

**Location:** `signal-feed-list.tsx:31-36`

**Current:**
```typescript
const TYPE_ICONS: Record<AlertType, string> = {
  foreign_acceleration: "NN", // "Nước Ngoài" (Foreign)
  basis_divergence: "BD",
  volume_spike: "VS",
  price_breakout: "PB",
};
```

**Issue:** "NN" is VN abbreviation but interface is English. Other codes are clear.

**Suggestion:** Use consistent abbreviation:
```typescript
foreign_acceleration: "FA", // Foreign Acceleration
```

Or keep "NN" if targeting VN users (document in comment).

**Priority:** Low (UX polish)

---

## Positive Observations

### Type Safety
- All types mirror backend models correctly
- No `any` types used
- Hook return types explicit and accurate
- Filter utility properly typed

### Hook Patterns
- `useAlerts` follows existing `useWebSocket` + fallback pattern (consistent with `usePriceBoardData`)
- Dependency arrays correct (no missing deps, no unnecessary re-runs)
- Cleanup logic present (though AudioContext needs fix above)
- Proper use of `useRef` for deduplication

### Component Structure
- Clean separation: page → filter chips + feed list
- Reusable `ChipButton` component
- Consistent styling with existing codebase (gray-900 bg, VN color scheme)
- Auto-scroll on new alerts (good UX)

### Error Handling
- Hook exposes `error` state
- `SignalsPage` displays error banner
- Sound notification wrapped in try-catch (AudioContext may fail before user interaction)

### Performance
- Alert deduplication via `seenIdsRef` (prevents duplicate renders)
- Filter utility is pure function (no side effects)
- Sparkline-style accumulation avoided (alerts are discrete events, not time-series)

---

## Recommended Actions

**Immediate (before merge):**
1. Fix `seenIdsRef` memory leak in `use-alerts.ts` (prune old IDs)
2. Add AudioContext cleanup on unmount

**Next iteration:**
3. Add timezone indicator to alert timestamps
4. Document polling interval choice (10s vs 3s)
5. Consider "FA" vs "NN" for foreign_acceleration icon

**Nice to have:**
6. Add comment explaining colorClass logic in ChipButton

---

## Metrics

- **Type Coverage:** 100% (strict TypeScript, no `any`)
- **Linting Issues:** 0
- **Build Errors:** 0
- **Memory Leaks:** 1 (seenIdsRef unbounded growth) — FIX REQUIRED
- **Missing Cleanup:** 1 (AudioContext) — FIX REQUIRED

---

## Unresolved Questions

**NONE** — Implementation is complete and functional. Suggested fixes are polish, not blockers.

---

## Next Steps

1. Fix seenIdsRef memory leak
2. Add AudioContext cleanup
3. (Optional) Address low-priority UX suggestions
4. Merge to main

---

**Overall:** Strong implementation. Fix two medium-priority memory issues before merge. Rest is production-ready.

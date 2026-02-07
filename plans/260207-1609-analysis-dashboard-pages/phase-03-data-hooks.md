# Phase 3: Data Fetching Hooks + API Client

## Context

- Backend endpoints from Phase 1: `/api/market/snapshot`, `/foreign-detail`, `/volume-stats`
- No WebSocket yet -- REST polling with configurable interval
- Vite proxy already configured: `/api` -> `http://localhost:8000`

## Overview

- **Priority**: P1
- **Status**: pending
- **Effort**: 45m

## Requirements

1. Generic `usePolling<T>` hook -- fetches URL at interval, returns `{ data, loading, error }`
2. `useMarketSnapshot()` -- polls `/api/market/snapshot` every 5s
3. `useForeignFlow()` -- polls `/api/market/foreign-detail` every 5s
4. `useVolumeAnalysis()` -- derives from `useMarketSnapshot()` quotes
5. API client module with fetch wrapper + error handling

## Files to Create

### `frontend/src/utils/api-client.ts` (~30 lines)

```typescript
const BASE_URL = "/api";

export async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`);
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json() as Promise<T>;
}
```

### `frontend/src/hooks/use-polling.ts` (~40 lines)

```typescript
import { useState, useEffect, useCallback, useRef } from "react";

export function usePolling<T>(
  fetcher: () => Promise<T>,
  intervalMs: number = 5000
): { data: T | null; loading: boolean; error: Error | null; refresh: () => void } {
  // useState for data/loading/error
  // useEffect with setInterval
  // cleanup on unmount
  // useRef for fetcher to avoid stale closures
  // Skip fetch if previous still in-flight (prevent pile-up)
}
```

Key behavior:
- First fetch immediately on mount
- Subsequent fetches every `intervalMs`
- If fetch takes longer than interval, skip next tick (no pile-up)
- `refresh()` forces immediate re-fetch
- Returns `loading: true` only on initial load (not subsequent polls)

### `frontend/src/hooks/use-market-snapshot.ts` (~15 lines)

```typescript
import { usePolling } from "./use-polling";
import { apiFetch } from "../utils/api-client";
import type { MarketSnapshot } from "../types";

export function useMarketSnapshot(intervalMs = 5000) {
  return usePolling(
    () => apiFetch<MarketSnapshot>("/market/snapshot"),
    intervalMs
  );
}
```

### `frontend/src/hooks/use-foreign-flow.ts` (~15 lines)

```typescript
import { usePolling } from "./use-polling";
import { apiFetch } from "../utils/api-client";
import type { ForeignDetailResponse } from "../types";

export function useForeignFlow(intervalMs = 5000) {
  return usePolling(
    () => apiFetch<ForeignDetailResponse>("/market/foreign-detail"),
    intervalMs
  );
}
```

## Files Summary

| Action | File | Lines |
|--------|------|-------|
| Create | `frontend/src/utils/api-client.ts` | ~30 |
| Create | `frontend/src/hooks/use-polling.ts` | ~40 |
| Create | `frontend/src/hooks/use-market-snapshot.ts` | ~15 |
| Create | `frontend/src/hooks/use-foreign-flow.ts` | ~15 |

## Todo

- [ ] Create `api-client.ts` with `apiFetch` wrapper
- [ ] Create `use-polling.ts` generic hook
- [ ] Create `use-market-snapshot.ts`
- [ ] Create `use-foreign-flow.ts`
- [ ] Verify `npm run build` compiles

## Success Criteria

- `usePolling` fetches on mount, then at interval
- No fetch pile-up when server is slow
- `loading` is true only on first load
- Hooks compile with correct TypeScript generics
- `npm run build` succeeds

## Design Notes

- Volume analysis does NOT need its own hook -- it derives from `useMarketSnapshot().data.quotes`. The page component will transform `Record<string, SessionStats>` into chart data. This avoids a redundant API call.
- When WebSocket lands (Phase 4), replace `usePolling` internals with WS subscription -- hook API stays the same (data/loading/error).

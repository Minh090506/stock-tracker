---
phase: 5
title: "Polish & convenience (mobile + theme + watchlist + CSV export)"
status: pending
priority: P2
effort: "1.5-2w"
dependencies: [1]
note: "Some sub-tasks can run in parallel with Phase 3 or 4 (independent)"
---

# Phase 5: Polish & Convenience

## Overview
UX hoàn thiện cho daily use. Mobile responsive cho **8 pages** (không phải 4), dark/light theme (Tailwind v4 CSS-first), watchlist localStorage + cross-tab sync, CSV export cho 5 tables.

## Requirements

### Functional
- Mobile responsive 375px width cho 8 pages
- Dark/Light theme toggle, persist localStorage, sync giữa tabs
- Watchlist star icon trên price-board rows
- Watchlist filter tab (chỉ show pinned symbols)
- Cmd+K palette quick search/filter
- CSV export button trên 5 tables

### Non-functional
- Lighthouse mobile score >85 cho chart-page
- Theme switch transition smooth (no flash)
- Watchlist sync cross-tab via `storage` event
- CSV UTF-8 BOM cho Excel Windows compat

## Architecture

```
Tailwind v4 dark mode:
  src/index.css
    @import "tailwindcss";
    @variant dark (.dark &);   /* Tailwind v4 syntax */
  All component classes use `dark:` prefix
  
Theme management:
  src/hooks/use-theme.ts        (toggle, persist, cross-tab sync)
  src/components/layout/theme-toggle.tsx
  
Watchlist:
  src/hooks/use-watchlist.ts    (CRUD + storage event)
  src/components/price-board/watchlist-star.tsx
  src/components/price-board/watchlist-filter-tab.tsx
  
Search palette:
  src/components/ui/command-palette.tsx  (Cmd+K)
  
CSV export:
  src/components/ui/csv-export-button.tsx
  src/utils/csv-encoder.ts      (with BOM)
```

## Related Code Files

### Modify (8 pages + components)
- `frontend/src/index.css` — Tailwind v4 dark variant setup
- `frontend/src/pages/price-board-page.tsx`
- `frontend/src/pages/chart-page.tsx`
- `frontend/src/pages/derivatives-page.tsx`
- `frontend/src/pages/foreign-flow-page.tsx`
- `frontend/src/pages/signals-page.tsx`
- `frontend/src/pages/velocity-page.tsx`
- `frontend/src/pages/volume-analysis-page.tsx`
- `frontend/src/pages/backtest-page.tsx`
- `frontend/src/components/price-board/price-board-table.tsx` — add star column
- All chart series colors → theme-aware (use CSS vars)

### Create
- `frontend/src/hooks/use-theme.ts`
- `frontend/src/hooks/use-watchlist.ts`
- `frontend/src/hooks/use-media-query.ts`
- `frontend/src/components/layout/theme-toggle.tsx`
- `frontend/src/components/price-board/watchlist-star.tsx`
- `frontend/src/components/price-board/watchlist-filter-tab.tsx`
- `frontend/src/components/ui/command-palette.tsx`
- `frontend/src/components/ui/csv-export-button.tsx`
- `frontend/src/utils/csv-encoder.ts`
- `frontend/src/__tests__/use-watchlist.test.ts`
- `frontend/src/__tests__/csv-encoder.test.ts`
- `frontend/src/__tests__/use-theme.test.ts`

## Implementation Steps

### Step 1: Tailwind v4 dark variant setup
```css
/* src/index.css */
@import "tailwindcss";

@variant dark (.dark &);

/* Custom CSS variables for chart colors */
:root {
  --chart-bg: #ffffff;
  --chart-text: #1f2937;
  --chart-grid: #e5e7eb;
  --candle-up: #10b981;
  --candle-down: #ef4444;
}

.dark {
  --chart-bg: #111827;
  --chart-text: #f3f4f6;
  --chart-grid: #374151;
  --candle-up: #ef4444;  /* VN convention: red=up */
  --candle-down: #10b981;  /* green=down */
}
```

### Step 2: Theme hook
```ts
// src/hooks/use-theme.ts
import { useState, useEffect } from "react";

type Theme = "light" | "dark";
const KEY = "theme";

export function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(() => {
    const stored = localStorage.getItem(KEY);
    if (stored === "light" || stored === "dark") return stored;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });

  // Apply to DOM
  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    localStorage.setItem(KEY, theme);
  }, [theme]);

  // Cross-tab sync via storage event
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === KEY && (e.newValue === "light" || e.newValue === "dark")) {
        setTheme(e.newValue);
      }
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const toggle = () => setTheme((t) => (t === "light" ? "dark" : "light"));
  return [theme, toggle];
}
```

### Step 3: Theme toggle button
```tsx
// components/layout/theme-toggle.tsx
import { useTheme } from "../../hooks/use-theme";

export function ThemeToggle() {
  const [theme, toggle] = useTheme();
  return (
    <button
      onClick={toggle}
      aria-label="Toggle theme"
      className="p-2 rounded-md hover:bg-gray-200 dark:hover:bg-gray-800"
    >
      {theme === "light" ? "🌙" : "☀️"}
    </button>
  );
}
```

### Step 4: Apply dark classes — page sweep
Approach: per-page, find all `bg-*`, `text-*`, `border-*` hardcoded classes → add `dark:` variant.

Example transformation:
```diff
- <div className="bg-gray-900 text-white">
+ <div className="bg-white text-gray-900 dark:bg-gray-900 dark:text-white">
```

Order: chart-page (biggest), price-board, derivatives, foreign-flow, signals, velocity, volume-analysis, backtest.

### Step 5: Chart series theme
lightweight-charts needs explicit color update on theme change:
```ts
// In candlestick-chart.tsx
useEffect(() => {
  if (!chartRef.current) return;
  const isDark = document.documentElement.classList.contains("dark");
  chartRef.current.applyOptions({
    layout: {
      background: { color: isDark ? "#111827" : "#ffffff" },
      textColor: isDark ? "#f3f4f6" : "#1f2937",
    },
    grid: {
      vertLines: { color: isDark ? "#374151" : "#e5e7eb" },
      horzLines: { color: isDark ? "#374151" : "#e5e7eb" },
    },
  });
}, [theme]);  // theme value from useTheme()
```

### Step 6: Media query hook
```ts
// hooks/use-media-query.ts
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const mq = window.matchMedia(query);
    const handler = (e: MediaQueryListEvent) => setMatches(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [query]);
  return matches;
}
```

### Step 7: Mobile responsive sweep
Per page:
1. Identify horizontal-scroll issues at 375px
2. Add `sm:` / `md:` breakpoints for grid layouts, font sizes
3. Hide secondary columns on mobile via `hidden md:table-cell`
4. Resize chart container to use 100% width with min-height

Example price-board mobile table:
```tsx
<table className="text-xs md:text-sm">
  <th>Symbol</th>
  <th>Price</th>
  <th className="hidden sm:table-cell">Change</th>
  <th className="hidden md:table-cell">Volume</th>
  <th className="hidden lg:table-cell">Active B/S</th>
</table>
```

Chart-page mobile:
- Stack chart + controls vertically
- Hide drawing tools (already done Phase 4)
- Smaller default time range (3M instead of 1Y)

### Step 8: Watchlist hook
```ts
// hooks/use-watchlist.ts
const KEY = "watchlist";
const MAX = 50;

export function useWatchlist() {
  const [symbols, setSymbols] = useState<string[]>(() => {
    try {
      return JSON.parse(localStorage.getItem(KEY) || "[]");
    } catch {
      return [];
    }
  });

  const save = (list: string[]) => {
    localStorage.setItem(KEY, JSON.stringify(list));
    setSymbols(list);
  };

  const add = (sym: string) => {
    if (symbols.includes(sym)) return;
    if (symbols.length >= MAX) return;
    save([...symbols, sym]);
  };

  const remove = (sym: string) => save(symbols.filter((s) => s !== sym));
  const toggle = (sym: string) => (symbols.includes(sym) ? remove(sym) : add(sym));

  // Cross-tab sync
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === KEY && e.newValue) {
        try { setSymbols(JSON.parse(e.newValue)); } catch {}
      }
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  return { symbols, add, remove, toggle, has: (s: string) => symbols.includes(s) };
}
```

### Step 9: Watchlist star + filter tab
```tsx
// components/price-board/watchlist-star.tsx
export function WatchlistStar({ symbol }: { symbol: string }) {
  const { has, toggle } = useWatchlist();
  const starred = has(symbol);
  return (
    <button onClick={() => toggle(symbol)} aria-label={`${starred ? "Remove" : "Add"} ${symbol}`}>
      {starred ? "★" : "☆"}
    </button>
  );
}

// components/price-board/watchlist-filter-tab.tsx
export function WatchlistFilterTab({
  current, onChange,
}: { current: "all" | "watchlist"; onChange: (v: "all" | "watchlist") => void }) {
  return (
    <div className="flex gap-2">
      <button onClick={() => onChange("all")} className={current === "all" ? "...active..." : "..."}>
        All VN30
      </button>
      <button onClick={() => onChange("watchlist")} className={current === "watchlist" ? "...active..." : "..."}>
        ★ Watchlist
      </button>
    </div>
  );
}
```

### Step 10: Command palette (Cmd+K)
```tsx
// components/ui/command-palette.tsx
export function CommandPalette({ symbols, onSelect }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  if (!open) return null;
  const filtered = symbols.filter((s) => s.toLowerCase().includes(query.toLowerCase()));
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-32 bg-black/50">
      <div className="bg-white dark:bg-gray-800 w-96 rounded-lg p-4">
        <input
          autoFocus value={query} onChange={(e) => setQuery(e.target.value)}
          placeholder="Search symbol..."
          className="w-full px-3 py-2 bg-gray-100 dark:bg-gray-700 rounded"
        />
        <ul className="mt-2 max-h-64 overflow-auto">
          {filtered.map((s) => (
            <li key={s}>
              <button onClick={() => { onSelect(s); setOpen(false); }}>{s}</button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
```

### Step 11: CSV export utility
```ts
// utils/csv-encoder.ts
const BOM = "﻿";  // UTF-8 BOM for Excel Windows

export function toCSV(rows: Record<string, unknown>[], filename: string): void {
  if (rows.length === 0) return;
  const headers = Object.keys(rows[0]);
  const csv = BOM + [
    headers.join(","),
    ...rows.map((r) => headers.map((h) => encodeCell(r[h])).join(",")),
  ].join("\r\n");

  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function encodeCell(v: unknown): string {
  if (v == null) return "";
  const s = String(v);
  if (/[",\r\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}
```

### Step 12: CSV export button
```tsx
// components/ui/csv-export-button.tsx
export function CSVExportButton<T extends Record<string, unknown>>({
  data, filename, label = "Export CSV",
}: { data: T[]; filename: string; label?: string }) {
  return (
    <button
      onClick={() => toCSV(data, filename)}
      disabled={data.length === 0}
      className="px-3 py-1.5 text-xs rounded-md bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50"
    >
      {label}
    </button>
  );
}
```

### Step 13: Wire CSV export into 5 tables
- price-board page: `<CSVExportButton data={rows} filename={`vn30-${date}.csv`} />`
- volume-analysis page
- foreign-flow page
- events (chart page sidebar): events list export
- derivatives page

### Step 14: Lighthouse audit + fix
Run Lighthouse mobile on chart-page. Target >85 in Performance + Accessibility.
Common fixes:
- Image lazy loading
- Reduce CLS (set chart container fixed aspect ratio)
- Add ARIA labels
- Focus indicators on interactive elements

### Step 15: Docs sync
- Update `docs/user-guide.md`: theme toggle, watchlist, search, CSV export usage
- Update `docs/design-guidelines.md` reflect dark mode support
- Update `docs/development-roadmap.md` mark Phase 5 complete

## Tests (TDD order)

1. **use-watchlist.test.ts**:
   - add/remove/toggle works
   - localStorage persist
   - max 50 enforced
   - cross-tab storage event syncs
2. **use-theme.test.ts**:
   - toggle flips theme
   - DOM class updated
   - prefers-color-scheme default respected when no localStorage
3. **csv-encoder.test.ts**:
   - Empty array → no download
   - Special chars escaped (comma, quote, newline)
   - UTF-8 BOM prefix present
   - Unicode chars (Vietnamese) preserved
4. **Visual regression (optional, Playwright)**:
   - Screenshot 8 pages at 375px width
   - Both light & dark themes
5. **Manual smoke**:
   - Toggle theme, refresh, theme persisted
   - Open 2 tabs, toggle in one → other updates
   - Star 5 symbols → filter tab shows only those 5
   - Cmd+K → search "VIC" → click → navigates
   - Export CSV from price-board → open in Excel, Vietnamese chars correct

## Success Criteria

- [ ] Tailwind v4 dark variant configured
- [ ] All 8 pages render correctly in both themes
- [ ] All 8 pages no horizontal scroll at 375px width
- [ ] Theme toggle button persists + cross-tab syncs
- [ ] Chart series re-color on theme change
- [ ] Watchlist star + filter tab functional
- [ ] Cmd+K palette opens, searches, selects
- [ ] CSV export downloads valid file for 5 tables
- [ ] Excel opens CSV with Vietnamese chars intact (BOM verified)
- [ ] Lighthouse mobile chart-page Performance ≥85, Accessibility ≥90
- [ ] Frontend tests ≥7 new
- [ ] Docs updated

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Dark mode regression — chart series invisible | Per-chart theme effect explicitly sets colors via applyOptions |
| Page sweep miss hardcoded gray classes | Grep `bg-gray-` `text-white` `text-black` → list, audit each |
| Lighthouse score below target | Chart-page is heavy; consider code-splitting or skeleton loading |
| Cross-tab sync race condition | localStorage atomic; storage event covers; double-set ok |
| CSV malformed for power users | Test with: empty cells, commas in values, quotes, newlines, Vietnamese diacritics |
| Mobile chart unusable (too small) | Set min-height 300px; allow horizontal pan via lightweight-charts touch |
| Cmd+K conflict with browser shortcut | Only override when no input is focused; let browser handle in URL bar |

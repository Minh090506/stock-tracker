# Phase 3: Responsive Design (Mobile)

## Context
- [app-layout-shell.tsx](/Users/minh/Projects/stock-tracker/frontend/src/components/layout/app-layout-shell.tsx) -- fixed sidebar + main flex layout
- [app-sidebar-navigation.tsx](/Users/minh/Projects/stock-tracker/frontend/src/components/layout/app-sidebar-navigation.tsx) -- w-60 fixed sidebar, no collapse
- Pages use some `md:` and `lg:` breakpoints but not comprehensive
- Summary cards: `grid-cols-1 md:grid-cols-3` (already responsive)
- Chart grids: `grid-cols-1 lg:grid-cols-2` (already responsive)
- Tables: no horizontal scroll wrapper
- Volume ratio cards: `grid-cols-3` (no mobile fallback)

## Overview
- **Priority:** P1
- **Status:** pending
- **Effort:** 2h
- **Depends on:** Phase 1 (sidebar changes affect layout shell)

Primary goal: make the dashboard usable on mobile devices (< 768px). The sidebar needs to become a collapsible hamburger menu, and tables need horizontal scroll.

## Key Insights
- Sidebar is the biggest blocker: 240px fixed width eats mobile screen
- Use React state for sidebar toggle (no need for a state library)
- Overlay approach: on mobile, sidebar overlays content with backdrop
- Most chart/card grids already collapse to single column via `grid-cols-1 lg:grid-cols-2`
- Volume ratio cards (`grid-cols-3`) need `grid-cols-1 sm:grid-cols-3` fix
- Tables need `overflow-x-auto` wrapper

## Requirements

**Functional:**
- Sidebar collapses to hamburger icon on screens < md (768px)
- Sidebar opens as overlay on mobile with backdrop click-to-close
- Tables scroll horizontally on small screens
- All tap targets >= 44px on mobile

**Non-functional:**
- No layout breakage at any viewport between 320px and 1920px
- Smooth sidebar transition (transform or opacity)

## Related Code Files

**Modify:**
- `frontend/src/components/layout/app-layout-shell.tsx` -- add mobile sidebar state + hamburger button
- `frontend/src/components/layout/app-sidebar-navigation.tsx` -- add mobile overlay behavior, close callback
- `frontend/src/components/volume/volume-ratio-summary-cards.tsx` -- fix `grid-cols-3` for mobile
- `frontend/src/components/foreign/foreign-flow-detail-table.tsx` -- add `overflow-x-auto`
- `frontend/src/components/volume/volume-detail-table.tsx` -- add `overflow-x-auto`

## Implementation Steps

### Step 1: Add mobile sidebar toggle to AppLayoutShell

Add state + hamburger button visible only on mobile:

```tsx
import { useState } from "react";
import { Outlet } from "react-router-dom";
import { AppSidebarNavigation } from "./app-sidebar-navigation";

export function AppLayoutShell() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen bg-gray-950 text-white flex">
      {/* Mobile hamburger button */}
      <button
        onClick={() => setSidebarOpen(true)}
        className="md:hidden fixed top-4 left-4 z-40 p-2 bg-gray-900 border border-gray-800 rounded-lg"
        aria-label="Open menu"
      >
        {/* 3-line hamburger icon (inline SVG, no extra dep) */}
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </button>

      <AppSidebarNavigation
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
```

### Step 2: Make AppSidebarNavigation responsive

Accept `isOpen` and `onClose` props. On mobile, render as overlay:

```tsx
import { NavLink, useLocation } from "react-router-dom";
import { useEffect } from "react";

interface AppSidebarNavigationProps {
  isOpen: boolean;
  onClose: () => void;
}

export function AppSidebarNavigation({ isOpen, onClose }: AppSidebarNavigationProps) {
  const location = useLocation();

  // Close sidebar on route change (mobile)
  useEffect(() => {
    onClose();
  }, [location.pathname]);

  return (
    <>
      {/* Backdrop (mobile only) */}
      {isOpen && (
        <div
          className="md:hidden fixed inset-0 bg-black/50 z-40"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          w-60 shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col z-50
          fixed md:static inset-y-0 left-0
          transition-transform duration-200
          ${isOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"}
        `}
      >
        {/* Close button (mobile only) */}
        <div className="p-4 border-b border-gray-800 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold text-white tracking-tight">
              VN Stock Tracker
            </h1>
            <p className="text-xs text-gray-500 mt-1">Real-time VN30 Analytics</p>
          </div>
          <button
            onClick={onClose}
            className="md:hidden p-1 text-gray-400 hover:text-white"
            aria-label="Close menu"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <nav className="flex-1 p-3 space-y-1">
          {NAV_ITEMS.map(...)} {/* unchanged */}
        </nav>

        <div className="p-4 border-t border-gray-800 text-xs text-gray-600">
          SSI FastConnect
        </div>
      </aside>
    </>
  );
}
```

**Key CSS pattern:**
- `fixed md:static` -- overlay on mobile, static in flow on desktop
- `-translate-x-full md:translate-x-0` -- hidden by default on mobile, always visible on desktop
- `transition-transform duration-200` -- smooth slide animation
- `z-50` on sidebar, `z-40` on backdrop to layer correctly

### Step 3: Add mobile padding for hamburger button

Pages currently have `p-6`. On mobile, the hamburger sits at top-left. Add top padding on mobile to avoid overlap:

In each page or in the layout shell's `<main>`:

```tsx
<main className="flex-1 overflow-auto pt-14 md:pt-0">
```

This gives room for the fixed hamburger button on mobile, while desktop has no extra top padding.

### Step 4: Fix volume ratio cards grid

In `volume-ratio-summary-cards.tsx`, change:
```
grid-cols-3
```
to:
```
grid-cols-1 sm:grid-cols-3
```

This stacks ratio cards vertically on very small screens.

### Step 5: Add horizontal scroll to tables

Wrap the `<table>` elements in both table components with `overflow-x-auto`:

```tsx
<div className="overflow-x-auto">
  <table className="w-full min-w-[600px]">
    ...
  </table>
</div>
```

`min-w-[600px]` ensures table doesn't squish columns; instead it scrolls.

### Step 6: Verify tap targets

Check all interactive elements have min 44px touch target:
- NavLink buttons: `py-2` = 32px height + text = ~40px. Increase to `py-2.5`
- Filter chips: `px-4 py-2` = ~36px. Increase to `py-2.5`
- Retry button in ErrorBanner: `py-1` = small. Increase to `py-2`

## Todo List

- [ ] Add `sidebarOpen` state + hamburger button to `app-layout-shell.tsx`
- [ ] Add `isOpen`/`onClose` props + overlay behavior to `app-sidebar-navigation.tsx`
- [ ] Add `pt-14 md:pt-0` to main content area for mobile hamburger clearance
- [ ] Auto-close sidebar on route change
- [ ] Fix `volume-ratio-summary-cards.tsx` grid for mobile
- [ ] Add `overflow-x-auto` to `foreign-flow-detail-table.tsx`
- [ ] Add `overflow-x-auto` to `volume-detail-table.tsx`
- [ ] Increase tap target sizes on buttons/links
- [ ] Test at 375px, 768px, 1024px, 1920px widths

## Success Criteria
- Dashboard usable at 375px width (iPhone SE)
- Sidebar hidden by default on mobile, opens with hamburger
- Backdrop click closes sidebar
- Route change closes sidebar
- Tables scroll horizontally without breaking layout
- No overlapping elements at any viewport

## Risk Assessment
- **Medium risk**: Layout changes can cascade; test at multiple breakpoints
- **Mitigation**: Use `md:` breakpoint consistently (768px); don't mix with custom breakpoints
- **Edge case**: Charts may have minimum widths enforced by Recharts; verify they don't overflow

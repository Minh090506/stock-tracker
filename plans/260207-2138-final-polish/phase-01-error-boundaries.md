# Phase 1: Error Boundaries

## Context
- [App.tsx](/Users/minh/Projects/stock-tracker/frontend/src/App.tsx) -- routes wrapped in Suspense, no error boundaries
- [error-banner.tsx](/Users/minh/Projects/stock-tracker/frontend/src/components/ui/error-banner.tsx) -- existing inline error UI (not for render crashes)
- React error boundaries require class components (componentDidCatch)

## Overview
- **Priority:** P1
- **Status:** pending
- **Effort:** 1h

React `Suspense` catches async loading failures but NOT render errors. If a page component throws during render, the entire app crashes with a white screen. Error boundaries catch render errors and display a fallback.

## Key Insights
- React 19 still requires class components for error boundaries (no hook equivalent)
- Keep it simple: one reusable `ErrorBoundary` component, wrap each route
- Reuse existing dark theme styling (gray-900 bg, red accents)
- Include reset mechanism via `key` prop or explicit retry button

## Requirements

**Functional:**
- Catch render errors in any dashboard page without crashing the app
- Display user-friendly error fallback with retry option
- Log error info to console for debugging

**Non-functional:**
- Fallback UI matches dark theme (gray-950/gray-900)
- Retry resets component state (re-mounts the child tree)

## Related Code Files

**Create:**
- `frontend/src/components/ui/error-boundary.tsx`

**Modify:**
- `frontend/src/App.tsx` -- wrap each route's Suspense in ErrorBoundary

## Implementation Steps

### Step 1: Create ErrorBoundary component

File: `frontend/src/components/ui/error-boundary.tsx`

```tsx
import { Component, type ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      return (
        <div className="flex flex-col items-center justify-center min-h-[50vh] p-6">
          <div className="bg-gray-900 border border-red-800/50 rounded-lg p-8 max-w-md text-center">
            <h2 className="text-lg font-semibold text-white mb-2">
              Something went wrong
            </h2>
            <p className="text-sm text-gray-400 mb-4">
              {this.state.error?.message || "An unexpected error occurred."}
            </p>
            <button
              onClick={this.handleRetry}
              className="px-4 py-2 bg-red-800 hover:bg-red-700 text-white text-sm font-medium rounded transition-colors"
            >
              Try Again
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
```

**Design decisions:**
- Default fallback built-in (no extra component needed)
- Optional `fallback` prop for custom fallbacks if needed later
- `handleRetry` resets state, causing children to re-mount
- Matches dark theme: gray-900 card, red accent button

### Step 2: Wrap routes in App.tsx

Update each route to wrap `Suspense` inside `ErrorBoundary`:

```tsx
import { ErrorBoundary } from "./components/ui/error-boundary";

// Each route becomes:
<Route
  path="/foreign-flow"
  element={
    <ErrorBoundary>
      <Suspense fallback={<PageLoadingSkeleton />}>
        <ForeignFlowPage />
      </Suspense>
    </ErrorBoundary>
  }
/>
```

**Why ErrorBoundary wraps Suspense (not inside):**
- ErrorBoundary catches errors from both the lazy load AND the rendered component
- If Suspense itself errors, ErrorBoundary still catches it

## Todo List

- [ ] Create `error-boundary.tsx` with class component
- [ ] Update `App.tsx` to wrap all 3 routes with ErrorBoundary
- [ ] Verify: throw error in a page component, confirm fallback renders
- [ ] Verify: click "Try Again" re-mounts the page

## Success Criteria
- Throwing an error inside ForeignFlowPage renders fallback UI (not white screen)
- Clicking "Try Again" re-renders the page normally
- Error logged to console with component stack
- Other pages remain functional when one page errors

## Risk Assessment
- **Low risk**: Error boundaries are a well-established React pattern
- **Edge case**: Errors in event handlers are NOT caught by error boundaries (expected; they use try-catch)

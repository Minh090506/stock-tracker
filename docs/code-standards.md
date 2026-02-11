# Code Standards & Guidelines

Coding standards for VN Stock Tracker (Python + TypeScript/React).

---

## Python Standards (Backend)

### File Organization

**File Size Management**:
- Maximum 200 LOC per file (hard limit for context management)
- Break large files into focused modules
- Use composition over inheritance

**File Naming**:
- Use `snake_case` for all filenames (Python import requirement)
- Use long, descriptive names: `ssi_auth_service.py` not `auth.py`
- Service files: `*_service.py`, `*_tracker.py`, `*_processor.py`

**Directory Structure**:
```
backend/
├── app/
│   ├── models/           # Domain models (domain.py, schemas.py, ssi_messages.py)
│   ├── services/         # Business logic services (*_service.py, *_tracker.py)
│   ├── routers/          # API endpoints (*_router.py)
│   ├── websocket/        # WebSocket handlers
│   ├── analytics/        # Alert + signal detection
│   ├── database/         # Persistence (pool.py)
│   ├── config.py         # Configuration (pydantic-settings)
│   └── main.py           # FastAPI app + lifespan
├── tests/                # Unit tests (test_*.py)
├── alembic/              # Database migrations
└── locust_tests/         # Load tests (separate from unit tests)
```

### Code Quality

**Type Hints** (Mandatory):
- All functions must have type hints (Python 3.12 syntax OK)
- Use modern syntax: `X | None` instead of `Optional[X]`, `list[str]` instead of `List[str]`
- Example:
```python
def classify(self, trade: SSITradeMessage) -> ClassifiedTrade:
    """Classify trade as active buy/sell/neutral."""
```

**Docstrings**:
- One-line docstring for simple functions
- Multi-line docstring (PEP 257) for complex logic
- Include parameter descriptions and return type

**Error Handling**:
- Use try-catch for external API calls
- Log errors with context (service name, operation, input)
- Raise descriptive exceptions: `ValueError`, `ConnectionError`, `TimeoutError`

**Performance**:
- Target <1ms for per-trade operations (classify, aggregate)
- Target <5ms for full snapshot aggregation (500+ symbols)
- Profile before optimizing; use bounded data structures

**Memory Management**:
- Use `collections.deque(maxlen=X)` for bounded history (cap memory)
- Reset in-memory state daily (session_aggregator, derivatives_tracker)
- Example: basis history capped at 3600 points (~1 hour)

### Testing

**Unit Tests**:
- File: `tests/test_*.py`
- Target: 80%+ code coverage (enforced in CI)
- Test all public methods + edge cases
- Use pytest fixtures from `conftest.py`

**Test Structure**:
```python
def test_trade_classification_active_buy():
    """Test trade classified as active buy when price >= ask."""
    # Arrange
    classifier = TradeClassifier(cache)

    # Act
    result = classifier.classify(trade)

    # Assert
    assert result.trade_type == TradeType.MUA_CHU_DONG
```

**Mocking**:
- Avoid mocks when testing real logic
- Use pytest fixtures for shared test data
- Mock only external dependencies (SSI API, database)

### Naming Conventions

**Variables & Functions**:
- `snake_case` for all variables, functions, methods
- Descriptive names: `active_buy_volume` not `vol`
- Private methods: prefix with `_` → `_compute_basis()`

**Classes**:
- `PascalCase` for all class names
- Service classes: `TradeClassifier`, `ForeignInvestorTracker`
- Model classes (Pydantic): `ClassifiedTrade`, `SessionStats`

**Constants**:
- `UPPER_SNAKE_CASE`
- Example: `MAX_HISTORY_SIZE = 3600`

**Enums**:
- Class name: `PascalCase` → `TradeType`
- Member names: `UPPER_SNAKE_CASE` → `MUA_CHU_DONG`

### Imports

**Order**:
1. Standard library (`asyncio`, `datetime`, `json`)
2. Third-party (`pydantic`, `fastapi`, `asyncpg`)
3. Local imports (`.models`, `.services`)

**Example**:
```python
from asyncio import to_thread
from datetime import datetime
from typing import AsyncGenerator

from fastapi import FastAPI
from pydantic import BaseModel

from app.config import Settings
from app.services.trade_classifier import TradeClassifier
```

### Configuration

**Environment Variables** (`.env`):
- Use `pydantic-settings` for config management (`app/config.py`)
- Required vars: `SSI_CONSUMER_ID`, `SSI_CONSUMER_SECRET`, `DATABASE_URL` (optional for graceful startup)
- Optional vars with defaults (FastAPI port, log level, etc.)

**Config Example**:
```python
class Settings(BaseSettings):
    ssi_consumer_id: str
    ssi_consumer_secret: str
    channel_r_interval_ms: int = 1000
    ws_throttle_interval_ms: int = 500
    database_url: str | None = None  # Graceful startup
    db_pool_min: int = 2
    db_pool_max: int = 10
```

---

## TypeScript/React Standards (Frontend)

### File Organization

**File Size Management**:
- Maximum 200 LOC per component (hard limit)
- Break large features into smaller, composable components
- Keep hooks focused on single concerns

**File Naming**:
- Use `kebab-case` for all filenames (JavaScript convention)
- Component files: `price-board-table.tsx`, `signal-filter-chips.tsx`
- Hook files: `use-websocket.ts`, `use-alerts.ts`
- Utility files: `format-number.ts`, `market-session.ts`

**Directory Structure**:
```
frontend/src/
├── components/
│   ├── layout/              # Navigation, sidebar
│   ├── price-board/         # Price board components
│   ├── derivatives/         # Derivatives panel
│   ├── foreign/             # Foreign flow dashboard
│   ├── signals/             # Alert components
│   ├── ui/                  # Generic UI (buttons, skeletons)
│   └── [feature]/           # Feature-specific components
├── hooks/                   # Custom React hooks
├── pages/                   # Page components
├── types/                   # TypeScript interfaces
├── utils/                   # Utility functions
└── App.tsx                  # Root app component
```

### Code Quality

**Type Safety**:
- Enable `strict: true` in `tsconfig.json` (✓ already enabled)
- All functions must have return type annotations
- Avoid `any` type; use specific types or `unknown` + type guard

**Example**:
```typescript
interface WebSocketResult<T> {
  data: T | null;
  status: ConnectionStatus;
  error: Error | null;
  isLive: boolean;
}

function useWebSocket<T>(
  channel: "market" | "foreign" | "index" | "alerts"
): WebSocketResult<T> {
  // Implementation
}
```

**Component Guidelines**:
- Functional components with hooks only (no class components)
- Export component as default
- Keep component-specific styles with component (or separate CSS file)

**Hook Guidelines**:
- Prefix with `use` (required by React lint)
- Handle cleanup in useEffect (unsubscribe, clear timers)
- Return stable object/array references (use useMemo if needed)

**Naming Conventions**:
- Components: `PascalCase` → `PriceBoardTable`
- Hooks: `camelCase`, prefix with `use` → `usePriceBoardData`
- Variables/functions: `camelCase` → `formatNumber`, `getTodayDate`
- Constants: `UPPER_SNAKE_CASE` → `MAX_CHART_POINTS`
- Interfaces: `PascalCase` → `MarketSnapshot`, `ConnectionStatus`

### Testing

**Jest + React Testing Library**:
- File: `src/__tests__/[component].test.tsx` (optional; focus on e2e)
- Test user interactions, not implementation details
- Mock API calls with `msw` or similar

**Accessibility**:
- Use semantic HTML (`<button>`, not `<div onClick>`)
- ARIA labels for complex components
- Keyboard navigation support

### Styling

**TailwindCSS v4** (Current):
- Use utility classes for styling (no custom CSS when possible)
- Keep component files clean (no inline styles)
- Use CSS modules if component-specific styles needed

**Color Convention (VN Market)**:
- Red = Up (price increase)
- Green = Down (price decrease)
- Fuchsia = Ceiling (TVT - giá trần)
- Cyan = Floor (STC - giá sàn)

### Performance

**Optimization**:
- Lazy load routes: `React.lazy()` + `Suspense`
- Memoize expensive computations: `useMemo`
- Avoid inline object/array literals in dependency arrays
- Use `useCallback` for event handlers passed to children

**Bundle Size**:
- Monitor with `npm run build`
- Avoid adding large dependencies without justification
- Tree-shake unused code (modern bundlers do this)

### API Integration

**Client Implementation**:
- Centralized API client: `src/utils/api-client.ts`
- REST endpoints via helper functions
- WebSocket connections via custom hooks

**Data Fetching**:
- Prefer hooks over direct fetch calls
- Implement error handling + loading states
- Use React Query / SWR if adding advanced features

**Example**:
```typescript
export const useAlerts = () => {
  const { data, status, error, isLive } = useWebSocket<Alert[]>("alerts", {
    fallbackFetcher: async () => {
      const response = await fetch("/api/market/alerts");
      return response.json();
    },
  });

  return { alerts: data || [], status, error, isLive };
};
```

### Best Practices

**State Management**:
- Use React Context for global state (auth, theme, alerts)
- Keep local state in components when possible
- Avoid prop drilling; use Context API or URL state

**Error Handling**:
- Use Error Boundary for component-level error handling
- Display user-friendly error messages
- Log errors to console (dev) or monitoring service (prod)

**Responsive Design**:
- Mobile-first approach
- Test at 375px (mobile), 768px (tablet), 1920px (desktop)
- Use TailwindCSS breakpoints: `sm`, `md`, `lg`, `xl`

---

## Shared Standards (Python + TypeScript)

### Comments & Documentation

**Inline Comments**:
- Explain WHY, not WHAT (code shows what)
- Keep comments accurate (update when code changes)
- Avoid obvious comments: `x = 5  # Set x to 5` ❌

**TODO Comments**:
- Use `# TODO: description` for future improvements
- Include context: who, why, deadline if applicable
- Remove obsolete TODOs during refactoring

**Documentation**:
- Docstrings for all public functions
- README in each major module
- Keep docs in sync with code

### Commit Messages

**Format** (Conventional Commits):
```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `test`: Tests only
- `refactor`: Code restructuring (no logic change)
- `perf`: Performance improvement
- `ci`: CI/CD pipeline changes

**Example**:
```
feat(alerts): add BASIS_DIVERGENCE signal detection

Implement PriceTracker callback for futures basis crossing zero.
Registers alert when basis flips from premium to discount or vice versa.

Fixes #42
```

### Code Review Checklist

Before submitting a PR:

- [ ] Tests written and passing (80%+ coverage)
- [ ] Code follows style guide (naming, imports, type hints)
- [ ] No hardcoded values or secrets
- [ ] Comments explain complex logic
- [ ] Commit messages follow Conventional Commits
- [ ] Documentation updated (if applicable)
- [ ] Performance verified (latency, memory, database queries)
- [ ] No console.log or print statements (use logging)

### CI/CD Requirements

**Backend (Python)**:
- `pytest --cov=app --cov-fail-under=80` must pass
- No type errors (if using mypy)
- Code must be importable

**Frontend (TypeScript)**:
- `npm run build` must succeed
- `npx tsc --noEmit` zero type errors
- ESLint warnings/errors resolved

**Docker**:
- `docker-compose.prod.yml build` must succeed
- Images must not exceed size limits
- Health checks must pass

---

## Gotchas & Common Mistakes

### Python

1. **Async Context**: `asyncio.to_thread()` for sync-only libraries (SSI SDK is sync-only)
2. **Loop Reference**: Store main event loop before using in threads
3. **Snake Case**: Python files MUST use snake_case (import requirement)
4. **Bounded Structures**: Use `deque(maxlen=X)` for capped memory

### TypeScript/React

1. **Strict Mode**: All files compiled with `strict: true`
2. **Hooks Rules**: Hooks only in components, not in conditions
3. **Key Props**: Always include `key` prop in lists
4. **Kebab Case**: Component/hook filenames MUST use kebab-case

---

## Tools & Linting

**Backend**:
- Formatter: `black` (auto-format on save)
- Linter: `pylint` (optional; focus on tests)
- Type check: `mypy` (optional; use type hints)
- Tests: `pytest` (required, 80% coverage enforced)

**Frontend**:
- Formatter: `prettier` (configured in package.json)
- Linter: `eslint` + `typescript-eslint`
- Type check: `tsc --noEmit` (strict mode)
- Build: `vite` (configured in vite.config.ts)

**Setup Commands**:
```bash
# Backend
cd backend && python -m pytest --cov=app --cov-fail-under=80

# Frontend
cd frontend && npm run build && npx tsc --noEmit

# Docker
docker-compose -f docker-compose.prod.yml build
```

---

## Architecture Principles

**YAGNI** (You Aren't Gonna Need It):
- Don't add features without clear requirements
- Keep code simple and focused

**KISS** (Keep It Simple, Stupid):
- Prefer straightforward solutions
- Avoid over-engineering

**DRY** (Don't Repeat Yourself):
- Extract common logic to shared modules
- Reuse functions/components

**Single Responsibility**:
- Each module/component has one reason to change
- Services focus on one data domain (trades, foreign, index)
- Components focus on one UI concern

---

## Resources

- **Python**: [PEP 8](https://pep8.org/), [Type Hints](https://docs.python.org/3/library/typing.html)
- **TypeScript**: [TypeScript Handbook](https://www.typescriptlang.org/docs/)
- **React**: [React Documentation](https://react.dev/)
- **TailwindCSS**: [Tailwind Docs](https://tailwindcss.com/docs)
- **FastAPI**: [FastAPI Guide](https://fastapi.tiangolo.com/)


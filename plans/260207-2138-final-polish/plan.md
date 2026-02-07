---
title: "Final Polish - UX, Config & Deployment"
description: "Error boundaries, loading skeletons, responsive design, env config, Docker Compose, README"
status: pending
priority: P1
effort: 8h
branch: master
tags: [frontend, ux, docker, deployment, polish]
created: 2026-02-07
---

# Final Polish Plan

## Phase Overview

| # | Phase | Effort | Priority | Status |
|---|-------|--------|----------|--------|
| 1 | Error Boundaries | 1h | P1 | pending |
| 2 | Loading Skeletons | 1.5h | P2 | pending |
| 3 | Responsive Design (Mobile) | 2h | P1 | pending |
| 4 | Environment Config (Production) | 1h | P2 | pending |
| 5 | Docker Compose (Full Stack) | 1.5h | P1 | pending |
| 6 | README Update | 1h | P2 | pending |

## Dependencies

```
Phase 1 (Error Boundaries) ─── independent
Phase 2 (Skeletons)        ─── independent
Phase 3 (Responsive)       ─── after Phase 1 (sidebar changes affect layout)
Phase 4 (Env Config)       ─── independent
Phase 5 (Docker Compose)   ─── after Phase 4 (needs env config)
Phase 6 (README)           ─── after Phase 4 + 5 (documents docker + env)
```

**Parallel Group A:** Phases 1, 2, 4 (independent)
**Sequential:** Phase 3 after 1; Phase 5 after 4; Phase 6 last

## Files Modified/Created Summary

### Frontend (kebab-case)
- `frontend/src/components/ui/error-boundary.tsx` -- NEW
- `frontend/src/components/ui/page-loading-skeleton.tsx` -- MODIFY (add page-specific variants)
- `frontend/src/components/ui/foreign-flow-skeleton.tsx` -- NEW
- `frontend/src/components/ui/volume-analysis-skeleton.tsx` -- NEW
- `frontend/src/components/ui/signals-skeleton.tsx` -- NEW
- `frontend/src/components/layout/app-layout-shell.tsx` -- MODIFY (responsive)
- `frontend/src/components/layout/app-sidebar-navigation.tsx` -- MODIFY (collapsible mobile)
- `frontend/src/App.tsx` -- MODIFY (wrap routes with error boundary)
- `frontend/.env.production` -- NEW

### Backend (snake_case)
- `backend/app/config.py` -- MODIFY (add CORS, LOG_LEVEL)
- `backend/.env.production` -- NEW

### Root
- `docker-compose.yml` -- MODIFY (add redis, data-collector, health checks)
- `README.md` -- MODIFY (comprehensive update)

## Phase Details

- [Phase 1: Error Boundaries](./phase-01-error-boundaries.md)
- [Phase 2: Loading Skeletons](./phase-02-loading-skeletons.md)
- [Phase 3: Responsive Design](./phase-03-responsive-design.md)
- [Phase 4: Environment Config](./phase-04-environment-config.md)
- [Phase 5: Docker Compose](./phase-05-docker-compose.md)
- [Phase 6: README Update](./phase-06-readme-update.md)

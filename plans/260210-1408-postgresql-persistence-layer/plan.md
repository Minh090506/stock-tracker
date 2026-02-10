---
title: "PostgreSQL Persistence Layer Enhancement"
description: "Harden DB layer with configurable pool, Alembic migrations, prod compose, and graceful startup"
status: completed
priority: P2
effort: 3h
branch: master
tags: [database, persistence, alembic, docker, resilience]
created: 2026-02-10
completed: 2026-02-10
---

# PostgreSQL Persistence Layer Enhancement

## Context

Backend already has asyncpg pool (`connection.py`), batch writer, history service, and full TimescaleDB schema in `db/migrations/001_create_hypertables.sql`. Current gaps: hardcoded pool sizes, no migration tooling, no DB in prod compose, and app crashes if DB is unavailable at startup.

## Scope

Enhance existing DB layer -- NOT rebuild. Four focused phases targeting config, migrations, deployment, and resilience.

## Phases

| # | Phase | Est. | Status | File |
|---|-------|------|--------|------|
| 1 | Pool config + health check | 45m | complete | [phase-01](./phase-01-pool-and-config.md) |
| 2 | Alembic migration setup | 45m | complete | [phase-02](./phase-02-alembic-setup.md) |
| 3 | Docker compose prod DB | 30m | complete | [phase-03](./phase-03-docker-compose-prod.md) |
| 4 | Graceful startup (DB optional) | 30m | complete | [phase-04](./phase-04-graceful-startup.md) |

## Dependencies

- Phase 1 must complete before Phase 4 (pool.py rename + health_check used in main.py)
- Phase 2 is independent (Alembic uses sync psycopg2, separate from async app)
- Phase 3 is independent (Docker compose changes only)
- Phase 4 depends on Phase 1

**Execution order:** Phase 1 -> (Phase 2 + Phase 3 in parallel) -> Phase 4

## Files Changed Summary

| Action | File |
|--------|------|
| RENAME | `backend/app/database/connection.py` -> `pool.py` |
| MODIFY | `backend/app/database/__init__.py` |
| MODIFY | `backend/app/database/batch_writer.py` |
| MODIFY | `backend/app/database/history_service.py` |
| MODIFY | `backend/app/config.py` |
| MODIFY | `backend/app/main.py` |
| MODIFY | `backend/app/routers/history_router.py` |
| MODIFY | `backend/tests/test_history_service.py` |
| MODIFY | `backend/tests/test_batch_writer.py` |
| MODIFY | `backend/requirements.txt` |
| MODIFY | `backend/.env.example` |
| MODIFY | `docker-compose.prod.yml` |
| CREATE | `backend/alembic.ini` |
| CREATE | `backend/alembic/env.py` |
| CREATE | `backend/alembic/script.py.mako` |
| CREATE | `backend/alembic/versions/001_create_hypertables.py` |

## Key Decisions

- **Rename not delete** `connection.py` -> `pool.py` — preserves git history
- **Raw SQL Alembic** — no SQLAlchemy ORM, keep asyncpg-only stack
- **psycopg2-binary** for Alembic only (sync driver required by Alembic)
- **Graceful degradation** — app starts without DB, real-time streaming still works

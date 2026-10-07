# AI-Assisted Systematic Literature Review (SLR) Platform

Production-oriented web application supporting systematic reviews, systematic
mapping studies, scoping and rapid reviews: literature import, deduplication,
title/abstract and full-text screening, AI-assisted recommendations with
criterion-level evidence, data extraction with human verification, quality
assessment, evidence matrices, PRISMA tracking and auditable synthesis.

> **Design law:** *AI assists the researcher; AI does not replace the
> researcher.* Every AI output is evidence-linked, versioned, reviewable and
> overridable. Research validity > traceability > recall > accuracy > workload
> > speed > cost.

## Status

**Phase 2 complete:** authentication (argon2id + server-side sessions), RBAC,
project/member management, versioned & lockable protocol, audit log, Alembic
migration baseline — **60 tests passing, ruff clean**.
Phase 1 delivered architecture docs + backend skeleton.
See [`docs/ROADMAP.md`](docs/ROADMAP.md) for the phased plan — no feature is
claimed complete until its tests have actually run.

## Documentation

| Document | Contents |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Principles, stack, components, layering, API/job/testing conventions |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | 15-phase plan, per-phase verification protocol |
| [`docs/DATABASE_SCHEMA.md`](docs/DATABASE_SCHEMA.md) | Full relational schema (35+ tables) and invariants |
| [`docs/AI_ARCHITECTURE.md`](docs/AI_ARCHITECTURE.md) | Provider abstraction, task services, evidence-first prompting, hallucination controls |
| [`docs/SECURITY.md`](docs/SECURITY.md) | Auth, RBAC, file security, prompt-injection defence, security test plan |

## Stack

- **Backend:** Python 3.13 · FastAPI · Pydantic v2 · SQLAlchemy 2.0
- **Database:** SQLite (dev/test) / PostgreSQL (production) — selected by `SLR_DATABASE_URL`
- **Frontend:** Next.js + TypeScript + Tailwind (Phase 2)
- **Tests:** pytest + ruff

## Development

```powershell
# from repository root
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt

cd backend
..\..\\.venv\Scripts\python.exe -m pytest        # run tests
..\..\\.venv\Scripts\python.exe -m ruff check .  # lint
..\..\\.venv\Scripts\python.exe -m uvicorn app.main:app --reload  # serve API
```

API docs: `http://localhost:8000/api/v1/docs` · Health: `GET /api/v1/health`

## Repository layout

```
docs/      architecture documentation (source of truth)
backend/   FastAPI application (app/), tests (tests/)
frontend/  Next.js application (Phase 2+)
```

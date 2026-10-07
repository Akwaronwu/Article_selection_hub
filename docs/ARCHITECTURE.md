# System Architecture — AI-Assisted SLR Platform

Status: Phase 1 baseline (2026-10-05). Living document; updated per phase.

## 1. Governing principles

1. **AI assists; AI does not replace the researcher.** Every AI output is a *recommendation* requiring human review unless an explicit automation policy is enabled.
2. **Evidence-grounded.** Every AI claim links to document → version → page → section → span.
3. **No hallucinated evidence.** Missing information is reported as `NOT_REPORTED` / "Unable to determine from available evidence."
4. **Reproducibility.** Every AI run records model, provider, prompt+version, timestamp, document version, retrieved passages, output, confidence.
5. **Version everything.** Criteria, protocols, prompts, decisions, extractions are versioned; changes never silently alter history.
6. **Researcher ownership.** AI output can always be accepted, edited, rejected, or restored — with rationale captured.

Optimisation order: research validity > traceability > screening recall > accuracy > workload > speed > cost.

## 2. Repository inspection result

The repository was **empty** (no code, no git, no configuration). Environment: Windows, Python 3.13.14, Node 24.14.0, npm 11.9.0, **no PostgreSQL, no Docker**. Consequence: SQLite is the dev/test database and PostgreSQL the production target; both accessed only through SQLAlchemy so switching is a configuration change (`DATABASE_URL`).

## 3. Stack

| Layer | Technology | Rationale |
|---|---|---|
| Backend | FastAPI + Pydantic v2 | Type-safe, OpenAPI, async-capable, verified installable |
| ORM / DB | SQLAlchemy 2.0 (declarative) | SQLite↔PostgreSQL portability; JSONB via `JSON` type |
| Migrations | Alembic (Phase 2) | Versioned schema evolution |
| Frontend | Next.js + TypeScript + Tailwind | Planned Phase 2; `npm.cmd` required on this machine |
| Jobs | `JobQueue` abstraction: in-process (dev), Redis/RQ (prod) | Long imports/AI runs must not block the UI |
| AI | `LLMProvider` protocol; OpenAI/Anthropic/Google/local adapters | No provider hard-coded anywhere |
| Vector | Abstract `VectorStore`; PostgreSQL+pgvector first | Swappable later |
| Tests | pytest + httpx `TestClient` + ruff | Run on every phase |

## 4. Component overview

```
Frontend (Next.js)  ──HTTP/JSON──►  API layer (FastAPI, /api/v1)
                                        │
             ┌──────────────┬───────────┼───────────────┬─────────────┐
             ▼              ▼           ▼               ▼             ▼
        Domain        AI orchestration  Document      Retrieval    Audit log
        services      (task services)   processing    (hybrid)     (append-only)
        screening     screening/extract parsing PDF   keyword      every important
        criteria      quality/classify  RIS/BibTeX    + vector     event + AI run
        extraction    synthesis         page-aware    section-aware
        conflicts     evidence-first    chunking      metadata
             │              │               │               │
             └──────────────┴───────┬───────┴───────────────┘
                                    ▼
                     Relational DB (SQLite dev / PostgreSQL prod)
                     + vector store (pgvector) + object storage (PDFs)
```

## 5. Repository layout

```
our-slr-app/
├── docs/                  ARCHITECTURE, ROADMAP, DATABASE_SCHEMA, AI_ARCHITECTURE, SECURITY
├── backend/
│   ├── app/
│   │   ├── main.py        ASGI app factory (create_app)
│   │   ├── config.py      Settings from environment (SLR_* prefix, .env)
│   │   ├── db.py          engine/session/Base; create/set/reset engine for tests
│   │   ├── api/           routers mounted under /api/v1
│   │   ├── models/        SQLAlchemy ORM models
│   │   ├── schemas/       Pydantic request/response models
│   │   ├── services/      business logic (pure where possible)
│   │   ├── ai/            providers/, tasks/, prompts/, retrieval/
│   │   ├── documents/     importers + parsers (untrusted-input handling)
│   │   └── jobs/          JobQueue abstraction
│   ├── tests/             pytest suites (unit + integration)
│   ├── requirements.txt   pinned runtime deps
│   └── requirements-dev.txt
├── frontend/              Next.js app (Phase 2+)
└── README.md
```

## 6. Layering rules

- `api` → `services` → `models`. Never the reverse; routers contain no business logic.
- `ai/*` depends on service interfaces, not on FastAPI or ORM sessions directly.
- All prompts live in the prompt registry (DB) — never inline in feature code.
- Configuration only via `Settings` (env vars). No hard-coded keys, models, thresholds, URLs.
- Domain logic (eligibility evaluation, PRISMA counting, duplicate scoring) is pure and unit-testable.

## 7. API conventions

- Base path `/api/v1`; REST; JSON; Pydantic schema for every request/response.
- Errors: `{"detail": ..., "code": ...}` with correct HTTP status; validation errors → 422.
- Pagination: `?page=&page_size=` with `total` in responses.
- Auth (implemented, Phase 2): HttpOnly session cookie → server-side session
  lookup; per-project RBAC (`app/rbac.py`, fail-closed); anti-IDOR 404s for
  non-members; every protected endpoint resolves identity + membership +
  permission. Passwords: argon2id.
- OpenAPI at `/docs`; restricted or disabled in production.

## 8. Background jobs

Operations that can exceed ~1s (bulk import, dedup, PDF parsing, embeddings, AI screening/extraction) are enqueued: `POST` returns `job_id` immediately; clients poll `GET /jobs/{id}` for progress/status. Failures set status `failed` with a reason — **never** a partial state change to study data. Job execution sits behind a `JobQueue` interface so dev (in-process) and prod (Redis/RQ) share one API.

## 9. Document processing

PDF/DOCX/TXT parsed into **page-preserving** structures: `document_versions` → `document_pages` → `document_sections/chunks`. Uploaded files are untrusted: size/type limits, hash-on-upload, no active content, parsing treated as hostile input. See `docs/SECURITY.md`.

## 10. Configuration & environments

- `SLR_*` env vars (see `.env.example`): `DATABASE_URL`, `ENVIRONMENT`, `CORS_ORIGINS`, provider keys, model names, thresholds.
- `development` / `test` / `production` profiles. Tests always use an isolated temp SQLite database (no shared state).
- API keys are backend-only; never sent to the browser.

## 11. Testing strategy

- **Unit:** eligibility rule engine, duplicate scoring, PRISMA counting, extraction validation.
- **Integration:** API endpoints via `TestClient`, DB round-trips, parsers with fixture files.
- **Security:** prompt-injection fixtures, malicious PDFs, upload validation, access control.
- **AI evaluation:** gold-standard set → precision/recall/F1/MCC/kappa/calibration; offline fixtures so CI never calls a live LLM.
- Per-phase protocol: implement → `pytest` → fix → `ruff` → update docs → report real results only.


# Roadmap

Derived from the master development prompt §110 (incremental development). Status: ⬜ not started · 🟨 in progress · ✅ complete & verified with tests.

## Phase status

| Phase | Scope | Status |
|---|---|---|
| 1 | Repository inspection & architecture docs + backend skeleton | ✅ |
| 2 | Authentication, RBAC, project management, protocols | ✅ |
| 3 | Literature import (RIS/BibTeX/CSV/DOI list), metadata store | ⬜ |
| 4 | Duplicate detection (exact → fuzzy → semantic) + human decisions | ⬜ |
| 5 | Title/abstract screening pipeline, criteria builder, state machine | ⬜ |
| 6 | Full-text upload, page-aware PDF processing, evidence viewer | ⬜ |
| 7 | AI screening (criterion-by-criterion, evidence-linked, uncertainty-aware) | ⬜ |
| 8 | Double screening, conflict resolution, inter-rater reliability | ⬜ |
| 9 | Extraction schema builder, AI extraction, human verification | ⬜ |
| 10 | Quality/risk-of-bias assessment frameworks | ⬜ |
| 11 | Evidence matrix, taxonomy, claim–evidence graph | ⬜ |
| 12 | PRISMA tracking + search strategy management | ⬜ |
| 13 | Synthesis workspace (grounded drafts, gap analysis, contradictions) | ⬜ |
| 14 | Experiments/benchmarking, gold standard, performance dashboard | ⬜ |
| 15 | Security hardening, performance, observability, exports | ⬜ |

## Phase 1 detail (this increment)

**Deliverables**
- `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, `docs/DATABASE_SCHEMA.md`, `docs/AI_ARCHITECTURE.md`, `docs/SECURITY.md`
- Backend skeleton: `config.py` (env-driven), `db.py` (engine/session/Base + test hooks), `main.py` (app factory), `/api/v1/health`
- Test suite: health endpoint, settings/env handling, DB engine round-trip, OpenAPI generation
- Tooling: pinned `requirements.txt`, `requirements-dev.txt`, `pytest.ini`, `.gitignore`, `.env.example`, `README.md`

**Explicitly out of scope for Phase 1:** frontend, auth, models for studies/criteria, AI calls, migrations.

## Verification protocol (every phase)

1. Implement in small increments.
2. Run `backend> .venv\Scripts\python -m pytest -q`.
3. Fix all failures before proceeding.
4. Run `ruff check .` and fix findings.
5. Update the affected docs.
6. Report: what was implemented · files changed · tests run · actual results · known limitations · next phase.

**Rule: never claim a feature works unless its tests have actually been executed and passed in this environment.**

## Phase 2 detail (completed)

**Decisions made**
- *Auth mechanism:* server-side sessions — random 256-bit token in an
  `HttpOnly; SameSite=Lax; Secure(prod)` cookie; only the **SHA-256 digest**
  stored in `user_sessions`. No JWT (first-party web app; revocation is trivial).
- *Password hashing:* argon2id with OWASP parameters (m=19 MiB, t=2, p=1).
- *Migrations:* Alembic baseline `1608e38400f0` (`alembic upgrade head`);
  `alembic/env.py` honours a programmatic URL so tests migrate temp DBs.
- *SQLite parity:* `PRAGMA foreign_keys=ON` on every connection so
  `RESTRICT`/`CASCADE`/`SET NULL` behave identically to PostgreSQL in dev/test.

**Delivered**
- Models: `users`, `project_members`, `projects`, `user_sessions`,
  `protocols`, `protocol_versions`, `audit_logs` (schema of record updated).
- Security: `app/security.py` (argon2id, session tokens, email normalisation),
  `app/rbac.py` (5 roles × 10 permissions, fail-closed), `app/deps.py`
  (cookie → session → user; anti-IDOR project context).
- Endpoints (14 total incl. health): register/login/logout/me, project CRUD
  with status state machine, member management with last-owner invariants,
  protocol read/versioned-edit/lock/unlock; audit rows on every mutation.
- Bug fixes found by tests: cookie `expires` needs tz-aware UTC (broke every
  auth flow), `last_login_at` read pre-flush `None`, deprecated 422 constant.

**Verification (actually executed)**
- `pytest`: **60 passed** (13 Phase-1 + 47 Phase-2), exit 0.
- `ruff check .`: **All checks passed**, exit 0.
- Alembic: `upgrade head` on empty DB creates all 7 tables;
  model↔migration parity asserted (`test_upgrade_creates_all_model_tables`);
  `downgrade base` verified.

**Known limitations**
- No frontend yet — API-only this phase (Next.js scaffold deferred to Phase 5
  so screening UI lands with it).
- No email verification/invites: closed registration admits the bootstrap
  user only; members are added by the owner via the members API.
- No password reset flow; no rate limiting on auth endpoints (Phase 15).
- `StarletteDeprecationWarning` about `httpx` is upstream (FastAPI TestClient);
  ignored, not ours.

**Next recommended phase:** Phase 3 — Literature import (RIS/BibTeX/CSV/DOI
list parsers, metadata store, import batches).

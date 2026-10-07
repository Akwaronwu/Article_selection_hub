# Database Schema

Target: PostgreSQL in production, SQLite in dev/tests. All tables use UUID string PKs (`id CHAR(36)`), `created_at`/`updated_at` timestamps (UTC). `JSONB` on PostgreSQL maps to SQLAlchemy `JSON`. Covers every entity in master prompt §106 plus duplicates, claims, jobs, and PRISMA.

Conventions: FKs are `ON DELETE RESTRICT` for research data (never silently cascade-delete evidence), `ON DELETE CASCADE` only for user-generated child rows (comments, notifications). Indexes on all FKs and every filter column listed.

## Identity & access

**users** — id, email (unique), display_name, password_hash (argon2id), is_active, created_at, last_login_at.
**user_sessions** — id, user_id → users (CASCADE), token_hash (SHA-256 hex, unique), created_at, expires_at, revoked_at, ip_address, user_agent. *Raw tokens exist only in HttpOnly cookies; the DB stores digests (docs/SECURITY.md §1).*
**projects** — id, title, research_question, review_type (slr/sms/scoping/rapid/evidence), objectives (JSON), status (draft/active/locked/archived), owner_id → users, settings (JSON), timestamps.
**project_members** — id, project_id → projects, user_id → users, role (owner/reviewer/adjudicator/assistant/viewer), is_blinded (bool: hides other reviewers' decisions until both submit), created_at. UNIQUE(project_id, user_id).

## Protocol & criteria (versioned)

**protocols** — id, project_id, current_version, locked_at (nullable), locked_version_id.
**protocol_versions** — id, protocol_id, version, objectives (JSON), research_questions (JSON), screening_procedure, extraction_procedure, synthesis_strategy, created_by, created_at, change_note.
**criteria** — id, project_id, code (IC01/EC01, unique per project), kind (inclusion/exclusion), name, description, operational_definition, framework (PICOS/PICOC/SPIDER/custom), required (bool), evidence_required (JSON), screening_stage, position, status (active/retired).
**criteria_versions** — id, criterion_id, version, snapshot (JSON of all fields), changed_by, changed_at, change_note. *A criteria change creates a row; historical decisions keep referencing the version they used (§1.5).*
**decision_rules** — id, project_id, stage, include_rule (JSON AST over criterion codes: AND/OR/NOT, nestable), exclude_rule (JSON AST), version, status. *Supports `INCLUDE IF: IC01 AND IC02` / `EXCLUDE IF: EC01 OR EC02` (§5).*

## Literature & import

**studies** — id, project_id, title, normalized_title, abstract, authors (JSON), year, venue, doi, url, keywords (JSON), affiliations (JSON), citation_count, language, publication_type, status (state machine §59: IMPORTED → DUPLICATE_CHECK → TITLE_ABSTRACT_PENDING → … → INCLUDED), stage_position, criteria_version_id (the criteria used for its decisions), created_at, updated_at. Indexes: (project_id, status), (project_id, doi); PG trigram on normalized_title.
**study_identifiers** — id, study_id, id_type (doi/pmid/arxiv/pmc/other), value. UNIQUE(study_id, id_type, value).
**study_sources** — id, study_id, search_id → searches, import_batch_id, source_database, imported_at. *Many-to-many: one study can arrive via several searches (PRISMA per-source counts).*
**searches** — id, project_id, database_name, search_string, search_string_version, date_searched, filters (JSON), result_count, export_file_path, export_file_hash, notes. *Auditable search history (§45–46).*
**import_batches** — id, project_id, filename, file_hash, format (ris/bibtex/csv/endnote_xml/doi_list/pubmed/scopus/wos/…), record_count, imported_by, imported_at, errors (JSON).

## Duplicates

**duplicate_pairs** — id, project_id, study_a_id, study_b_id, stage (exact/fuzzy/semantic), similarity (float), signals (JSON: {doi, title, authors, year, venue}), status (pending/kept_a/kept_b/merged/not_duplicate). UNIQUE(project_id, study_a_id, study_b_id).
**duplicate_decisions** — id, pair_id, decision, decided_by, decided_at, rationale, merged_study_id (nullable). *Never auto-delete: rows are kept, `status` marks the loser and PRISMA counts it as "duplicates removed" (§9).*

## Documents

**documents** — id, study_id, kind (full_text/supplement/other), current_version_id, retrieval_method (upload/doi/url/repository), status (pending/processing/ready/failed), created_at.
**document_versions** — id, document_id, version (int), filename, mime_type, byte_size, sha256, storage_path, page_count, extraction_status, uploaded_by, created_at. *Replacing a PDF creates a new version; extractions record which version they used (§96).*
**document_pages** — id, document_version_id, page_number, text, section_hint. FTS index on text (PostgreSQL tsvector / SQLite FTS5).
**document_chunks** — id, document_version_id, page_from, page_to, section, chunk_index, text, embedding (vector, nullable), token_count. Vector index (pgvector HNSW) when present.

## Screening

**screening_stages** — id, project_id, name (title_abstract/full_text/final/custom), position, criteria_version_id, config (JSON: blind_reviewers, require_exclusion_reason), is_active. *Researchers can create custom stages (§10).*
**screening_decisions** — id, study_id, stage_id, reviewer_id, decision (include/exclude/unclear), exclusion_reason_id (nullable), notes, criteria_version_id, decision_version (int), supersedes_id (nullable), is_final (bool), created_at. *Append-only versioning: an edit inserts a new row (§97).*
**screening_evidence** — id, decision_id, criterion_id, ai_run_id (nullable), source (ai/human), criterion_decision (satisfied/not_satisfied/unclear/not_applicable), evidence_text, document_version_id, page_number, section, span_start, span_end, confidence. *Criterion-by-criterion auditability (§12).*
**exclusion_reasons** — id, project_id, code, label, category (controlled: wrong_population / wrong_intervention / wrong_outcome / wrong_context / wrong_publication_type / not_empirical / duplicate / insufficient_information / wrong_language / outside_period / domain_specific / custom), is_default, position. *Feeds PRISMA (§19).*
**reviewer_conflicts** — id, study_id, stage_id, decision_a_id, decision_b_id, status (open/resolved), resolution, resolution_reason, adjudicator_id, resolved_at. *A vs B stay blinded until both submit (§20).*

## Extraction

**extraction_schemas** — id, project_id, name, version, status (draft/active/retired), created_by, created_at.
**extraction_fields** — id, schema_id, key, label, field_type (text / long_text / number / decimal / date / boolean / select / multi_select / list / object / table / citation / evidence_span), options (JSON), validation (JSON: min/max/regex/required), evidence_required (bool), help_text, position.
**extraction_values** — id, study_id, field_id, schema_version_id, value (JSON), status (reported / inferred / not_reported / unclear / human_verified), confidence, source (ai/human), ai_run_id, document_version_id (nullable), version (int), supersedes_id (nullable), verified_by, verified_at, notes. *`inferred` is never silently converted to `reported` (§25).*
**extraction_evidence** — id, extraction_value_id, document_version_id, page_number, section, paragraph_index, quote_text, span_start, span_end, table_ref (nullable), figure_ref (nullable), is_approximate (bool default false). *Every value traceable to source (§66).*

## Quality assessment

**quality_frameworks** — id, project_id, name (CASP/JBI/MMAT/ROBINS-I/custom), version, items (JSON), status, created_at.
**quality_assessments** — id, study_id, framework_id, item_responses (JSON: [{item_id, response, rationale, evidence_id}]), overall_score (nullable), overall_rating (high/medium/low/unclear), assessor_id, ai_run_id (nullable), version, supersedes_id, created_at.

## Taxonomy & classification

**taxonomies** — id, project_id, name, description, status (proposed_by_ai/approved/retired), source (human/ai), version. *AI-proposed taxonomies require approval (§35).*
**taxonomy_terms** — id, taxonomy_id, parent_id (self-FK nullable), code, label, description, position. *Unlimited hierarchy (§34).*
**study_classifications** — id, study_id, term_id, source (ai/human), confidence, ai_run_id, assigned_by, created_at. UNIQUE(study_id, term_id).

## AI & prompts

**prompts** — id, key (unique: SCREEN_TITLE_ABSTRACT_V1, FULL_TEXT_SCREENING_V1, EXTRACT_METHOD_V1, EXTRACT_RESULTS_V1, QUALITY_ASSESSMENT_V1, SYNTHESIS_V1, …), name, task (screening/extraction/quality/classification/synthesis), description, output_schema (JSON Schema), created_at.
**prompt_versions** — id, prompt_id, version (int), system_instructions, template, model_hints (JSON), temperature, author, created_at, is_active, change_note. *Prompts live here — never inline in feature code (§67).*
**ai_runs** — id, project_id, task, provider, model, model_version, prompt_version_id, temperature, document_version_id (nullable), study_id (nullable), input_summary (JSON), retrieved_passages (JSON), raw_output, parsed_output (JSON), validation_status (ok/retried/failed), confidence, token_in, token_out, cost_usd, latency_ms, error (nullable), created_at. *The AI audit log (§49).*
**ai_outputs** — id, ai_run_id, target_type (screening_decision/extraction_value/classification/quality/synthesis), target_id (nullable), status (proposed/accepted/edited/rejected), human_decision_id (nullable), human_feedback. *Links recommendation → human verdict for evaluation and feedback loops (§102).*

## Synthesis, evidence & PRISMA

**claims** — id, project_id, text, type (finding/gap/contradiction), status (ai_draft/verified/rejected), created_by, ai_run_id (nullable), created_at.
**claim_evidence** — id, claim_id, study_id, extraction_value_id (nullable), relation (supports/contradicts/qualifies), note, added_by. *Claim → supporting studies → extracted evidence → document → page (§41).*
**evidence_clusters** — id, project_id, name, basis (rq/method/technique/problem/dataset/outcome), locked (bool default false). **cluster_members** — cluster_id, study_id, source (ai/human), confidence. *Researchers can edit clusters (§39).*
**synthesis_documents** — id, project_id, kind (narrative/thematic/table), content_md, status (ai_draft/human_edited/approved), ai_run_id, version, created_by, updated_at. *AI drafts, human publishes (§75).*
**prisma_snapshots** — id, project_id, computed_at, counts (JSON: identified, duplicates_removed, screened, screened_excluded, full_texts_assessed, full_texts_excluded, included + per-source and per-reason breakdown), is_consistent (bool), warnings (JSON). *Derived from data; inconsistent manual numbers warn (§44).*

## Collaboration & system

**audit_logs** — id, project_id (nullable), user_id, action, entity_type, entity_id, object_before (JSON), object_after (JSON), reason, ai_run_id (nullable), ip_address, created_at. *Append-only: no UPDATE/DELETE (§48).*
**comments** — id, project_id, entity_type, entity_id, author_id, body, mentions (JSON), parent_id (nullable), created_at, deleted_at (nullable).
**notifications** — id, user_id, project_id, kind, payload (JSON), read_at (nullable), created_at.
**jobs** — id, project_id, kind, status (queued/running/failed/done), progress (0–100), payload (JSON), result (JSON), error, created_by, created_at, started_at, finished_at. *Background operations (§108).*
**experiments** — id, project_id, name, hypothesis, config (JSON: arms human_only / ai_only / human_ai, models, prompts, parameters), dataset_version, criteria_version, prompt_versions, status, metrics (JSON), started_at, finished_at, created_by. **experiment_events** — id, experiment_id, event_type (screening_decision/ai_run/active_learning_round), payload (JSON), elapsed_ms, created_at. *Versioned, reproducible experiments (§71–74).*

## Key invariants

1. Decisions and extracted values are **append-only versioned** (`supersedes_id` chains); corrections never overwrite history (§97).
2. Every AI-influenced row carries `ai_run_id` → full reproducibility record (§49).
3. No cascade deletes on research data; deletion is an audited, explicit operation (§56).
4. Counts for PRISMA are always computed from rows, never stored by hand as truth.



# AI Architecture

Governing rule: **AI assists the researcher; AI does not replace the researcher.** Every design decision below serves traceability, reproducibility and human override (master prompt §114–118).

## 1. Provider abstraction (§50)

```
LLMProvider (Protocol)
├── complete(request: LLMRequest) -> LLMResponse     # supports structured output
├── embed(texts) -> vectors
├── healthcheck() -> bool
└── capabilities: {json_schema, streaming, vision, context_window}
```
Adapters: `OpenAIProvider`, `AnthropicProvider`, `GoogleProvider`, `LocalProvider` (Ollama / any OpenAI-compatible endpoint). Selected by env config — **no provider is hard-coded**; model choice per task (screening / extraction / synthesis / classification) is stored in project settings.

## 2. Task services (separate, never one generic AI function)

| Service | Responsibility | Output contract |
|---|---|---|
| `ScreeningService` | title/abstract + full-text eligibility | `ScreeningResult` (§3) |
| `ExtractionService` | field-level extraction | `ExtractionResult[]` (§4) |
| `QualityService` | risk-of-bias checks (leakage, baselines, stats…) | `QualityResult[]` |
| `ClassificationService` | taxonomy assignment | `ClassificationResult[]` |
| `SynthesisService` | drafts from *verified* data only | `SynthesisDraft` with claim→evidence links |
| `RetrievalService` | hybrid retrieval for all tasks | ranked `Passage[]` |
| `EvidenceService` | claim verification / contradiction detection | `VerificationResult` |

## 3. Structured output contracts (§68) — Pydantic, validated

```python
class CriterionResult(BaseModel):
    criterion_id: str
    decision: Literal["satisfied", "not_satisfied", "unclear", "not_applicable"]
    evidence: list[EvidenceRef]          # page, section, quote, span
    confidence: float                    # AI confidence score, NOT a probability
    rationale: str                       # concise, evidence-based; no chain-of-thought

class ScreeningResult(BaseModel):
    recommendation: Literal["include", "exclude", "unclear"]
    confidence: float
    criterion_results: list[CriterionResult]
    missing_information: list[str]
    reasoning_summary: str
```
Validation failure → one structured retry → log failure in `ai_runs.validation_status` → **never** accept malformed output and never mark a study screened on failure (§109).

## 4. Evidence-first prompting (§116)

Prompt assembly order: `TASK` → `RESEARCHER RULES (criteria/schema versions)` → `UNTRUSTED DOCUMENT EVIDENCE` → `OUTPUT JSON SCHEMA`. Document text is wrapped in delimiters and explicitly labelled untrusted; instructions inside papers are data, not commands (§86–87, see SECURITY.md). Prompts are rows in `prompts`/`prompt_versions` — the registry is the single source of truth (§67).

## 5. AI run record (`ai_runs`, §49)

provider, model, model_version, prompt_version_id, temperature, document_version_id, retrieved_passages, raw_output, parsed_output, validation_status, confidence, token_in/out, cost_usd, latency, timestamps + link to the human verdict (`ai_outputs.status`). This is the reproducibility backbone.

## 6. Retrieval (§115)

Hybrid: keyword (FTS/BM25) + vector similarity + metadata filters + section/page awareness. Section priority is task-dependent (screening → abstract, methods, results; extraction → methods/results/tables). Chunking preserves page boundaries so citations can deep-link into the PDF viewer. Never send whole documents when chunk retrieval suffices (§92).

## 7. Confidence & calibration (§70)

UI language: "AI confidence score". Stored raw; calibrated later against the gold-standard set (reliability diagrams, Brier score, ECE). Low confidence, conflicting criteria, or missing evidence ⇒ `unclear` + "Human review recommended" (§13, §118).

## 8. Hallucination controls (§69)

1. Evidence required — every claim carries `EvidenceRef` or status `not_reported`.
2. Retrieval grounding — answers built only from retrieved passages.
3. Explicit missing-information states: `reported / inferred / not_reported / unclear`.
4. Human verification gates every state change to *final*.
5. Contradiction detection compares claims against source and across studies (§38).
6. Synthesis only from `human_verified` extraction values; every sentence links to supporting studies (§40, §76, §82).

## 9. Agent permissions (§88)

Screening agent: read documents, write *recommendation* only — cannot set final decision. Extraction agent: write *draft* — cannot approve. Synthesis agent: read verified data — cannot modify source data. Enforced at the service layer (AI services receive read-only repositories and a narrow write interface).

## 10. Routing, caching, cost (§54, §55, §93)

Difficulty estimator (metadata completeness, criteria conflict, retrieval score spread) routes: easy → cheap/fast model; ambiguous → strong model; high-risk disagreement → human. Result cache keyed by (study, document_version, criteria_version, prompt_version, model) — unchanged inputs are never re-billed. Token/cost totals per stage surfaced in the dashboard.

## 11. Evaluation (§51–53, §103)

Gold-standard set (two independent experts → adjudicated) drives offline metrics: accuracy, precision, recall, F1, specificity, sensitivity, MCC, Cohen's kappa, calibration; false-exclusion rate is reported prominently and optimised against first (§122). Model comparison uses only human-verified ground truth. CI runs recorded fixtures — no live LLM calls.

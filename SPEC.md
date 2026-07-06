# GovAgent-IQ — System Specification

**An Enterprise GDPR Compliance & Risk-Mitigation Engine**

> Capstone — 5-Day AI Agents Intensive (Google × Kaggle). Track: *Agents for Business*.
> Spec-first by design: this document is the contract with the agents. Code is written *against* it.

---

## 1. Problem & value

Companies face fines up to 4% of global revenue when vendor contracts and internal
policies quietly drift out of line with GDPR. Legal review is slow, expensive, and
inconsistent. GovAgent-IQ ingests business documents, audits them against GDPR
obligations, and returns a triaged, evidence-backed risk report — autonomously.

**Who it's for:** compliance officers, legal ops, and procurement teams doing first-pass
contract/policy review.

---

## 2. Scope (deliberately narrow for a 4-day build)

| In scope | Out of scope |
|---|---|
| GDPR (EU data-privacy) obligations | CCPA, SOX, PCI-DSS, HIPAA |
| Vendor contracts + internal policies | Live legal-database subscriptions |
| Text documents (`.md` / `.txt`) | OCR of scanned PDFs, multi-language |
| First-pass risk flagging | Binding legal advice |

**Honest data disclosure (state this in the writeup):** GDPR obligations are represented
as a *real, structured ruleset* derived from the regulation and validated against *live web
search* for recent amendments. Company documents under audit are *realistic synthetic
samples* — mirroring how production compliance systems separate a stable regulatory
knowledge base from client-specific inputs.

---

## 3. Architecture — a 3-agent graph

```
Documents ─► [1. Ingestion] ─► [2. Auditor] ─► [3. Risk Assessor] ─► Compliance Report
                                    ▲
                    ┌───────────────┼───────────────┐
                    │               │               │
            GDPR ruleset      Live web search   Mock company DB
            (REAL, snapshot)  (REAL, amendments) (MOCK, ok to fake)
```

Each agent maps to a course day, which makes the technical rubric easy to score against.

---

## 4. Agent contracts

### Agent 1 — Ingestion & Parsing Specialist  *(Day 3: Context Engineering)*
- **Role:** Turn raw documents into token-optimized, compliance-relevant segments.
- **Input:** raw document text + document type hint (`contract` | `policy`).
- **Does:** classifies the doc, chunks it, summarizes each chunk into a dense segment,
  tags each segment with candidate GDPR topics, maintains session state across a batch.
- **Output:** `List[Segment]` (schema §5).
- **Model:** `gemini-2.0-flash` — high volume, cheap (model routing, Day 5 economics).
- **Why it exists:** keeps the Auditor from blowing the token budget on full documents.

### Agent 2 — The Auditor  *(Day 2: Tools & MCP)*
- **Role:** Decide, per segment, whether GDPR obligations are met.
- **Input:** `List[Segment]`.
- **Tools:**
  - `retrieve_gdpr_rules(topic)` → pulls relevant obligations from the snapshot ruleset.
  - `check_recent_amendments(query)` → **live web search** for changes/enforcement.
  - `query_company_db(entity)` → **mock** lookup of processor/DPA registry.
- **Output:** `List[RawFinding]` (schema §5) — *pre-judgment*.
- **Model:** `gemini-2.0-flash` (upgrade the reasoning step to a pro model if budget allows).
- **Why it exists:** this is the reasoning core; tools make its claims grounded, not guessed.

### Agent 3 — Risk Assessor  *(Day 4: Security, Guardrails, LLM-as-Judge)*
- **Role:** Validate the Auditor's findings and prevent hallucinations.
- **Input:** `List[RawFinding]`.
- **Does (as an LLM-as-judge):** checks every finding is backed by quoted evidence,
  assigns severity + confidence, overturns unsupported claims, computes an overall
  risk score.
- **Guardrails (deterministic, run in code — not left to the model):**
  - Reject any finding whose `evidence` is empty or not present in the source doc.
  - Drop findings with `confidence < 0.6` into `needs_review`, never `violation`.
  - Refuse to output legal advice phrased as certainty ("you must" → "consider").
- **Output:** `ComplianceReport` (schema §5).
- **Model:** `gemini-2.0-flash`.
- **Why it exists:** a fluent-but-wrong compliance finding is worse than none. The judge
  is the difference between "vibe coding" and "agentic engineering."

---

## 5. Data contracts (the schemas everything speaks)

```jsonc
// Segment — output of Agent 1
{
  "segment_id": "S-001",
  "document": "vendor_contract_acme.md",
  "doc_type": "contract",
  "text": "…dense summary of the relevant clause…",
  "topic_tags": ["processor_agreement", "international_transfer"]
}

// RawFinding — output of Agent 2 (before judging)
{
  "finding_id": "F-001",
  "segment_id": "S-001",
  "regulation": "GDPR Art. 28",
  "obligation": "processor_agreement_clauses",
  "status": "violation",            // violation | compliant | needs_review
  "evidence": "exact text located in the document",
  "explanation": "why this is a risk",
  "recommendation": "how to fix it",
  "confidence": 0.0
}

// ComplianceReport — output of Agent 3 (final)
{
  "overall_risk_score": 0.0,        // 0 (clean) → 1 (severe)
  "documents_reviewed": 2,
  "findings": [ /* validated RawFinding + fields below */ 
    {
      "…": "…all RawFinding fields…",
      "severity": "high",           // high | medium | low
      "judge_verdict": "upheld"     // upheld | overturned | flagged_hallucination
    }
  ]
}
```

A single structured schema is what lets Streamlit render cleanly **and** lets the eval
suite score deterministically. It is a first-class design decision, not an afterthought.

---

## 6. Tools spec

| Tool | Type | Source | Notes |
|---|---|---|---|
| `retrieve_gdpr_rules` | Retrieval | `data/regulations/gdpr_rules.json` | Real, structured obligations |
| `check_recent_amendments` | Web search | `google_search` (from Day 1!) | Real, live — proves "up-to-date" |
| `query_company_db` | Lookup | `data/mock/company_registry.json` | Mock — clearly disclosed |

`check_recent_amendments` reuses the exact `google_search` tool from the Day 1 codelab,
so no new integration risk.

---

## 7. Evaluation (Day 4 — write these before the code)

**Golden set:** ~6 planted findings across the sample documents (known violations +
known-compliant clauses + one ambiguous case).

| Metric | What it measures | Target |
|---|---|---|
| Recall on planted violations | Does the Auditor catch known issues? | ≥ 5/6 |
| Hallucination rate | Findings with no real evidence, caught by the judge | 0 shipped |
| Judge agreement | Judge verdict vs. human label | ≥ 80% |
| Trajectory | Did each agent call its expected tools? | 100% |

Evals live in `src/govagent/evals/` and run before every "ship."

---

## 8. Deployment

- **Frontend:** Streamlit (`app.py`) — thin UI, zero agent logic. Upload docs → run graph
  → render `ComplianceReport` as a triaged table + risk gauge.
- **Target:** Cloud Run (containerized Streamlit). Gives a live URL for the demo video and
  satisfies Day 5's production criterion.
- **Secrets:** `GOOGLE_API_KEY` via env var / Cloud Run secret. Never committed.

---

## 9. Success criteria (definition of done)

1. Upload 2 documents → get a valid `ComplianceReport` end-to-end.
2. At least one real GDPR violation caught with correct evidence.
3. The judge overturns at least one unsupported finding on the golden set.
4. Live amendment check returns a real, recent web result.
5. Deployed to a public Cloud Run URL.
6. Kaggle writeup + < 3-min video + public code link.

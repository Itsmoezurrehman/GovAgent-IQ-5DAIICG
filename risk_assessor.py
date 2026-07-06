"""Agent 3 — The Risk Assessor (LLM-as-judge + deterministic guardrails).

Maps to Day 4 (Security, Guardrails, LLM-as-Judge): the final node validates the
Auditor's findings, catches hallucinations, and produces the `ComplianceReport`.

Two layers:
1. Deterministic guardrails run in pure Python via a `before_agent_callback` — grounding
   (evidence must appear in the source) and a confidence floor (low-confidence violations
   are downgraded to needs_review). This never trusts the model to police itself.
2. The judge is an `LlmAgent` with `output_schema=ComplianceReport` and NO tools — with a
   schema set, ADK constrains it to emit clean, valid structured output.
"""

import json

from google.adk.agents import LlmAgent

from ..config import MODEL
from ..schemas import ComplianceReport
from ..tools.guardrails import apply_guardrails


def guardrail_callback(callback_context):
    """Deterministic pre-judge guardrails. Runs as the judge's before_agent_callback.

    Reads the Auditor's JSON-string output and the source document from session state,
    annotates each finding with `grounding_ok`, enforces the confidence floor, and writes
    the annotated list back to state under `guarded_findings`. Returns None so the judge
    agent proceeds normally.
    """
    state = callback_context.state

    raw = state.get("auditor_output")
    findings: list[dict] = []
    if raw:
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
            findings = parsed.get("findings", []) if isinstance(parsed, dict) else []
        except (json.JSONDecodeError, TypeError, AttributeError):
            # Malformed auditor output — proceed with no findings rather than crash.
            findings = []

    source_text = state.get("source_documents", "") or ""
    guarded = apply_guardrails(findings, source_text)

    # Store as a JSON string so instruction templating renders clean JSON for the model.
    state["guarded_findings"] = json.dumps(guarded, indent=2)
    return None


JUDGE_INSTRUCTION = """
You are the Risk Assessor — an LLM-as-judge in a GDPR compliance pipeline. Deterministic
guardrails have already run in code. Your job is to validate each finding, catch
hallucinations, assign severity, and compute an overall risk score.

## Input
Read the annotated findings from session state here:
{guarded_findings}

This is a JSON list. Each finding has all the original fields (`finding_id`, `segment_id`,
`regulation`, `obligation`, `status`, `evidence`, `explanation`, `recommendation`,
`confidence`) PLUS a boolean `grounding_ok` added by the guardrails.

## Per-finding judgment
For each finding produce a validated finding that KEEPS every original field, and add:

1. `judge_verdict`:
   - If `grounding_ok` is false → "flagged_hallucination" (its evidence is not in the
     source document; it must not be trusted).
   - Otherwise, evaluate the finding against its own evidence and explanation:
     - "upheld" if the finding is well-supported and correct.
     - "overturned" if the evidence does not actually support the stated status.

2. `severity` ("high" | "medium" | "low"), based on the obligation's risk:
   - HIGH: processor agreements (Art. 28), international transfers (Art. 44-46),
     security (Art. 32).
   - MEDIUM: retention / storage limitation (Art. 5(1)(e)), data minimisation
     (Art. 5(1)(c)), breach notification (Art. 33).
   - LOW: everything else / compliant findings.

## Overall risk score
Compute `overall_risk_score` as a float in [0, 1], driven by the count and severity of
UPHELD violations only:
- 0.0 when there are no upheld violations (clean).
- Approaching 1.0 with multiple high-severity upheld violations.
- Findings that are compliant, overturned, or flagged_hallucination do NOT raise the score.

## Other fields
- `documents_reviewed`: the number of distinct source documents represented (here, 1).
- `findings`: the list of validated findings (every input finding, judged).

## Output — STRICT
Output ONLY a single JSON object matching the ComplianceReport schema. No markdown, no
code fences, no commentary.
""".strip()


risk_assessor_agent = LlmAgent(
    name="risk_assessor",
    model=MODEL,
    description=(
        "Validates the Auditor's findings with deterministic guardrails plus an "
        "LLM-as-judge, then emits the final ComplianceReport."
    ),
    instruction=JUDGE_INSTRUCTION,
    output_schema=ComplianceReport,
    output_key="compliance_report",
    before_agent_callback=guardrail_callback,
)

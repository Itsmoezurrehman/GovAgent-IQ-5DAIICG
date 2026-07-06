"""Agent 2 — The Auditor.

Maps to Day 2 (Tools & MCP): this is the reasoning core of the pipeline. It reads the
segments Agent 1 wrote to session state, then grounds every judgment with tools — the
structured GDPR ruleset, a mock company registry, and live web search for amendments.

ADK 2.0 constraints honored here:
- `google_search` is a built-in tool and cannot share a `tools=[...]` list with custom
  FunctionTools. We isolate it in a dedicated search specialist and expose that agent to
  the Auditor via `AgentTool` (the agent-as-tool pattern).
- We deliberately DO NOT set `output_schema` on the Auditor: doing so would disable tool
  use. Instead the instruction demands strict JSON output and we validate it in code
  against `AuditorOutput`.
"""

from google.adk.agents import LlmAgent
from google.adk.tools import AgentTool, FunctionTool, google_search

from ..config import MODEL
from ..tools import query_company_db, retrieve_gdpr_rules

# --- Search specialist: the ONLY place google_search lives -----------------------

amendment_search_agent = LlmAgent(
    name="amendment_search",
    model=MODEL,
    description=(
        "GDPR amendment search specialist — checks the live web for recent "
        "amendments or enforcement actions relevant to a regulation reference."
    ),
    instruction=(
        "You are a GDPR amendment search specialist. Given a regulation "
        "reference, search for recent amendments or enforcement actions and "
        "report concisely."
    ),
    tools=[google_search],  # ONLY google_search
)


# --- The Auditor -----------------------------------------------------------------

AUDITOR_INSTRUCTION = """
You are the Auditor in a GDPR compliance pipeline. Your job is to decide, per segment,
whether GDPR obligations are met, and to ground every judgment with your tools.

## Input
The Ingestion agent has placed the segments to audit in session state. Read them here:
{ingestion_output}

This is an object with a `segments` list. Each segment has: `segment_id`, `document`,
`doc_type`, `text`, and `topic_tags`.

## Procedure
For each segment:
1. For EACH tag in the segment's `topic_tags`, call `retrieve_gdpr_rules(topic=<tag>)`
   to pull the exact obligations that apply. Never guess what GDPR requires — look it up.
2. Compare the segment `text` against each retrieved rule. Decide a compliance `status`
   per obligation:
   - "violation"     — the clause clearly fails the obligation.
   - "compliant"     — the clause clearly satisfies it.
   - "needs_review"  — genuinely ambiguous or insufficient information.
3. When a segment names a vendor/processor, you MAY call `query_company_db(entity=<name>)`
   to check its DPA status, data location, and retention policy as supporting evidence.
4. For a material regulation reference (e.g. "GDPR Art. 28"), you MAY call the
   `amendment_search` tool to confirm nothing recent changes your assessment.

## Evidence
For each finding, `evidence` MUST be exact text quoted from the segment's `text` — never
paraphrase or invent it. If you cannot locate supporting text, do not raise a violation.

## Output — STRICT
Output ONLY a single JSON object. No markdown, no code fences, no commentary. It must
match exactly:

{
  "findings": [
    {
      "finding_id": "F-001",
      "segment_id": "S-001",
      "regulation": "GDPR Art. 28",
      "obligation": "processor_agreement_clauses",
      "status": "violation",
      "evidence": "exact text quoted from the segment",
      "explanation": "why this is or is not a risk",
      "recommendation": "concrete fix",
      "confidence": 0.0
    }
  ]
}

Rules for the fields:
- `finding_id`: sequential — F-001, F-002, ...
- `segment_id`: the id of the segment the finding came from.
- `status`: one of "violation", "compliant", "needs_review".
- `confidence`: a float from 0.0 to 1.0.
- Produce at least one finding per segment that has applicable rules.
Emit the JSON object and nothing else.
""".strip()


auditor_agent = LlmAgent(
    name="auditor",
    model=MODEL,
    description=(
        "Audits ingested compliance segments against the GDPR ruleset and grounds "
        "each finding with retrieval, a company registry, and live amendment search."
    ),
    instruction=AUDITOR_INSTRUCTION,
    tools=[
        FunctionTool(retrieve_gdpr_rules),
        FunctionTool(query_company_db),
        AgentTool(agent=amendment_search_agent),
    ],
    output_key="auditor_output",
    # NO output_schema — that would disable tool use.
)

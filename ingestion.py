"""Agent 1 — Ingestion & Parsing Specialist.

Maps to Day 3 (Context Engineering): it compresses long compliance documents into
dense, token-optimized segments so downstream agents never see raw boilerplate.

ADK 2.0 note: because we set `output_schema`, this agent is constrained to emit valid
`IngestionOutput` JSON and cannot call tools or transfer control — exactly what we want
for a clean, deterministic first node in the SequentialAgent graph.
"""

from google.adk.agents import LlmAgent

from ..config import MODEL
from ..schemas import IngestionOutput

# Canonical GDPR topic tags the Auditor knows how to look up. Keeping this list here
# (static context) keeps Agent 1's tagging aligned with the ruleset in
# data/regulations/gdpr_rules.json.
KNOWN_TOPICS = [
    "processor_agreement",
    "lawful_basis",
    "international_transfer",
    "data_minimisation",
    "retention",
    "security",
    "breach_notification",
]

INGESTION_INSTRUCTION = f"""
You are the Ingestion & Parsing Specialist in a GDPR compliance pipeline.

You receive ONE document. The first line of the user message is a hint like
`doc_type: contract` or `doc_type: policy`. The rest is the document body.

Your job:
1. Read the whole document.
2. Extract ONLY clauses that could be relevant to GDPR compliance (data handling,
   retention, transfers, security, breach, lawful basis, processor duties).
   Ignore pure boilerplate (signatures, service-availability language, governing law
   unless it affects data location).
3. For each relevant clause, write a DENSE summary segment — capture the compliance
   substance in as few tokens as possible. Do not copy the clause verbatim; compress it.
4. Tag each segment with one or more topics from this exact list:
   {KNOWN_TOPICS}
   Only use tags from that list. If a clause spans several topics, include all that apply.
5. Assign sequential ids: S-001, S-002, ...

Return your answer strictly as the required JSON schema. Do not add commentary.
""".strip()


ingestion_agent = LlmAgent(
    name="ingestion_specialist",
    model=MODEL,
    description=(
        "Parses a compliance document and compresses it into token-optimized, "
        "GDPR-relevant segments."
    ),
    instruction=INGESTION_INSTRUCTION,
    output_schema=IngestionOutput,
    # Writes the result into session state so Agent 2 (the Auditor) can read it.
    output_key="ingestion_output",
)

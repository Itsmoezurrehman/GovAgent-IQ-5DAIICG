"""Reusable end-to-end pipeline: ingestion → auditor → risk assessor.

This is the single entry point the Streamlit UI (and any script) uses to run the whole
three-agent graph and get back a validated `ComplianceReport`. It contains NO agent logic
of its own — it only wires the existing agents together and runs them.
"""

import json

from google.adk.agents import SequentialAgent
from google.adk.runners import Runner
from google.adk.sessions import BaseSessionService
from google.genai import types

from .agents import auditor_agent, ingestion_agent, risk_assessor_agent
from .schemas import ComplianceReport

APP_NAME = "govagent_iq"
USER_ID = "streamlit_user"


def build_pipeline() -> SequentialAgent:
    """Assemble the full three-agent sequential pipeline.

    IMPORTANT: this is the ONLY place a SequentialAgent is constructed. ADK sets each
    sub-agent's `parent_agent` at construction and raises "already has a parent" if the
    same sub-agent is placed in a second SequentialAgent. Because the sub-agents are
    module-level singletons, this must be called exactly once per process (the caller is
    responsible for caching — e.g. Streamlit's @st.cache_resource). `run_audit` never
    builds a pipeline; it takes an existing Runner instead.
    """
    return SequentialAgent(
        name="full_pipeline",
        sub_agents=[ingestion_agent, auditor_agent, risk_assessor_agent],
    )


def _strip_code_fences(text: str) -> str:
    """Peel ```json fences the model may add despite instructions."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[1] if "\n" in stripped else stripped
        if stripped.endswith("```"):
            stripped = stripped[: stripped.rfind("```")]
    return stripped.strip()


async def run_audit(
    runner: Runner,
    session_service: BaseSessionService,
    doc_text: str,
    doc_type: str,
) -> ComplianceReport:
    """Run the full pipeline on one document and return a validated ComplianceReport.

    Takes an already-built `runner` (wrapping the single cached SequentialAgent) and its
    `session_service`; it never constructs a pipeline itself, so the "already has a parent"
    error cannot occur on Streamlit reruns. A fresh session is created per call and seeded
    with `source_documents` so Agent 3's grounding guardrail can verify each finding's
    evidence against the real source text.

    Raises:
        RuntimeError: if the pipeline produced no report, or the output failed schema
            validation — with a message the UI can surface directly.
    """
    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        state={"source_documents": doc_text},
    )

    message = types.Content(
        role="user",
        parts=[types.Part(text=f"doc_type: {doc_type}\n\n{doc_text}")],
    )

    final_report_text: str | None = None
    async for event in runner.run_async(
        user_id=USER_ID, session_id=session.id, new_message=message
    ):
        if (
            event.is_final_response()
            and event.author == "risk_assessor"
            and event.content
            and event.content.parts
        ):
            final_report_text = event.content.parts[0].text

    # Fall back to session state if the final event text wasn't captured.
    if not final_report_text:
        final_session = await session_service.get_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=session.id
        )
        report_raw = final_session.state.get("compliance_report")
        if report_raw:
            final_report_text = (
                report_raw if isinstance(report_raw, str) else json.dumps(report_raw)
            )

    if not final_report_text:
        raise RuntimeError(
            "The pipeline did not produce a compliance report. "
            "Check that GOOGLE_API_KEY is set and the model is reachable."
        )

    raw = _strip_code_fences(final_report_text)
    try:
        return ComplianceReport.model_validate_json(raw)
    except Exception as exc:  # pydantic ValidationError or JSON error
        raise RuntimeError(
            f"The pipeline returned output that did not match the ComplianceReport "
            f"schema: {exc}"
        ) from exc

"""Full-pipeline test: ingestion → auditor → risk assessor (Agents 1 + 2 + 3).

Run from the project root:
    uv run python scripts/test_risk_assessor.py

Requires GOOGLE_API_KEY in your .env. Seeds session state with the raw source document
so Agent 3's deterministic grounding guardrail can verify each finding's evidence, then
runs the whole graph and validates the final ComplianceReport.
"""

import asyncio
import json
import sys
from pathlib import Path

# Windows consoles default to cp1252, which can't encode the arrows/emoji below.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Verify TLS against the OS trust store when available. On machines where an
# antivirus/proxy intercepts HTTPS (e.g. AVG Web Shield), its root CA lives in the
# system store but not in certifi, so certifi-based verification fails. truststore
# degrades gracefully to normal verification everywhere else.
try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass

from dotenv import load_dotenv
from google.adk.agents import SequentialAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from govagent.agents import auditor_agent, ingestion_agent, risk_assessor_agent
from govagent.schemas import ComplianceReport

load_dotenv()

APP_NAME = "govagent_iq"
USER_ID = "dev_user"
SAMPLE_DOC = Path("data/mock_contracts/vendor_contract_acme.md")


def _strip_code_fences(text: str) -> str:
    """Models sometimes wrap JSON in ```json fences despite instructions; peel them."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[1] if "\n" in stripped else stripped
        if stripped.endswith("```"):
            stripped = stripped[: stripped.rfind("```")]
    return stripped.strip()


async def main() -> None:
    doc_text = SAMPLE_DOC.read_text(encoding="utf-8")

    full_pipeline = SequentialAgent(
        name="full_pipeline",
        sub_agents=[ingestion_agent, auditor_agent, risk_assessor_agent],
    )

    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        # Seed the source text so the grounding guardrail can verify evidence.
        state={"source_documents": doc_text},
    )
    runner = Runner(
        agent=full_pipeline,
        app_name=APP_NAME,
        session_service=session_service,
    )

    message = types.Content(
        role="user",
        parts=[types.Part(text=f"doc_type: contract\n\n{doc_text}")],
    )

    print(f"Running full pipeline on {SAMPLE_DOC.name} ...\n")
    async for event in runner.run_async(
        user_id=USER_ID, session_id=session.id, new_message=message
    ):
        if event.is_final_response() and event.content and event.author:
            print(f"[{event.author}] produced final response.")

    final_session = await session_service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=session.id
    )
    report_raw = final_session.state.get("compliance_report")
    if not report_raw:
        print("No compliance_report in session state. Check your API key and model access.")
        return

    raw = report_raw if isinstance(report_raw, str) else json.dumps(report_raw)
    raw = _strip_code_fences(raw)

    print("\n=== Raw compliance_report ===")
    print(raw)

    report = ComplianceReport.model_validate_json(raw)
    print(
        f"\n✅ Validated ComplianceReport — risk score {report.overall_risk_score}, "
        f"{report.documents_reviewed} document(s), {len(report.findings)} findings.\n"
    )

    for f in report.findings:
        print(
            f"  [{f.judge_verdict:20}] sev={f.severity:6} {f.status:13} "
            f"{f.regulation:16} {f.obligation}"
        )


if __name__ == "__main__":
    asyncio.run(main())

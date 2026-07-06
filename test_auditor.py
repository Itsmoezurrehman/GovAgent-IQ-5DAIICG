"""Smoke-test the ingestion → auditor pipeline (Agents 1 + 2).

Run from the project root:
    uv run python scripts/test_auditor.py

Requires GOOGLE_API_KEY in your .env (copied from .env.example). Builds a
SequentialAgent so Agent 1 writes `ingestion_output` to session state and Agent 2
(the Auditor) reads it, then prints and validates the Auditor's JSON findings.
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

from govagent.agents import auditor_agent, ingestion_agent
from govagent.schemas import AuditorOutput

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
    audit_pipeline = SequentialAgent(
        name="audit_pipeline",
        sub_agents=[ingestion_agent, auditor_agent],
    )

    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, state={}
    )
    runner = Runner(
        agent=audit_pipeline,
        app_name=APP_NAME,
        session_service=session_service,
    )

    doc_text = SAMPLE_DOC.read_text(encoding="utf-8")
    message = types.Content(
        role="user",
        parts=[types.Part(text=f"doc_type: contract\n\n{doc_text}")],
    )

    print(f"Auditing {SAMPLE_DOC.name} through ingestion → auditor ...\n")
    async for event in runner.run_async(
        user_id=USER_ID, session_id=session.id, new_message=message
    ):
        if event.is_final_response() and event.content and event.author:
            print(f"[{event.author}] produced final response.")

    # Read the Auditor's output from session state (set via output_key).
    final_session = await session_service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=session.id
    )
    auditor_output = final_session.state.get("auditor_output")
    if not auditor_output:
        print("No auditor_output in session state. Check your API key and model access.")
        return

    raw = auditor_output if isinstance(auditor_output, str) else json.dumps(auditor_output)
    raw = _strip_code_fences(raw)

    print("\n=== Raw auditor_output ===")
    print(raw)

    # Validate against the shared data contract.
    result = AuditorOutput.model_validate_json(raw)
    print(f"\n✅ Validated AuditorOutput with {len(result.findings)} findings.\n")

    for f in result.findings:
        print(f"  [{f.status.upper():13}] {f.regulation:16} {f.obligation}")
        print(f"      evidence: {f.evidence[:90]}")
        print(f"      confidence: {f.confidence}")


if __name__ == "__main__":
    asyncio.run(main())

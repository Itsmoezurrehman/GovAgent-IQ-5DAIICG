"""Smoke-test Agent 1 (Ingestion) standalone.

Run from the project root:
    uv run python scripts/test_ingestion.py

Requires GOOGLE_API_KEY in your .env (copied from .env.example).
"""

import asyncio
import json
from pathlib import Path

from dotenv import load_dotenv
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from govagent.agents import ingestion_agent

load_dotenv()

APP_NAME = "govagent_iq"
USER_ID = "dev_user"
SAMPLE_DOC = Path("data/mock_contracts/vendor_contract_acme.md")


async def main() -> None:
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, state={}
    )
    runner = Runner(
        agent=ingestion_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )

    doc_text = SAMPLE_DOC.read_text(encoding="utf-8")
    message = types.Content(
        role="user",
        parts=[types.Part(text=f"doc_type: contract\n\n{doc_text}")],
    )

    print(f"Ingesting {SAMPLE_DOC.name} ...\n")
    final_text = None
    async for event in runner.run_async(
        user_id=USER_ID, session_id=session.id, new_message=message
    ):
        if event.is_final_response() and event.content:
            final_text = event.content.parts[0].text

    if not final_text:
        print("No final response produced. Check your API key and model access.")
        return

    # Pretty-print the structured segments so you can eyeball the compression.
    parsed = json.loads(final_text)
    print(json.dumps(parsed, indent=2))
    print(f"\n✅ Produced {len(parsed['segments'])} segments.")


if __name__ == "__main__":
    asyncio.run(main())

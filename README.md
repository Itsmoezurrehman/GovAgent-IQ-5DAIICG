# GovAgent-IQ

An enterprise **GDPR compliance & risk-mitigation engine** — a 3-agent ADK 2.0 graph that
ingests business documents, audits them against GDPR obligations, and returns an
evidence-backed risk report.

See [`SPEC.md`](./SPEC.md) for the full system specification.

## Architecture

```
Documents ─► [1. Ingestion] ─► [2. Auditor] ─► [3. Risk Assessor] ─► Compliance Report
```

| Agent | Course day | Role |
|---|---|---|
| Ingestion | Day 3 (Context) | Compress docs into token-optimized segments |
| Auditor | Day 2 (Tools/MCP) | Check segments against GDPR rules + live search |
| Risk Assessor | Day 4 (Guardrails) | LLM-as-judge validation, prevent hallucinations |

## Setup

```bash
# 1. Install uv if you don't have it (https://docs.astral.sh/uv/)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Create the env and install deps
uv sync

# 3. Configure your API key
cp .env.example .env
#    then edit .env and paste your Gemini key from https://aistudio.google.com/app/apikey

# 4. (Optional) Install the Agents CLI toolchain for scaffold/eval/deploy
uvx google-agents-cli setup
```

## Run

```bash
# Smoke-test Agent 1 (Ingestion) against the sample contract
uv run python scripts/test_ingestion.py
```

## Project layout

```
govagent-iq/
├── SPEC.md                     # spec-driven-development contract
├── pyproject.toml              # uv deps
├── .env.example
├── data/
│   ├── regulations/gdpr_rules.json      # REAL structured GDPR obligations
│   └── mock_contracts/                  # synthetic test documents
├── src/govagent/
│   ├── schemas.py              # shared Pydantic data contracts
│   └── agents/ingestion.py     # Agent 1 (built)
├── scripts/test_ingestion.py   # standalone smoke test
└── app.py                      # Streamlit UI (coming Day 5 stage)
```

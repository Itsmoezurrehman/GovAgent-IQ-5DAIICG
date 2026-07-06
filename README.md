# GovAgent-IQ

An agentic GDPR (General Data Protection Regulation) compliance reviewer. Upload a company privacy or data-protection policy document
and get back a graded compliance report. Findings are tied to specific GDPR articles, each
with a risk level, justification and even the evidence it was based on.

It is built for the Agents for Business track of the 5-Day AI Agents Intensive (Google | Kaggle) course using Google's Agent Development Kit (ADK) 2.0 and Gemini 2.5 Flash.

Live app link: https://govagent-iq-576364730473.us-central1.run.app

## What it does:

A human compliance reviewer usually reads a policy, checks it against GDPR, looks for
recent changes to the regulation and writes up the gaps. GovAgent-IQ does that first
pass automatically so the reviewer starts from a draft instead of raw text.

## How does it work:

The system is an ADK `SequentialAgent` with three agents that run in order.

1. Ingestion: An `LlmAgent` with an `output_schema` reads the uploaded document and
   compresses it into GDPR-tagged segments so later steps reason over relevant chunks
   instead of the whole document.

2. Auditor: Reasons over the segments using custom tools (`retrieve_gdpr_rules`,
   `query_company_db`) and a live web search for recent amendments. Because ADK doesn't
   allow a built-in search tool alongside custom tools in the same agent, the search runs
   in its own sub-agent that the auditor calls as a tool.

3. Risk assessor: A `before_agent_callback` runs a deterministic check that every finding
   is grounded in evidence and clears a confidence floor. What passes goes to an
   LLM-as-a-judge that grades severity and writes the final `ComplianceReport`.

A Streamlit UI (`app.py`) wraps a decoupled `pipeline.py`. `Dockerfile` handles the deployement of app to Cloud Run.

## Tech stack involved:

- Google ADK 2.0
- Gemini 2.5 Flash via the Gemini API
- Streamlit for the UI
- Docker and Google Cloud Run for deployment
- uv for Python environment and dependency management

## Repository layout

```
config.py        # model name and shared settings, referenced by every agent
pipeline.py      # builds and runs the three-agent pipeline
app.py           # Streamlit UI
agents/          # the three agents and their tools
Dockerfile       # Cloud Run build
pyproject.toml   # dependencies
SPEC.md          # the spec written before any agent code
```

## To run it locally:

You need Python 3.11 or newer, `uv`and a Gemini API key.

1. Clone and enter the project:

   ```
   git clone https://github.com/[your-github-username]/govagent-iq.git
   cd govagent-iq
   ```

2. Create the environment and install these dependencies:

   ```
   uv venv
   uv sync
   ```

3. Setup your API key. Create a `.env` file in the project root:

   ```
   GEMINI_API_KEY=your_key_here
   ```

   Do not commit `.env`. It's already in `.gitignore`.

4. Run the app:

   ```
   uv run streamlit run app.py
   ```

   The app opens in your browser. Upload a policy document and start the audit. A sample
   policy is included for testing.

## Notes:

- The model name is centralized in `config.py`. If Google retires the current model,
  changing it in one place updates the whole pipeline.
- If your antivirus intercepts TLS, install `truststore` so the app can reach the Gemini
  API.
- On Windows, zip the contents of the project folder rather than the folder itself before
  uploading to Cloud Shell or the nested folder structure can cause Cloud Run to skip the
  Dockerfile.

## Scope:

The GDPR rule set is a curated snapshot rather than the full corpus, and the company
records database is synthetic. The report is a first pass and is meant to be reviewed by a
person and not to be treated as a final compliance decision.

"""GovAgent-IQ — Streamlit UI.

A THIN layer over the three-agent pipeline (see SPEC.md section 8). It collects a document,
runs the existing ingestion → auditor → risk-assessor graph and renders the resulting
ComplianceReport as a risk gauge, summary metrics, severity chart and per-finding cards.
No agent logic lives here.
"""

# TLS + env setup: must run before any Gemini call
import truststore

truststore.inject_into_ssl()  # trust the OS cert store (fixes AVG/proxy TLS interception)

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv

load_dotenv()  # GOOGLE_API_KEY stays in the environment, never hardcoded

# Regular imports
import asyncio
import json
from collections import Counter
from pathlib import Path

import pandas as pd
import streamlit as st
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from govagent.pipeline import APP_NAME, build_pipeline, run_audit

SAMPLE_DIR = Path("data/mock_contracts")

# Page config
st.set_page_config(page_title="GovAgent-IQ", page_icon="🛡️", layout="wide")


@st.cache_resource
def get_runner():
    """Build the SequentialAgent AND its Runner exactly once for the whole app process.

    ADK agents can hold only one parent, so the pipeline must never be rebuilt across
    Streamlit reruns. @st.cache_resource guarantees this body runs a single time; every
    audit reuses the same runner + session_service (a fresh session is made per audit).
    """
    session_service = InMemorySessionService()
    runner = Runner(
        agent=build_pipeline(),  # the ONLY SequentialAgent construction in the process
        app_name=APP_NAME,
        session_service=session_service,
    )
    return runner, session_service


runner, session_service = get_runner()

st.title("GovAgent-IQ 🛡️")
st.caption("Enterprise GDPR Compliance & Risk-Mitigation Engine")

# Color maps for badges
STATUS_COLORS = {"violation": "#d64545", "needs_review": "#d9a441", "compliant": "#3f9142"}
VERDICT_COLORS = {
    "upheld": "#3f9142",
    "overturned": "#7a7a7a",
    "flagged_hallucination": "#d64545",
}
SEVERITY_ORDER = ["high", "medium", "low"]
SEVERITY_COLORS = {"high": "#d64545", "medium": "#d9a441", "low": "#3f9142"}


def badge(text: str, color: str) -> str:
    """Small inline HTML badge."""
    return (
        f"<span style='background:{color};color:white;padding:2px 8px;"
        f"border-radius:6px;font-size:0.8em;font-weight:600;'>{text}</span>"
    )


# Input area (sidebar)
with st.sidebar:
    st.header("Document")
    source = st.radio(
        "Source", ["Sample document", "Upload", "Paste text"], index=0
    )

    doc_text = ""
    doc_name = "document"

    if source == "Sample document":
        samples = sorted(p.name for p in SAMPLE_DIR.glob("*.*"))
        if samples:
            choice = st.selectbox("Sample", samples)
            doc_name = choice
            doc_text = (SAMPLE_DIR / choice).read_text(encoding="utf-8")
        else:
            st.warning(f"No files found in {SAMPLE_DIR}/")

    elif source == "Upload":
        uploaded = st.file_uploader("Upload a document", type=["md", "txt"])
        if uploaded is not None:
            doc_name = uploaded.name
            doc_text = uploaded.read().decode("utf-8", errors="replace")

    else:  # Paste text
        doc_text = st.text_area("Paste document text", height=260)
        doc_name = "pasted_text"

    doc_type = st.selectbox("Document type", ["contract", "policy"])

    run_clicked = st.button("Run compliance audit", type="primary", width="stretch")

    if doc_text.strip():
        with st.expander("Preview source text"):
            st.text(doc_text[:2000] + ("…" if len(doc_text) > 2000 else ""))

# Run the pipeline
if run_clicked:
    if not doc_text.strip():
        st.error("Please provide a document (sample, upload, or pasted text) first.")
    else:
        with st.spinner("Auditing… running ingestion → auditor → risk assessor"):
            try:
                report = asyncio.run(
                    run_audit(runner, session_service, doc_text, doc_type)
                )
                st.session_state["report"] = report.model_dump()
                st.session_state["report_name"] = doc_name
            except Exception as exc:
                st.session_state.pop("report", None)
                st.error(f"Audit failed: {exc}")

# Render the report
report = st.session_state.get("report")

if not report:
    st.info("Choose a document in the sidebar and click **Run compliance audit** to begin.")
else:
    findings = report["findings"]
    score = float(report["overall_risk_score"])

    # Risk gauge
    if score >= 0.7:
        risk_color, risk_label = "#d64545", "High risk"
    elif score >= 0.4:
        risk_color, risk_label = "#d9a441", "Medium risk"
    else:
        risk_color, risk_label = "#3f9142", "Low risk"

    st.subheader(f"Report — {st.session_state.get('report_name', '')}")
    st.markdown(
        f"""
        <div style='margin:0.25rem 0 0.5rem 0;'>
          <div style='display:flex;justify-content:space-between;font-weight:600;'>
            <span>Overall risk</span>
            <span style='color:{risk_color};'>{risk_label} — {score:.2f}</span>
          </div>
          <div style='background:#e6e6e6;border-radius:8px;height:22px;overflow:hidden;'>
            <div style='width:{score * 100:.0f}%;background:{risk_color};height:100%;'></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Summary metrics
    n_violations = sum(1 for f in findings if f["status"] == "violation")
    n_needs_review = sum(1 for f in findings if f["status"] == "needs_review")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Documents reviewed", report["documents_reviewed"])
    c2.metric("Total findings", len(findings))
    c3.metric("Violations", n_violations)
    c4.metric("Needs review", n_needs_review)

    # Severity bar chart 
    sev_counts = Counter(f["severity"] for f in findings)
    sev_df = pd.DataFrame(
        {"severity": SEVERITY_ORDER, "count": [sev_counts.get(s, 0) for s in SEVERITY_ORDER]}
    ).set_index("severity")
    st.markdown("**Findings by severity**")
    st.bar_chart(sev_df, height=200)

    # Per-finding cards
    st.markdown("### Findings")

    # Show most severe first.
    findings_sorted = sorted(
        findings, key=lambda f: SEVERITY_ORDER.index(f.get("severity", "low"))
    )
    for f in findings_sorted:
        title = f"[{f['severity'].upper()}] {f['obligation']} — {f['regulation']}"
        with st.expander(title):
            st.markdown(
                badge(f["status"], STATUS_COLORS.get(f["status"], "#7a7a7a"))
                + " "
                + badge(f["severity"], SEVERITY_COLORS.get(f["severity"], "#7a7a7a"))
                + " "
                + badge(f["judge_verdict"], VERDICT_COLORS.get(f["judge_verdict"], "#7a7a7a"))
                + f" &nbsp; <span style='color:#888;'>confidence: {f['confidence']:.2f}</span>",
                unsafe_allow_html=True,
            )
            st.markdown("**Evidence**")
            st.code(f["evidence"] or "(none)", language="text")
            st.markdown(f"**Explanation** — {f['explanation']}")
            st.markdown(f"**Recommendation** — {f['recommendation']}")

    # Download
    st.download_button(
        "⬇️ Download report (JSON)",
        data=json.dumps(report, indent=2),
        file_name=f"compliance_report_{st.session_state.get('report_name', 'doc')}.json",
        mime="application/json",
    )

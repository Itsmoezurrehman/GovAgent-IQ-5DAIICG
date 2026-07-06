"""Data contracts shared across the GovAgent-IQ agent graph (see SPEC.md section 5)."""

from typing import Literal
from pydantic import BaseModel, Field

# --- Agent 1: Ingestion output -------------------------------------------------


class Segment(BaseModel):
    """A token-optimized, compliance-relevant slice of a source document."""

    segment_id: str = Field(description="Stable id, e.g. 'S-001'.")
    document: str = Field(description="Source filename.")
    doc_type: Literal["contract", "policy"]
    text: str = Field(description="Dense summary of the relevant clause(s).")
    topic_tags: list[str] = Field(
        description="Candidate GDPR topics, e.g. ['processor_agreement', 'retention']."
    )


class IngestionOutput(BaseModel):
    """Root object Agent 1 writes to session state under `ingestion_output`."""

    segments: list[Segment]


# --- Agent 2: Auditor output ---------------------------------------------------


class RawFinding(BaseModel):
    """A pre-judgment compliance finding produced by the Auditor."""

    finding_id: str
    segment_id: str
    regulation: str = Field(description="e.g. 'GDPR Art. 28'.")
    obligation: str
    status: Literal["violation", "compliant", "needs_review"]
    evidence: str = Field(description="Exact text located in the source document.")
    explanation: str
    recommendation: str
    confidence: float = Field(ge=0.0, le=1.0)


class AuditorOutput(BaseModel):
    findings: list[RawFinding]


# --- Agent 3: Risk Assessor (final report) -------------------------------------


class ValidatedFinding(RawFinding):
    severity: Literal["high", "medium", "low"]
    judge_verdict: Literal["upheld", "overturned", "flagged_hallucination"]


class ComplianceReport(BaseModel):
    overall_risk_score: float = Field(ge=0.0, le=1.0)
    documents_reviewed: int
    findings: list[ValidatedFinding]

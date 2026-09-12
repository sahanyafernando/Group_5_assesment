"""Claude request/response contracts.

Claude is a language-understanding component only. Nothing here carries a
priority score, a crew, or a dispatch decision (CLAUDE.md section 5).
"""

from pydantic import BaseModel, Field

from app.schemas.common import Severity


class ReportAnalysisRequest(BaseModel):
    report_id: str | None = None
    description: str
    location_text: str | None = None
    category: str | None = None
    urgency: str | None = None


class LocationHint(BaseModel):
    """A hint only. assets.csv remains the authority on whether a road exists."""

    road_hint: str | None = None
    landmark: str | None = None


class ReportAnalysis(BaseModel):
    work_type: str
    category: str | None = None
    incident_title: str
    incident_summary: str
    location: LocationHint = LocationHint()
    severity: Severity
    hazards: list[str] = []
    impact: list[str] = []
    confidence: float = Field(ge=0, le=1)
    needs_review: bool


class IncidentInsight(BaseModel):
    """An on-demand Claude read of one incident: what it is, and what a
    coordinator might want to check before acting on it.

    Advisory only - recommended_actions are suggestions to consider, never a
    crew, priority, or dispatch decision (CLAUDE.md section 5). The
    coordinator's own assign/override actions are the only real decisions.
    """

    summary: str
    recommended_actions: list[str] = []
    generated_at: str
    insight_error: str | None = None

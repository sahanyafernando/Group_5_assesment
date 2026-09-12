from typing import Literal

from pydantic import BaseModel, Field


CrewName = Literal[
    "Road Surface",
    "Drainage",
    "Lighting & Street Furniture",
    "Manual Review",
]


class PriorityReason(BaseModel):
    factor: str
    points: int
    reason: str


class Incident(BaseModel):
    id: str
    incident_code: str
    title: str
    summary: str | None = None
    canonical_road: str | None = None
    ward: str | None = None
    category: str | None = None
    work_type: str | None = None
    severity: str | None = None
    report_count: int = 1
    priority_score: int = Field(ge=0, le=100)
    priority_level: str
    priority_reasons: list[PriorityReason] = []
    required_crew: str
    status: str
    classification_confidence: float | None = None
    location_confidence: float | None = None
    needs_review: bool = False


class DashboardSummary(BaseModel):
    reports: int
    incidents: int
    high_or_critical: int
    needs_review: int


class ReportAnalysisRequest(BaseModel):
    report_id: str | None = None
    description: str
    location_text: str | None = None
    category: str | None = None
    urgency: str | None = None


class LocationHint(BaseModel):
    road_hint: str | None = None
    landmark: str | None = None


class ReportAnalysis(BaseModel):
    work_type: str
    category: str | None = None
    incident_title: str
    incident_summary: str
    location: LocationHint = LocationHint()
    severity: Literal["critical", "high", "medium", "low", "unknown"]
    hazards: list[str] = []
    impact: list[str] = []
    confidence: float = Field(ge=0, le=1)
    needs_review: bool

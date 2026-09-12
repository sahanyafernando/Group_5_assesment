"""Incident response models.

An incident is the consolidated unit of work: one or more resident reports
about the same underlying problem (DECISIONS.md D1).
"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.schemas.common import PriorityLevel
from app.schemas.report import ReportOut


class PriorityReason(BaseModel):
    """One scored factor plus the explanation for the points it added.

    CLAUDE.md section 8: every point added must produce an explanation string.
    """

    factor: str
    points: int
    reason: str

    @computed_field
    @property
    def label(self) -> str:
        """Single-line rendering, e.g. '+15 bus route'."""
        return f"+{self.points} {self.reason}"


class PriorityFactors(BaseModel):
    """Per-factor point totals, for showing the score breakdown as a bar/table.

    Ceilings come from CLAUDE.md section 8.
    """

    safety: int = Field(default=0, ge=0, le=35)
    road_impact: int = Field(default=0, ge=0, le=20)
    facility: int = Field(default=0, ge=0, le=15)
    persistence: int = Field(default=0, ge=0, le=15)
    report_count: int = Field(default=0, ge=0, le=10)
    urgency: int = Field(default=0, ge=0, le=5)

    @computed_field
    @property
    def total(self) -> int:
        return (
            self.safety
            + self.road_impact
            + self.facility
            + self.persistence
            + self.report_count
            + self.urgency
        )


class RecentJobWarning(BaseModel):
    """A possibly-related completed job.

    This is a warning for the coordinator, never an automatic closure
    (CLAUDE.md section 5).
    """

    model_config = ConfigDict(extra="ignore")

    job_id: str | None = None
    crew: str | None = None
    work_type: str | None = None
    road_name: str | None = None
    completed_date: date | None = None
    notes: str | None = None

    # Explainability (NFR-01): how old the job is, and the line shown to Maya.
    days_ago: int | None = None
    message: str | None = None


class IncidentOut(BaseModel):
    """An incident as shown in the ranked list."""

    model_config = ConfigDict(extra="ignore")

    id: str
    incident_code: str | None = None
    title: str
    summary: str | None = None

    # Location, resolved against assets.csv.
    canonical_road: str | None = None
    ward: str | None = None
    road_class: str | None = None
    asset_types: list[str] = []
    nearest_facility: str | None = None
    facility_distance_m: float | None = None

    # Classification. Kept as str, not WorkType, so an unexpected stored value
    # surfaces as a review item instead of a 500 on read.
    category: str | None = None
    work_type: str | None = None
    severity: str | None = None
    hazards: list[str] = []
    impact: list[str] = []

    # Deterministic outputs (crew_service / priority_service).
    required_crew: str = "Manual Review"
    priority_score: int = Field(default=0, ge=0, le=100)
    priority_level: PriorityLevel | str = "LOW"
    priority_reasons: list[PriorityReason] = []
    priority_factors: PriorityFactors | None = None

    # Volume and timing.
    report_count: int = Field(default=1, ge=1)
    first_reported_at: datetime | None = None
    latest_reported_at: datetime | None = None

    # Workflow and trust signals.
    status: str = "New"
    classification_confidence: float | None = Field(default=None, ge=0, le=1)
    location_confidence: float | None = Field(default=None, ge=0, le=1)
    needs_review: bool = False
    recent_job_warning: RecentJobWarning | None = None

    @field_validator("required_crew", "priority_level", mode="before")
    @classmethod
    def _coerce_stored_null(cls, value, info):
        """A stored row can have this column explicitly NULL (not merely
        absent), which bypasses the field's default - so it surfaces here
        as the literal value None. Map it to the same default the field
        already declares, matching the resilience pattern used above for
        work_type/category/severity: an incomplete row becomes a review
        item, not a 500 on read."""
        if value is not None:
            return value
        return "Manual Review" if info.field_name == "required_crew" else "LOW"


class IncidentDetail(IncidentOut):
    """An incident plus the raw reports behind it (REQUIREMENTS.md FR-18)."""

    source_reports: list[ReportOut] = []

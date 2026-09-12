"""Dashboard and dispatch-view response models."""

from pydantic import BaseModel, Field, computed_field

from app.schemas.incident import IncidentOut


class DashboardSummary(BaseModel):
    """Compact counts for the four summary cards.

    Kept as-is because the React SummaryCards component already consumes this
    shape from GET /api/dashboard/summary.
    """

    reports: int = 0
    incidents: int = 0
    high_or_critical: int = 0
    needs_review: int = 0


class DashboardStats(BaseModel):
    """Fuller statistics for GET /api/stats, including breakdowns."""

    total_reports: int = 0
    total_incidents: int = 0
    high_priority_count: int = 0
    needs_review_count: int = 0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_crew: dict[str, int] = Field(default_factory=dict)


class DispatchQueue(BaseModel):
    """One crew's queue, already sorted by priority."""

    crew: str
    incidents: list[IncidentOut] = []

    @computed_field
    @property
    def count(self) -> int:
        return len(self.incidents)


class DispatchView(BaseModel):
    """Incidents grouped by crew.

    A list rather than a bare dict so the four queues always render in the same
    order, including when a queue is empty.
    """

    queues: list[DispatchQueue] = []

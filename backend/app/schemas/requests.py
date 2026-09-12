"""Request bodies for the coordinator's write actions.

Every one of these represents a human decision that overrides a recommendation
(CLAUDE.md section 5, DECISIONS.md D5).
"""

from pydantic import BaseModel, Field

from app.schemas.common import CrewName, IncidentStatus, OverridableField


class StatusUpdate(BaseModel):
    status: IncidentStatus
    note: str | None = None


class AssignCrew(BaseModel):
    crew: CrewName
    assigned_by: str = "Maya"
    notes: str | None = None


class OverrideRequest(BaseModel):
    """A manual override of one recommended field.

    `new_value` accepts an int so priority_score can be corrected without
    round-tripping through a string.
    """

    field: OverridableField = Field(description="Which incident field to override.")
    new_value: str | int
    reason: str | None = None
    changed_by: str = "Maya"

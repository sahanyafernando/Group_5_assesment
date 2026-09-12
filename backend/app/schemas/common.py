"""Shared literal types used across request and response models.

These mirror CLAUDE.md sections 6 and 7 and supabase/schema.sql. Keeping them
in one place stops the allowed values drifting apart between endpoints.
"""

from typing import Literal

# CLAUDE.md section 6 -- the only work types Claude may return.
WorkType = Literal[
    "Pothole",
    "Road surface damage",
    "Pavement damage",
    "Kerb",
    "Road marking",
    "Blocked drain",
    "Gully",
    "Culvert",
    "Manhole",
    "Drainage flooding",
    "Streetlight",
    "Sign post",
    "Bus shelter",
    "Bench",
    "Unsupported",
]

# CLAUDE.md section 7 -- crews. Anything unmapped becomes Manual Review.
CrewName = Literal[
    "Road Surface",
    "Drainage",
    "Lighting & Street Furniture",
    "Manual Review",
]

# REQUIREMENTS.md FR-22.
IncidentStatus = Literal[
    "New",
    "Triaged",
    "Assigned",
    "In Progress",
    "Completed",
    "Needs Review",
]

PriorityLevel = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]

Severity = Literal["critical", "high", "medium", "low", "unknown"]

# Fields a coordinator is allowed to override (audited in the overrides table).
OverridableField = Literal[
    "work_type",
    "required_crew",
    "priority_score",
    "priority_level",
    "status",
    "category",
    "severity",
]

CREW_ORDER: tuple[str, ...] = (
    "Road Surface",
    "Drainage",
    "Lighting & Street Furniture",
    "Manual Review",
)

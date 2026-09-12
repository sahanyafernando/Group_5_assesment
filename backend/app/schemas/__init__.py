"""API schemas.

Import from the package root: `from app.schemas import IncidentOut`.
"""

from app.schemas.ai import IncidentInsight, LocationHint, ReportAnalysis, ReportAnalysisRequest
from app.schemas.common import (
    CREW_ORDER,
    CrewName,
    IncidentStatus,
    OverridableField,
    PriorityLevel,
    Severity,
    WorkType,
)
from app.schemas.dashboard import (
    DashboardStats,
    DashboardSummary,
    DispatchQueue,
    DispatchView,
)
from app.schemas.incident import (
    IncidentDetail,
    IncidentOut,
    PriorityFactors,
    PriorityReason,
    RecentJobWarning,
)
from app.schemas.report import ReportOut
from app.schemas.requests import AssignCrew, OverrideRequest, StatusUpdate

__all__ = [
    "CREW_ORDER",
    "AssignCrew",
    "CrewName",
    "DashboardStats",
    "DashboardSummary",
    "DispatchQueue",
    "DispatchView",
    "IncidentDetail",
    "IncidentInsight",
    "IncidentOut",
    "IncidentStatus",
    "LocationHint",
    "OverridableField",
    "OverrideRequest",
    "PriorityFactors",
    "PriorityLevel",
    "PriorityReason",
    "RecentJobWarning",
    "ReportAnalysis",
    "ReportAnalysisRequest",
    "ReportOut",
    "Severity",
    "StatusUpdate",
    "WorkType",
]

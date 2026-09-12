from typing import get_args

import pytest
from pydantic import ValidationError

from app.schemas import (
    AssignCrew,
    CrewName,
    DispatchQueue,
    IncidentDetail,
    IncidentOut,
    IncidentStatus,
    OverrideRequest,
    PriorityFactors,
    PriorityReason,
    ReportOut,
    StatusUpdate,
    WorkType,
)
from app.services.crew_service import ALLOWED_WORK_TYPES, CREW_MAP


def test_work_type_literal_matches_crew_service():
    """The Literal must not drift from the mapping crew_service actually uses."""
    assert set(get_args(WorkType)) == set(ALLOWED_WORK_TYPES)


def test_crew_literal_matches_crew_map_plus_manual_review():
    assert set(get_args(CrewName)) == set(CREW_MAP.values()) | {"Manual Review"}


def test_report_accepts_db_column_names():
    report = ReportOut.model_validate(
        {
            "id": "uuid-1",
            "source_report_id": "MR-121627",
            "location_text": "Havelock Road, by the bus halt",
            "received_at": "2026-09-08T08:38:07",
            "source_row_number": 2,
        }
    )
    assert report.source_report_id == "MR-121627"
    assert report.received_at.year == 2026


def test_report_accepts_person_b_field_aliases():
    """report_id / location_raw are accepted as aliases for the DB names."""
    report = ReportOut.model_validate(
        {"report_id": "MR-607800", "location_raw": "outside 39 Kirula Road"}
    )
    assert report.source_report_id == "MR-607800"
    assert report.location_text == "outside 39 Kirula Road"


def test_report_ignores_unknown_db_columns():
    report = ReportOut.model_validate(
        {"id": "uuid-1", "raw_payload": {"anything": 1}, "ai_analysis": None}
    )
    assert report.id == "uuid-1"


def test_priority_reason_renders_label():
    reason = PriorityReason(factor="Road / public impact", points=15, reason="bus route")
    assert reason.label == "+15 bus route"
    assert reason.model_dump()["label"] == "+15 bus route"


def test_priority_factors_total_is_the_sum():
    factors = PriorityFactors(
        safety=35, road_impact=20, facility=15, persistence=15, report_count=10, urgency=5
    )
    assert factors.total == 100


def test_priority_factors_reject_over_ceiling():
    with pytest.raises(ValidationError):
        PriorityFactors(safety=36)


def test_incident_out_minimal_row():
    incident = IncidentOut.model_validate({"id": "uuid-1", "title": "Open manhole"})
    assert incident.required_crew == "Manual Review"
    assert incident.priority_score == 0
    assert incident.report_count == 1


def test_incident_out_rejects_impossible_score():
    with pytest.raises(ValidationError):
        IncidentOut(id="uuid-1", title="x", priority_score=101)


def test_incident_out_parses_nested_json_columns():
    incident = IncidentOut.model_validate(
        {
            "id": "uuid-1",
            "title": "Missing manhole cover",
            "hazards": ["open hole"],
            "priority_reasons": [
                {"factor": "Safety / severity", "points": 35, "reason": "open manhole"}
            ],
            "recent_job_warning": {
                "job_id": "JOB-4174",
                "completed_date": "2026-08-25",
                "crew": "Drainage",
            },
        }
    )
    assert incident.priority_reasons[0].label.startswith("+35")
    assert incident.recent_job_warning.job_id == "JOB-4174"


def test_incident_detail_carries_source_reports():
    detail = IncidentDetail.model_validate(
        {
            "id": "uuid-1",
            "title": "Open manhole",
            "source_reports": [{"report_id": "MR-1"}, {"report_id": "MR-1"}],
        }
    )
    # Duplicate source report IDs are legal -- the CSV contains them.
    assert [r.source_report_id for r in detail.source_reports] == ["MR-1", "MR-1"]


def test_dispatch_queue_counts_itself():
    queue = DispatchQueue(
        crew="Drainage",
        incidents=[IncidentOut(id="a", title="x"), IncidentOut(id="b", title="y")],
    )
    assert queue.count == 2


def test_status_update_rejects_unknown_status():
    assert StatusUpdate(status="Assigned").status == "Assigned"
    with pytest.raises(ValidationError):
        StatusUpdate(status="Done")


def test_assign_crew_rejects_invented_crew():
    assert AssignCrew(crew="Drainage").assigned_by == "Maya"
    with pytest.raises(ValidationError):
        AssignCrew(crew="Tree Team")


def test_override_rejects_unlisted_field():
    assert OverrideRequest(field="work_type", new_value="Pothole").changed_by == "Maya"
    assert OverrideRequest(field="priority_score", new_value=72).new_value == 72
    with pytest.raises(ValidationError):
        OverrideRequest(field="incident_code", new_value="INC-999")

import pytest

from app.db import incidents_repo as repo
from tests.fakes import ExplodingSupabase, FakeSupabase

INCIDENTS = [
    {"id": "i1", "title": "Open manhole", "required_crew": "Drainage", "status": "New",
     "needs_review": False, "ward": "Bambalapitiya", "work_type": "Manhole", "priority_score": 90},
    {"id": "i2", "title": "Pothole", "required_crew": "Road Surface", "status": "Triaged",
     "needs_review": True, "ward": "Kirulapone", "work_type": "Pothole", "priority_score": 60},
]

INCIDENT_REPORTS = [
    {"incident_id": "i1", "report_id": "r1", "match_confidence": 0.9},
    {"incident_id": "i1", "report_id": "r2", "match_confidence": 0.8},
]

RAW_REPORTS = [
    {"id": "r1", "source_report_id": "MR-1", "received_at": "2026-09-08T10:00:00"},
    {"id": "r2", "source_report_id": "MR-2", "received_at": "2026-09-07T09:00:00"},
    {"id": "r3", "source_report_id": "MR-3", "received_at": "2026-09-06T09:00:00"},
]


def db() -> FakeSupabase:
    return FakeSupabase(tables={
        "incidents": [dict(row) for row in INCIDENTS],
        "incident_reports": [dict(row) for row in INCIDENT_REPORTS],
        "raw_reports": [dict(row) for row in RAW_REPORTS],
    })


# --- list_incidents -----------------------------------------------------------


def test_list_returns_all_rows_with_no_filters():
    assert {row["id"] for row in repo.list_incidents(db())} == {"i1", "i2"}


def test_list_filters_by_crew():
    rows = repo.list_incidents(db(), crew="Drainage")
    assert [row["id"] for row in rows] == ["i1"]


def test_list_filters_by_status():
    rows = repo.list_incidents(db(), status="Triaged")
    assert [row["id"] for row in rows] == ["i2"]


def test_list_filters_by_needs_review():
    rows = repo.list_incidents(db(), needs_review=True)
    assert [row["id"] for row in rows] == ["i2"]


def test_list_filters_by_ward_and_work_type():
    assert [r["id"] for r in repo.list_incidents(db(), ward="Bambalapitiya")] == ["i1"]
    assert [r["id"] for r in repo.list_incidents(db(), work_type="Pothole")] == ["i2"]


def test_list_combines_filters():
    assert repo.list_incidents(db(), crew="Drainage", status="Triaged") == []


# --- get_incident ---------------------------------------------------------


def test_get_incident_returns_the_row():
    assert repo.get_incident("i2", db=db())["title"] == "Pothole"


def test_get_incident_returns_none_when_missing():
    assert repo.get_incident("nope", db=db()) is None


# --- get_source_reports ---------------------------------------------------


def test_source_reports_are_joined_through_incident_reports():
    reports = repo.get_source_reports("i1", db=db())
    assert {r["id"] for r in reports} == {"r1", "r2"}


def test_source_reports_excludes_unrelated_reports():
    reports = repo.get_source_reports("i1", db=db())
    assert "r3" not in {r["id"] for r in reports}


def test_source_reports_empty_when_no_links():
    assert repo.get_source_reports("i2", db=db()) == []


def test_source_reports_does_not_query_raw_reports_when_no_links():
    client = db()
    repo.get_source_reports("i2", db=client)
    assert ("table", "raw_reports") not in client.calls


# --- update_incident --------------------------------------------------------


def test_update_incident_changes_and_returns_the_row():
    client = db()
    updated = repo.update_incident("i1", {"status": "Assigned"}, db=client)
    assert updated["status"] == "Assigned"


def test_update_incident_raises_when_missing():
    with pytest.raises(RuntimeError, match="not found"):
        repo.update_incident("nope", {"status": "Assigned"}, db=db())


# --- insert_assignment / insert_override -------------------------------------


def test_insert_assignment_shapes_the_row():
    client = db()
    row = repo.insert_assignment("i1", "Drainage", assigned_by="Maya", notes="go", db=client)
    assert row["incident_id"] == "i1"
    assert row["crew"] == "Drainage"
    assert row["status"] == "Assigned"
    assert row["assigned_by"] == "Maya"


def test_insert_override_carries_before_and_after():
    client = db()
    row = repo.insert_override("i1", "work_type", "Pothole", "Kerb", reason="reclass", db=client)
    assert row["previous_value"] == "Pothole"
    assert row["new_value"] == "Kerb"
    assert row["reason"] == "reclass"
    assert row["changed_by"] == "Maya"  # default


# --- Failures propagate -------------------------------------------------------


def test_query_errors_are_raised_not_swallowed():
    with pytest.raises(RuntimeError, match="connection reset"):
        repo.list_incidents(ExplodingSupabase())

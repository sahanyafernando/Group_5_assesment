from datetime import date

import pytest

from app.schemas import RecentJobWarning
from app.services.crew_service import CREW_MAP
from app.services.history_service import (
    WORK_TYPE_SIMILARITY,
    check_recent_jobs,
    find_related_jobs,
    related_job_work_types,
)
from tests.fakes import ExplodingSupabase, FakeSupabase

JOBS = [
    {"source_job_id": "JOB-1", "completed_date": "2026-08-25", "crew": "Drainage",
     "work_type": "Manhole cover replacement", "road_name": "Kirula Road", "notes": "Completed."},
    {"source_job_id": "JOB-2", "completed_date": "2026-09-02", "crew": "Drainage",
     "work_type": "Manhole cover replacement", "road_name": "Kirula Road", "notes": "Partial, returned next day."},
    {"source_job_id": "JOB-3", "completed_date": "2026-09-05", "crew": "Drainage",
     "work_type": "Drain clearing", "road_name": "Kirula Road", "notes": "Closed."},
    {"source_job_id": "JOB-4", "completed_date": "2026-09-06", "crew": "Road Surface",
     "work_type": "Pothole patching", "road_name": "Galle Road", "notes": ""},
    {"source_job_id": "JOB-5", "completed_date": "2026-08-24", "crew": "Road Surface",
     "work_type": "Road resurfacing", "road_name": "Galle Road", "notes": "Completed."},
]


def db() -> FakeSupabase:
    return FakeSupabase(tables={"jobs_history": JOBS})


# --- The similarity map ------------------------------------------------------


def test_every_incident_work_type_has_a_mapping():
    """Every crew-mapped work type must be checkable against history."""
    assert set(WORK_TYPE_SIMILARITY) == set(CREW_MAP)


@pytest.mark.parametrize("work_type", sorted(WORK_TYPE_SIMILARITY))
def test_mapping_values_are_non_empty(work_type):
    assert related_job_work_types(work_type)


def test_manhole_maps_to_cover_replacement():
    assert related_job_work_types("Manhole") == ["Manhole cover replacement"]


def test_drainage_flooding_maps_to_three_job_types():
    assert related_job_work_types("Drainage flooding") == [
        "Drain clearing", "Storm drain inspection", "Gully cleaning",
    ]


@pytest.mark.parametrize("work_type", [None, "", "   ", "Tree removal", "Unsupported"])
def test_unknown_work_type_has_no_candidates(work_type):
    assert related_job_work_types(work_type) == []


def test_mapping_tolerates_casing_and_whitespace():
    assert related_job_work_types("  manhole ") == ["Manhole cover replacement"]


def test_mapping_returns_a_copy():
    related_job_work_types("Kerb").append("Tree felling")
    assert WORK_TYPE_SIMILARITY["Kerb"] == ["Kerb repair"]


# --- check_recent_jobs -------------------------------------------------------


def test_returns_the_most_recent_match():
    warning = check_recent_jobs("Kirula Road", "Manhole", db=db())
    assert warning["job_id"] == "JOB-2"
    assert warning["completed_date"] == "2026-09-02"


def test_road_match_is_case_insensitive():
    assert check_recent_jobs("kirula road", "Manhole", db=db())["job_id"] == "JOB-2"


def test_only_compatible_work_types_match():
    """A drain job on the road must not be reported as manhole history."""
    assert check_recent_jobs("Kirula Road", "Manhole", db=db())["work_type"] == "Manhole cover replacement"


def test_pothole_matches_both_related_job_types():
    assert check_recent_jobs("Galle Road", "Pothole", db=db())["job_id"] == "JOB-4"
    assert {j["job_id"] for j in find_related_jobs("Galle Road", "Pothole", db=db())} == {"JOB-4", "JOB-5"}


def test_no_match_returns_none():
    assert check_recent_jobs("Nowhere Street", "Manhole", db=db()) is None
    assert check_recent_jobs("Galle Road", "Bench", db=db()) is None


@pytest.mark.parametrize(("road", "work_type"), [(None, "Manhole"), ("", "Manhole"), ("Kirula Road", None), ("Kirula Road", "Tree removal")])
def test_missing_inputs_return_none_without_querying(road, work_type):
    client = db()
    assert check_recent_jobs(road, work_type, db=client) is None
    assert client.calls == []


def test_within_days_filters_older_jobs():
    recent = find_related_jobs("Galle Road", "Pothole", db=db(), within_days=3650)
    assert len(recent) == 2
    assert find_related_jobs("Galle Road", "Pothole", db=db(), within_days=1) == []


# --- The warning itself ------------------------------------------------------


def test_warning_validates_against_the_schema():
    warning = RecentJobWarning.model_validate(check_recent_jobs("Kirula Road", "Manhole", db=db()))
    assert warning.job_id == "JOB-2"
    assert warning.completed_date == date(2026, 9, 2)
    assert warning.crew == "Drainage"
    assert warning.notes == "Partial, returned next day."


def test_warning_message_is_explainable():
    message = check_recent_jobs("Kirula Road", "Manhole", db=db())["message"]
    assert "Drainage" in message
    assert "Manhole cover replacement" in message
    assert "Kirula Road" in message
    assert "same problem" in message


def test_warning_reports_age_in_days():
    assert check_recent_jobs("Kirula Road", "Manhole", db=db())["days_ago"] >= 0


def test_missing_completed_date_is_tolerated():
    client = FakeSupabase(tables={"jobs_history": [
        {"source_job_id": "JOB-X", "completed_date": None, "crew": "Drainage",
         "work_type": "Manhole cover replacement", "road_name": "Kirula Road", "notes": None},
    ]})
    warning = check_recent_jobs("Kirula Road", "Manhole", db=client)
    assert warning["completed_date"] is None
    assert warning["days_ago"] is None
    assert "recently" in warning["message"]


# --- Failures must not look like an all-clear --------------------------------


def test_query_errors_are_raised_not_swallowed():
    """Returning None on error would falsely tell Maya there is no recent job."""
    with pytest.raises(RuntimeError, match="connection reset"):
        check_recent_jobs("Kirula Road", "Manhole", db=ExplodingSupabase())


# --- Nothing here decides anything -------------------------------------------


def test_service_never_returns_a_closure_decision():
    warning = check_recent_jobs("Kirula Road", "Manhole", db=db())
    assert "status" not in warning
    assert "resolved" not in warning
    assert "close" not in str(warning.get("message", "")).lower()

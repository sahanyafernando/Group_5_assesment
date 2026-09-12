import pytest

from app.services.enrichment_pipeline import enrich_all_incidents, enrich_incident
from tests.fakes import ExplodingSupabase, FakeSupabase

ASSETS = [
    {"road_name": "Galle Road", "ward": "Kollupitiya", "road_class": "main road",
     "asset_type": "footpath", "nearest_facility": "St Anthony's Girls School", "facility_distance_m": 80},
    {"road_name": "Nawala Road", "ward": "Nawala", "road_class": "residential",
     "asset_type": "drain", "nearest_facility": None, "facility_distance_m": None},
]

JOBS = [
    {"source_job_id": "JOB-1", "completed_date": "2026-08-25", "crew": "Road Surface",
     "work_type": "Pothole patching", "road_name": "Galle Road", "notes": "Completed."},
]

INCIDENT_MANHOLE = {
    "id": "i1",
    "title": "Missing manhole cover",
    "summary": "Dangerous open manhole, a child nearly fell in.",
    "canonical_road": "Galle Road",
    "work_type": "Manhole",
    "severity": "critical",
    "hazards": ["open hole"],
    "report_count": 5,
    "required_crew": "Manual Review",
    "priority_score": 0,
    "priority_level": "LOW",
    "status": "New",
    "needs_review": False,
}

INCIDENT_UNSUPPORTED = {
    "id": "i2",
    "title": "Fallen tree branch",
    "canonical_road": "Nawala Road",
    "work_type": "Unsupported",
    "severity": "medium",
    "report_count": 1,
    "required_crew": "Manual Review",
    "priority_score": 0,
    "priority_level": "LOW",
    "status": "New",
    "needs_review": False,
}

INCIDENT_ALREADY_FLAGGED = {
    **INCIDENT_MANHOLE,
    "id": "i3",
    "work_type": "Pothole",  # a supported type
    "needs_review": True,     # already flagged by a human or earlier step
}


def db(incidents=None) -> FakeSupabase:
    return FakeSupabase(tables={
        "assets": [dict(row) for row in ASSETS],
        "jobs_history": [dict(row) for row in JOBS],
        "incidents": [dict(row) for row in (incidents or [])],
    })


# --- enrich_incident: the full pass ------------------------------------------


def test_enrich_fills_in_asset_context():
    client = db([dict(INCIDENT_MANHOLE)])
    updated = enrich_incident("i1", db=client)
    assert updated["ward"] == "Kollupitiya"
    assert updated["road_class"] == "main road"
    assert updated["nearest_facility"] == "St Anthony's Girls School"
    assert updated["facility_distance_m"] == 80
    assert updated["asset_types"] == ["footpath"]


def test_enrich_recommends_the_correct_crew():
    client = db([dict(INCIDENT_MANHOLE)])
    updated = enrich_incident("i1", db=client)
    assert updated["required_crew"] == "Drainage"


def test_enrich_computes_an_explainable_priority():
    client = db([dict(INCIDENT_MANHOLE)])
    updated = enrich_incident("i1", db=client)
    assert updated["priority_score"] > 0
    assert updated["priority_level"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    assert all(r["points"] > 0 for r in updated["priority_reasons"])
    assert sum(updated["priority_factors"].values()) == updated["priority_score"]


def test_enrich_attaches_a_recent_job_warning_when_related_work_exists():
    incident = {**INCIDENT_MANHOLE, "id": "i4", "work_type": "Pothole"}
    client = db([incident])
    updated = enrich_incident("i4", db=client)
    assert updated["recent_job_warning"]["job_id"] == "JOB-1"


def test_enrich_leaves_warning_none_when_nothing_related():
    client = db([dict(INCIDENT_MANHOLE)])  # Manhole has no matching job in JOBS
    updated = enrich_incident("i1", db=client)
    assert updated["recent_job_warning"] is None


def test_enrich_clears_a_stale_warning_on_rerun():
    """Re-running after the underlying data changed must not leave old state."""
    incident = {**INCIDENT_MANHOLE, "id": "i5", "work_type": "Pothole",
                "recent_job_warning": {"job_id": "STALE-JOB"}}
    client = db([incident])
    updated = enrich_incident("i5", db=client)
    assert updated["recent_job_warning"]["job_id"] == "JOB-1"  # replaced, not merged


# --- needs_review is monotonic (never cleared by this pipeline) --------------


def test_enrich_sets_needs_review_when_crew_is_manual_review():
    client = db([dict(INCIDENT_UNSUPPORTED)])
    updated = enrich_incident("i2", db=client)
    assert updated["required_crew"] == "Manual Review"
    assert updated["needs_review"] is True


def test_enrich_does_not_clear_an_existing_needs_review_flag():
    """A supported work type must not silently un-flag a human-flagged incident."""
    client = db([dict(INCIDENT_ALREADY_FLAGGED)])
    updated = enrich_incident("i3", db=client)
    assert updated["required_crew"] == "Road Surface"  # a supported crew
    assert updated["needs_review"] is True  # still flagged


def test_enrich_does_not_flag_a_supported_clean_incident():
    incident = {**INCIDENT_MANHOLE, "id": "i6", "work_type": "Pothole"}
    client = db([incident])
    updated = enrich_incident("i6", db=client)
    assert updated["needs_review"] is False


# --- Missing incident ----------------------------------------------------------


def test_enrich_raises_value_error_for_unknown_incident():
    with pytest.raises(ValueError, match="not found"):
        enrich_incident("nope", db=db())


# --- enrich_all_incidents: batch behaviour ------------------------------------


def test_enrich_all_processes_every_incident():
    client = db([dict(INCIDENT_MANHOLE), dict(INCIDENT_UNSUPPORTED)])
    result = enrich_all_incidents(db=client)
    assert result["processed"] == 2
    assert result["succeeded"] == 2
    assert result["failed"] == []


def test_enrich_all_persists_results_for_every_incident():
    client = db([dict(INCIDENT_MANHOLE), dict(INCIDENT_UNSUPPORTED)])
    enrich_all_incidents(db=client)
    stored = {row["id"]: row for row in client.tables["incidents"]}
    assert stored["i1"]["required_crew"] == "Drainage"
    assert stored["i2"]["required_crew"] == "Manual Review"


class _FlakyIncidentLookup(FakeSupabase):
    """A FakeSupabase whose get_incident-style query fails for one chosen id.

    Everything else (list_incidents, update_incident, assets, jobs_history)
    behaves normally -- this isolates exactly the failure enrich_all_incidents
    is meant to survive: one incident's own read blowing up mid-batch.
    """

    def __init__(self, tables: dict, fail_id: str):
        super().__init__(tables=tables)
        self._fail_id = fail_id

    def table(self, name: str):
        query = super().table(name)
        if name == "incidents":
            real_eq = query.eq

            def guarded_eq(column: str, value):
                if column == "id" and value == self._fail_id:
                    raise RuntimeError(f"simulated transient failure reading {value}")
                return real_eq(column, value)

            query.eq = guarded_eq
        return query


def test_enrich_all_continues_past_a_single_failure():
    """One bad incident must not stop the batch (CLAUDE.md section 9)."""
    client = _FlakyIncidentLookup(
        tables={
            "assets": [dict(row) for row in ASSETS],
            "jobs_history": [dict(row) for row in JOBS],
            "incidents": [dict(INCIDENT_MANHOLE), dict(INCIDENT_UNSUPPORTED)],
        },
        fail_id="i2",
    )

    result = enrich_all_incidents(db=client)
    assert result["processed"] == 2
    assert result["succeeded"] == 1
    assert len(result["failed"]) == 1
    assert result["failed"][0]["incident_id"] == "i2"
    assert "simulated transient failure" in result["failed"][0]["error"]

    # The healthy incident must still have been enriched and persisted.
    stored = {row["id"]: row for row in client.tables["incidents"]}
    assert stored["i1"]["required_crew"] == "Drainage"


def test_enrich_all_empty_table_is_a_no_op():
    result = enrich_all_incidents(db=db())
    assert result == {"processed": 0, "succeeded": 0, "failed": []}


# --- Errors from a completely unreachable database ----------------------------


def test_enrich_incident_propagates_a_connection_failure():
    with pytest.raises(RuntimeError, match="connection reset"):
        enrich_incident("i1", db=ExplodingSupabase())

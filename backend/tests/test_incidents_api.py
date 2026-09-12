"""API-level tests against demo data (tests/conftest.py forces DEMO_MODE)."""

import pytest


# --- GET /api/incidents -------------------------------------------------------


def test_list_returns_all_demo_incidents(client):
    resp = client.get("/api/incidents")
    assert resp.status_code == 200
    assert len(resp.json()) == 4


def test_list_is_sorted_by_priority_desc(client):
    scores = [row["priority_score"] for row in client.get("/api/incidents").json()]
    assert scores == sorted(scores, reverse=True)


def test_list_filters_by_crew(client):
    rows = client.get("/api/incidents", params={"crew": "Drainage"}).json()
    assert all(row["required_crew"] == "Drainage" for row in rows)
    assert len(rows) == 1


def test_list_filters_by_status(client):
    rows = client.get("/api/incidents", params={"status": "New"}).json()
    assert all(row["status"] == "New" for row in rows)


def test_list_filters_by_needs_review(client):
    rows = client.get("/api/incidents", params={"needs_review": True}).json()
    assert len(rows) == 1
    assert rows[0]["needs_review"] is True


def test_list_filters_by_ward(client):
    rows = client.get("/api/incidents", params={"ward": "Bambalapitiya"}).json()
    assert [r["ward"] for r in rows] == ["Bambalapitiya"]


def test_list_filters_by_work_type(client):
    rows = client.get("/api/incidents", params={"work_type": "Streetlight"}).json()
    assert [r["work_type"] for r in rows] == ["Streetlight"]


def test_list_search_matches_title_road_or_work_type(client):
    assert len(client.get("/api/incidents", params={"q": "pothole"}).json()) == 1
    assert len(client.get("/api/incidents", params={"q": "kirula"}).json()) == 1
    assert len(client.get("/api/incidents", params={"q": "nonexistent"}).json()) == 0


def test_list_combines_filters(client):
    rows = client.get("/api/incidents", params={"crew": "Drainage", "status": "New"}).json()
    assert rows == []  # the one Drainage incident is Triaged, not New


# --- GET /api/incidents/{id} ---------------------------------------------------


def test_get_incident_detail(client):
    resp = client.get("/api/incidents/demo-001")
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Missing manhole cover"
    assert body["source_reports"] == []


def test_get_incident_404_for_unknown_id(client):
    assert client.get("/api/incidents/does-not-exist").status_code == 404


# --- GET /api/dispatch ---------------------------------------------------------


def test_dispatch_has_all_four_queues_in_order(client):
    queues = client.get("/api/dispatch").json()["queues"]
    assert [q["crew"] for q in queues] == [
        "Road Surface", "Drainage", "Lighting & Street Furniture", "Manual Review",
    ]


def test_dispatch_groups_incidents_correctly(client):
    queues = {q["crew"]: q["incidents"] for q in client.get("/api/dispatch").json()["queues"]}
    assert [i["title"] for i in queues["Drainage"]] == ["Missing manhole cover"]
    assert [i["title"] for i in queues["Manual Review"]] == ["Fallen tree branch"]


def test_dispatch_queues_are_sorted_by_priority(client):
    for queue in client.get("/api/dispatch").json()["queues"]:
        scores = [i["priority_score"] for i in queue["incidents"]]
        assert scores == sorted(scores, reverse=True)


def test_dispatch_counts_match_incident_lists(client):
    for queue in client.get("/api/dispatch").json()["queues"]:
        assert queue["count"] == len(queue["incidents"])


# --- GET /api/stats --------------------------------------------------------------


def test_stats_totals_match_demo_data(client):
    stats = client.get("/api/stats").json()
    assert stats["total_incidents"] == 4
    assert stats["high_priority_count"] == 2  # CRITICAL + HIGH
    assert stats["needs_review_count"] == 1


def test_stats_breakdowns_sum_to_total(client):
    stats = client.get("/api/stats").json()
    assert sum(stats["by_status"].values()) == stats["total_incidents"]
    assert sum(stats["by_crew"].values()) == stats["total_incidents"]


# --- POST /api/incidents/{id}/status ---------------------------------------------


def test_status_update_changes_status(client):
    resp = client.post("/api/incidents/demo-002/status", json={"status": "Assigned"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "Assigned"
    assert client.get("/api/incidents/demo-002").json()["status"] == "Assigned"


def test_status_update_rejects_unknown_status(client):
    resp = client.post("/api/incidents/demo-002/status", json={"status": "Closed"})
    assert resp.status_code == 422


def test_status_update_404_for_unknown_incident(client):
    resp = client.post("/api/incidents/nope/status", json={"status": "New"})
    assert resp.status_code == 404


# --- POST /api/incidents/{id}/assign ----------------------------------------------


def test_assign_sets_crew_and_status(client):
    resp = client.post("/api/incidents/demo-003/assign", json={"crew": "Drainage"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["required_crew"] == "Drainage"
    assert body["status"] == "Assigned"


def test_assign_rejects_invented_crew(client):
    resp = client.post("/api/incidents/demo-003/assign", json={"crew": "Tree Team"})
    assert resp.status_code == 422


def test_assign_404_for_unknown_incident(client):
    resp = client.post("/api/incidents/nope/assign", json={"crew": "Drainage"})
    assert resp.status_code == 404


def test_assign_is_recorded_as_an_override_too(client):
    from app.services import demo_store

    client.post("/api/incidents/demo-003/assign", json={"crew": "Drainage", "notes": "swap"})
    overrides = demo_store.list_overrides("demo-003")
    assert any(o["field_name"] == "required_crew" and o["new_value"] == "Drainage" for o in overrides)


# --- POST /api/incidents/{id}/override --------------------------------------------


def test_override_work_type_recalculates_crew(client):
    resp = client.post(
        "/api/incidents/demo-004/override",
        json={"field": "work_type", "new_value": "Bench"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["work_type"] == "Bench"
    assert body["required_crew"] == "Lighting & Street Furniture"


def test_override_work_type_to_unmapped_falls_back_to_manual_review(client):
    resp = client.post(
        "/api/incidents/demo-002/override",
        json={"field": "work_type", "new_value": "Unsupported"},
    )
    assert resp.json()["required_crew"] == "Manual Review"


def test_override_priority_score_recalculates_level(client):
    resp = client.post(
        "/api/incidents/demo-001/override",
        json={"field": "priority_score", "new_value": 30},
    )
    body = resp.json()
    assert body["priority_score"] == 30
    assert body["priority_level"] == "LOW"


def test_override_status_does_not_touch_crew(client):
    before = client.get("/api/incidents/demo-002").json()["required_crew"]
    resp = client.post(
        "/api/incidents/demo-002/override",
        json={"field": "status", "new_value": "Needs Review"},
    )
    assert resp.json()["status"] == "Needs Review"
    assert resp.json()["required_crew"] == before


def test_override_rejects_field_not_in_allowlist(client):
    resp = client.post(
        "/api/incidents/demo-001/override",
        json={"field": "incident_code", "new_value": "HACKED"},
    )
    assert resp.status_code == 422


def test_override_404_for_unknown_incident(client):
    resp = client.post(
        "/api/incidents/nope/override", json={"field": "status", "new_value": "New"}
    )
    assert resp.status_code == 404


def test_override_is_recorded_in_the_audit_trail(client):
    from app.services import demo_store

    client.post(
        "/api/incidents/demo-001/override",
        json={"field": "severity", "new_value": "low", "reason": "resident retracted"},
    )
    overrides = demo_store.list_overrides("demo-001")
    assert len(overrides) == 1
    assert overrides[0]["field_name"] == "severity"
    assert overrides[0]["previous_value"] == "critical"
    assert overrides[0]["new_value"] == "low"
    assert overrides[0]["reason"] == "resident retracted"


# --- POST /api/pipeline/run --------------------------------------------------------


def test_pipeline_placeholder_returns_not_implemented(client):
    resp = client.post("/api/pipeline/run")
    assert resp.status_code == 200
    assert resp.json()["status"] == "not_implemented"

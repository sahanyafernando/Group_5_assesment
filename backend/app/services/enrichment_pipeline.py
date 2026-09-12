"""The bridge between Person A's pipeline output and deterministic business logic.

Person A creates an incident with the fields only Claude/clustering can supply:
title, summary, canonical_road, work_type, severity, hazards, report_count,
first_reported_at, latest_reported_at. enrich_incident() then adds everything
this backend owns: required_crew, priority_score/level/reasons/factors, ward,
road_class, asset_types, nearest_facility, facility_distance_m, and a recent
job warning. Nothing here calls Claude and nothing here is a coordinator
decision (CLAUDE.md sections 5 and 8).

This always operates on the live Supabase `incidents` table via
app.db.incidents_repo, never on demo_store: enrichment is part of the real
pipeline, not the frontend demo (DEMO_MODE only changes what the dashboard
reads, not what a pipeline run writes).
"""

from app.db import incidents_repo as repo
from app.services.asset_service import enrich_from_assets
from app.services.crew_service import get_crew
from app.services.history_service import check_recent_jobs
from app.services.priority_service import (
    calculate_priority,
    days_between,
    parse_iso_datetime,
)


def _priority_input(incident: dict, asset: dict) -> dict:
    """Merge the incident's own fields with resolved asset context.

    Asset fields take priority over anything already stored on the incident:
    assets.csv is the authority on road_class/facility (CLAUDE.md section 5),
    so a stale value from a previous enrichment run is always replaced.
    """
    first_reported = parse_iso_datetime(incident.get("first_reported_at"))

    return {
        "severity": incident.get("severity"),
        "road_class": asset.get("road_class"),
        "facility_distance_m": asset.get("facility_distance_m"),
        "nearest_facility": asset.get("nearest_facility"),
        "age_days": days_between(first_reported),
        "report_count": incident.get("report_count") or 1,
        "urgency": incident.get("urgency"),
        "title": incident.get("title"),
        "summary": incident.get("summary"),
        "hazards": incident.get("hazards") or [],
    }


def enrich_incident(incident_id: str, db=None) -> dict:
    """Read an incident, compute every deterministic field, and persist it.

    Raises ValueError if the incident does not exist -- a missing incident is
    a caller bug (a stale ID), not a data-quality issue to swallow.
    """
    incident = repo.get_incident(incident_id, db=db)
    if incident is None:
        raise ValueError(f"Incident {incident_id} not found; nothing to enrich.")

    road_name = incident.get("canonical_road")
    asset = enrich_from_assets(road_name, db=db)
    priority = calculate_priority(_priority_input(incident, asset))
    required_crew = get_crew(incident.get("work_type"))
    recent_job = check_recent_jobs(road_name, incident.get("work_type"), db=db)

    # needs_review only ever turns on here, never off: clearing a review flag
    # is a coordinator decision this pipeline must not make on its own
    # (CLAUDE.md section 5, "never overwrite a manual coordinator decision").
    needs_review = bool(incident.get("needs_review")) or required_crew == "Manual Review"

    fields = {
        "ward": asset.get("ward"),
        "road_class": asset.get("road_class"),
        "asset_types": asset.get("asset_types") or [],
        "nearest_facility": asset.get("nearest_facility"),
        "facility_distance_m": asset.get("facility_distance_m"),
        "required_crew": required_crew,
        "priority_score": priority["priority_score"],
        "priority_level": priority["priority_level"],
        "priority_reasons": priority["priority_reasons"],
        "priority_factors": priority["priority_factors"],
        "recent_job_warning": recent_job,
        "needs_review": needs_review,
    }

    return repo.update_incident(incident_id, fields, db=db)


def enrich_all_incidents(db=None) -> dict:
    """Re-enrich every incident. Useful after a rule change (Step 4/6/7 edit).

    One incident failing (a bad row, a transient query error) must not stop
    the rest of the batch (CLAUDE.md section 9); each failure is collected and
    returned rather than raised.
    """
    incidents = repo.list_incidents(db=db)

    succeeded: list[str] = []
    failed: list[dict] = []

    for incident in incidents:
        incident_id = incident["id"]
        try:
            enrich_incident(incident_id, db=db)
            succeeded.append(incident_id)
        except Exception as exc:  # noqa: BLE001 - intentionally broad, see docstring
            failed.append({"incident_id": incident_id, "error": str(exc)})

    return {
        "processed": len(incidents),
        "succeeded": len(succeeded),
        "failed": failed,
    }

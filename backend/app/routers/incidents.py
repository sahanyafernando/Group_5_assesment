"""Incident read/write endpoints.

Read endpoints serve the dashboard. Write endpoints are Maya's decisions --
every one of them is audited (CLAUDE.md section 5, DECISIONS.md D5).
"""

from anthropic import Anthropic
from fastapi import APIRouter, HTTPException, Query

from app.core.config import get_settings
from app.db import incidents_repo as repo
from app.schemas import (
    AssignCrew,
    IncidentDetail,
    IncidentInsight,
    IncidentOut,
    OverrideRequest,
    StatusUpdate,
)
from app.services import demo_store
from app.services.ai_summarizer import generate_incident_insight
from app.services.crew_service import get_crew
from app.services.enrichment_pipeline import enrich_incident
from app.services.priority_service import priority_level as compute_priority_level

router = APIRouter(prefix="/incidents", tags=["incidents"])


def _text_matches(row: dict, needle: str) -> bool:
    needle = needle.lower()
    return (
        needle in (row.get("title") or "").lower()
        or needle in (row.get("canonical_road") or "").lower()
        or needle in (row.get("work_type") or "").lower()
    )


@router.get("", response_model=list[IncidentOut])
def list_incidents(
    crew: str | None = Query(default=None),
    status: str | None = Query(default=None),
    needs_review: bool | None = Query(default=None),
    ward: str | None = Query(default=None),
    work_type: str | None = Query(default=None),
    q: str | None = Query(default=None, description="Free-text search over title/road/work type"),
) -> list[dict]:
    settings = get_settings()

    if settings.demo_mode:
        rows = demo_store.list_incidents()
        if crew:
            rows = [r for r in rows if r.get("required_crew") == crew]
        if status:
            rows = [r for r in rows if r.get("status") == status]
        if needs_review is not None:
            rows = [r for r in rows if bool(r.get("needs_review")) == needs_review]
        if ward:
            rows = [r for r in rows if r.get("ward") == ward]
        if work_type:
            rows = [r for r in rows if r.get("work_type") == work_type]
    else:
        try:
            rows = repo.list_incidents(
                crew=crew, status=status, needs_review=needs_review, ward=ward, work_type=work_type
            )
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Database query failed: {exc}") from exc

    if q:
        rows = [row for row in rows if _text_matches(row, q)]

    return sorted(rows, key=lambda row: row.get("priority_score", 0), reverse=True)


@router.get("/{incident_id}", response_model=IncidentDetail)
def get_incident(incident_id: str) -> dict:
    settings = get_settings()

    if settings.demo_mode:
        incident = demo_store.find_incident(incident_id)
        if incident is None:
            raise HTTPException(status_code=404, detail="Incident not found")
        return {**incident, "source_reports": []}

    try:
        incident = repo.get_incident(incident_id)
        if incident is None:
            raise HTTPException(status_code=404, detail="Incident not found")
        source_reports = repo.get_source_reports(incident_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database query failed: {exc}") from exc

    return {**incident, "source_reports": source_reports}


@router.post("/{incident_id}/ai-insight", response_model=IncidentInsight)
async def get_incident_insight(incident_id: str) -> dict:
    """An on-demand Claude read of one incident: a summary plus a short list
    of things worth checking before acting on it.

    Advisory only (CLAUDE.md section 5) - never persisted over the
    deterministic pipeline's own fields, and never raises for a Claude
    failure; it degrades to a plain result with insight_error set instead
    (CLAUDE.md section 9).
    """
    settings = get_settings()

    if settings.demo_mode:
        incident = demo_store.find_incident(incident_id)
        if incident is None:
            raise HTTPException(status_code=404, detail="Incident not found")
        source_reports = []
    else:
        try:
            incident = repo.get_incident(incident_id)
            if incident is None:
                raise HTTPException(status_code=404, detail="Incident not found")
            source_reports = repo.get_source_reports(incident_id)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Database query failed: {exc}") from exc

    if not settings.claude_configured:
        raise HTTPException(
            status_code=503,
            detail="Claude API is not configured. Set ANTHROPIC_API_KEY in backend/.env.",
        )

    client = Anthropic(api_key=settings.anthropic_api_key)
    return await generate_incident_insight(client, incident, source_reports)


@router.post("/{incident_id}/status", response_model=IncidentOut)
def update_status(incident_id: str, payload: StatusUpdate) -> dict:
    """Set an incident's workflow status (REQUIREMENTS.md FR-22)."""
    settings = get_settings()
    fields = {"status": payload.status}

    if settings.demo_mode:
        try:
            return demo_store.update_incident(incident_id, fields)
        except RuntimeError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        current = repo.get_incident(incident_id)
        if current is None:
            raise HTTPException(status_code=404, detail="Incident not found")
        return repo.update_incident(incident_id, fields)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database update failed: {exc}") from exc


@router.post("/{incident_id}/assign", response_model=IncidentOut)
def assign_crew(incident_id: str, payload: AssignCrew) -> dict:
    """Assign an incident to a crew, with an audit trail (REQUIREMENTS.md FR-21).

    This always records an override: assigning a crew that differs from the
    system recommendation is itself a coordinator decision worth auditing, even
    when it happens to match the recommendation.
    """
    settings = get_settings()
    fields = {"required_crew": payload.crew, "status": "Assigned"}

    if settings.demo_mode:
        current = demo_store.find_incident(incident_id)
        if current is None:
            raise HTTPException(status_code=404, detail="Incident not found")
        previous_crew = current.get("required_crew")
        updated = demo_store.update_incident(incident_id, fields)
        demo_store.record_override(
            incident_id, "required_crew", previous_crew, payload.crew,
            reason=payload.notes, changed_by=payload.assigned_by,
        )
        return updated

    try:
        current = repo.get_incident(incident_id)
        if current is None:
            raise HTTPException(status_code=404, detail="Incident not found")

        repo.insert_assignment(
            incident_id, payload.crew, assigned_by=payload.assigned_by, notes=payload.notes
        )
        repo.insert_override(
            incident_id,
            "required_crew",
            current.get("required_crew"),
            payload.crew,
            reason=payload.notes,
            changed_by=payload.assigned_by,
        )
        return repo.update_incident(incident_id, fields)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database update failed: {exc}") from exc


@router.post("/{incident_id}/override", response_model=IncidentOut)
def override_field(incident_id: str, payload: OverrideRequest) -> dict:
    """Override one recommended field, with a full before/after audit row.

    If work_type changes, required_crew is recalculated through crew_service
    -- never chosen by the caller -- so a work_type override cannot leave a
    stale crew behind (CLAUDE.md section 7). If priority_score changes,
    priority_level is recalculated the same deterministic way, so the two
    never disagree.
    """
    settings = get_settings()

    if settings.demo_mode:
        current = demo_store.find_incident(incident_id)
        if current is None:
            raise HTTPException(status_code=404, detail="Incident not found")
        previous_value = current.get(payload.field)
        fields = _derive_override_fields(payload)
        demo_store.record_override(
            incident_id, payload.field, previous_value, payload.new_value,
            reason=payload.reason, changed_by=payload.changed_by,
        )
        return demo_store.update_incident(incident_id, fields)

    try:
        current = repo.get_incident(incident_id)
        if current is None:
            raise HTTPException(status_code=404, detail="Incident not found")

        previous_value = current.get(payload.field)
        fields = _derive_override_fields(payload)

        repo.insert_override(
            incident_id, payload.field, previous_value, payload.new_value,
            reason=payload.reason, changed_by=payload.changed_by,
        )
        return repo.update_incident(incident_id, fields)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database update failed: {exc}") from exc


def _derive_override_fields(payload: OverrideRequest) -> dict:
    """The full set of columns a single override actually changes."""
    fields: dict = {payload.field: payload.new_value}

    if payload.field == "work_type":
        fields["required_crew"] = get_crew(str(payload.new_value))

    if payload.field == "priority_score":
        fields["priority_level"] = compute_priority_level(int(payload.new_value))

    return fields


@router.post("/{incident_id}/enrich", response_model=IncidentOut)
def enrich_one_incident(incident_id: str) -> dict:
    """Recompute crew/priority/asset/history fields for one incident.

    Always operates on the live Supabase incidents table, regardless of
    DEMO_MODE -- enrichment belongs to Person A's real pipeline, not the
    frontend demo. Useful for re-running Step 8 by hand after a rule change.
    """
    try:
        return enrich_incident(incident_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Enrichment failed: {exc}") from exc

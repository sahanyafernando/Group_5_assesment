"""Supabase queries for incidents and their related tables.

Kept separate from app/routers/incidents.py so the router stays thin: it
decides demo-vs-live and HTTP shape, this module only knows how to talk to
Postgres. No FastAPI imports here, and no AI -- pure reads/writes.
"""

from datetime import datetime, timezone

from app.db.supabase import get_supabase_client


def list_incidents(
    db=None,
    *,
    crew: str | None = None,
    status: str | None = None,
    needs_review: bool | None = None,
    ward: str | None = None,
    work_type: str | None = None,
) -> list[dict]:
    """Incidents sorted by priority_score desc, with optional exact filters."""
    db = db or get_supabase_client()

    query = db.table("incidents").select("*").order("priority_score", desc=True)

    if crew:
        query = query.eq("required_crew", crew)
    if status:
        query = query.eq("status", status)
    if needs_review is not None:
        query = query.eq("needs_review", needs_review)
    if ward:
        query = query.eq("ward", ward)
    if work_type:
        query = query.eq("work_type", work_type)

    return query.execute().data or []


def get_incident(incident_id: str, db=None) -> dict | None:
    """One incident row, or None if it does not exist."""
    db = db or get_supabase_client()
    response = db.table("incidents").select("*").eq("id", incident_id).limit(1).execute()
    rows = response.data or []
    return rows[0] if rows else None


def get_source_reports(incident_id: str, db=None) -> list[dict]:
    """Raw reports behind an incident, via the incident_reports link table.

    REQUIREMENTS.md FR-18. Ordered newest first so the latest resident account
    is easy to find; duplicate source_report_id values are expected and kept
    (CLAUDE.md section 10).
    """
    db = db or get_supabase_client()
    links = (
        db.table("incident_reports")
        .select("report_id")
        .eq("incident_id", incident_id)
        .execute()
        .data
        or []
    )
    report_ids = [row["report_id"] for row in links if row.get("report_id")]
    if not report_ids:
        return []

    reports = (
        db.table("raw_reports")
        .select("*")
        .in_("id", report_ids)
        .order("received_at", desc=True)
        .execute()
        .data
        or []
    )
    return reports


def update_incident(incident_id: str, fields: dict, db=None) -> dict:
    """Patch an incident row and return the updated row.

    Raises RuntimeError if the incident does not exist -- the caller (a
    router) turns that into a 404, so a missing incident never looks like a
    silently-ignored write.
    """
    db = db or get_supabase_client()
    response = (
        db.table("incidents").update(fields).eq("id", incident_id).execute()
    )
    rows = response.data or []
    if not rows:
        raise RuntimeError(f"Incident {incident_id} not found; nothing updated.")
    return rows[0]


def insert_assignment(
    incident_id: str,
    crew: str,
    *,
    assigned_by: str = "Maya",
    notes: str | None = None,
    db=None,
) -> dict:
    """Record a crew assignment. One row per assignment action (append-only)."""
    db = db or get_supabase_client()
    row = {
        "incident_id": incident_id,
        "crew": crew,
        "status": "Assigned",
        "assigned_by": assigned_by,
        "notes": notes,
    }
    response = db.table("assignments").insert(row).execute()
    return (response.data or [row])[0]


def insert_override(
    incident_id: str,
    field_name: str,
    previous_value,
    new_value,
    *,
    reason: str | None = None,
    changed_by: str = "Maya",
    db=None,
) -> dict:
    """Record one manual override for the audit trail (CLAUDE.md section 5).

    previous_value/new_value are stored as jsonb, so both scalars (a string, an
    int) and structured values round-trip without a manual cast.
    """
    db = db or get_supabase_client()
    row = {
        "incident_id": incident_id,
        "field_name": field_name,
        "previous_value": previous_value,
        "new_value": new_value,
        "reason": reason,
        "changed_by": changed_by,
    }
    response = db.table("overrides").insert(row).execute()
    return (response.data or [row])[0]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

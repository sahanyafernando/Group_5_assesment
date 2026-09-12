from fastapi import APIRouter, HTTPException, Query

from app.core.config import get_settings
from app.db.supabase import get_supabase_client
from app.services.demo_data import DEMO_INCIDENTS

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("")
def list_incidents(
    crew: str | None = Query(default=None),
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
) -> list[dict]:
    settings = get_settings()

    if settings.demo_mode:
        rows = list(DEMO_INCIDENTS)
    else:
        try:
            db = get_supabase_client()
            response = (
                db.table("incidents")
                .select("*")
                .order("priority_score", desc=True)
                .execute()
            )
            rows = response.data or []
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Database query failed: {exc}") from exc

    if crew:
        rows = [row for row in rows if row.get("required_crew") == crew]
    if status:
        rows = [row for row in rows if row.get("status") == status]
    if q:
        needle = q.lower()
        rows = [
            row
            for row in rows
            if needle in (row.get("title") or "").lower()
            or needle in (row.get("canonical_road") or "").lower()
            or needle in (row.get("work_type") or "").lower()
        ]

    return sorted(rows, key=lambda row: row.get("priority_score", 0), reverse=True)


@router.get("/{incident_id}")
def get_incident(incident_id: str) -> dict:
    settings = get_settings()

    if settings.demo_mode:
        for incident in DEMO_INCIDENTS:
            if incident["id"] == incident_id:
                return incident
        raise HTTPException(status_code=404, detail="Incident not found")

    try:
        db = get_supabase_client()
        response = (
            db.table("incidents")
            .select("*")
            .eq("id", incident_id)
            .limit(1)
            .execute()
        )
        if not response.data:
            raise HTTPException(status_code=404, detail="Incident not found")
        return response.data[0]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database query failed: {exc}") from exc

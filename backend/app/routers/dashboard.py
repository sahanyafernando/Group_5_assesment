from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.db.supabase import get_supabase_client
from app.services.demo_data import DEMO_INCIDENTS

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def dashboard_summary() -> dict:
    settings = get_settings()

    if settings.demo_mode:
        return {
            "reports": 240,
            "incidents": len(DEMO_INCIDENTS),
            "high_or_critical": sum(
                1
                for item in DEMO_INCIDENTS
                if item["priority_level"] in {"HIGH", "CRITICAL"}
            ),
            "needs_review": sum(1 for item in DEMO_INCIDENTS if item["needs_review"]),
        }

    try:
        db = get_supabase_client()

        reports = (
            db.table("raw_reports")
            .select("id", count="exact")
            .limit(1)
            .execute()
        )
        incidents = (
            db.table("incidents")
            .select("id,priority_level,needs_review")
            .execute()
        )

        incident_rows = incidents.data or []

        return {
            "reports": reports.count or 0,
            "incidents": len(incident_rows),
            "high_or_critical": sum(
                1
                for item in incident_rows
                if item.get("priority_level") in {"HIGH", "CRITICAL"}
            ),
            "needs_review": sum(
                1 for item in incident_rows if item.get("needs_review")
            ),
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database query failed: {exc}") from exc

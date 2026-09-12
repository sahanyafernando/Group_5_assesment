"""Dashboard statistics (REQUIREMENTS.md MVP screen 'Dashboard').

Separate from GET /api/dashboard/summary, which Person C's dashboard already
consumes with a smaller, fixed shape -- this endpoint adds the by_status /
by_crew breakdowns without changing that existing contract.
"""

import collections

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.db import incidents_repo as repo
from app.db.supabase import count_rows
from app.schemas import DashboardStats
from app.services import demo_store

router = APIRouter(tags=["stats"])

HIGH_PRIORITY_LEVELS = {"HIGH", "CRITICAL"}


def _build_stats(rows: list[dict], total_reports: int) -> DashboardStats:
    return DashboardStats(
        total_reports=total_reports,
        total_incidents=len(rows),
        high_priority_count=sum(
            1 for row in rows if row.get("priority_level") in HIGH_PRIORITY_LEVELS
        ),
        needs_review_count=sum(1 for row in rows if row.get("needs_review")),
        by_status=dict(collections.Counter(row.get("status") or "Unknown" for row in rows)),
        by_crew=dict(collections.Counter(row.get("required_crew") or "Unknown" for row in rows)),
    )


@router.get("/stats", response_model=DashboardStats)
def get_stats() -> DashboardStats:
    settings = get_settings()

    if settings.demo_mode:
        return _build_stats(demo_store.list_incidents(), total_reports=240)

    try:
        rows = repo.list_incidents()
        total_reports = count_rows("raw_reports")
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database query failed: {exc}") from exc

    return _build_stats(rows, total_reports=total_reports)

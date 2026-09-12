"""Crew dispatch queues (REQUIREMENTS.md FR-20, MVP screen 'Dispatch view')."""

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.db import incidents_repo as repo
from app.schemas import CREW_ORDER, DispatchQueue, DispatchView
from app.services import demo_store

router = APIRouter(tags=["dispatch"])


@router.get("/dispatch", response_model=DispatchView)
def get_dispatch_view() -> dict:
    """Incidents grouped by crew, each queue sorted by priority_score desc.

    Every crew in CREW_ORDER appears, including an empty queue, so the four
    dispatch columns render consistently (CLAUDE.md section 11).
    """
    settings = get_settings()

    if settings.demo_mode:
        rows = demo_store.list_incidents()
    else:
        try:
            rows = repo.list_incidents()
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Database query failed: {exc}") from exc

    queues = []
    for crew in CREW_ORDER:
        crew_rows = sorted(
            (row for row in rows if row.get("required_crew") == crew),
            key=lambda row: row.get("priority_score", 0),
            reverse=True,
        )
        queues.append(DispatchQueue(crew=crew, incidents=crew_rows))

    return DispatchView(queues=queues)

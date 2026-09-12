"""Recent-work check against the jobs_history table.

REQUIREMENTS.md FR-12. When a crew has recently completed related work on the
same road, the coordinator should see that before dispatching another crew --
it may be a repeat failure, a partial fix, or simply the same problem reported
again.

CLAUDE.md section 5 is explicit: nothing here may decide that a historical job
resolves a new report. This service produces a WARNING. Maya decides.
"""

from datetime import date, datetime, timedelta, timezone

from app.db.supabase import get_supabase_client

# Incident work_type -> the work_type strings used in jobs-history.csv.
# Verified against all 15 distinct work_type values in the supplied data.
WORK_TYPE_SIMILARITY: dict[str, list[str]] = {
    "Pothole": ["Pothole patching", "Road resurfacing"],
    "Road surface damage": ["Road resurfacing", "Pothole patching"],
    "Pavement damage": ["Pavement slab replacement"],
    "Kerb": ["Kerb repair"],
    "Road marking": ["Line marking"],
    "Blocked drain": ["Drain clearing", "Gully cleaning", "Storm drain inspection"],
    "Gully": ["Gully cleaning", "Drain clearing"],
    "Culvert": ["Culvert repair"],
    "Manhole": ["Manhole cover replacement"],
    "Drainage flooding": ["Drain clearing", "Storm drain inspection", "Gully cleaning"],
    "Streetlight": ["Streetlight column repair", "Streetlight bulb replacement"],
    "Sign post": ["Sign post repair"],
    "Bus shelter": ["Bus shelter repair"],
    "Bench": ["Bench replacement"],
}


def related_job_work_types(work_type: str | None) -> list[str]:
    """Historical work types that could relate to this incident work type.

    Returns an empty list for unknown or unsupported work types -- no guessing.
    """
    if not work_type or not work_type.strip():
        return []

    if work_type in WORK_TYPE_SIMILARITY:
        return list(WORK_TYPE_SIMILARITY[work_type])

    # Tolerate casing/whitespace, exactly as crew_service does.
    normalized = " ".join(work_type.lower().split())
    for key, values in WORK_TYPE_SIMILARITY.items():
        if " ".join(key.lower().split()) == normalized:
            return list(values)
    return []


def _as_date(value) -> date | None:
    """Parse a completed_date that may arrive as a date or an ISO string."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except ValueError:
        return None


def _days_ago(completed: date | None, today: date | None = None) -> int | None:
    if completed is None:
        return None
    today = today or datetime.now(timezone.utc).date()
    return max((today - completed).days, 0)


def _build_warning(row: dict, today: date | None = None) -> dict:
    """Shape a jobs_history row into a coordinator-facing warning."""
    completed = _as_date(row.get("completed_date"))
    days_ago = _days_ago(completed, today)
    crew = row.get("crew") or "A crew"
    work_type = row.get("work_type") or "related work"
    road = row.get("road_name") or "this road"

    when = f"{days_ago} day(s) ago" if days_ago is not None else "recently"
    message = (
        f"{crew} completed '{work_type}' on {road} {when}. "
        "Check whether this is the same problem before dispatching again."
    )

    return {
        "job_id": row.get("source_job_id") or row.get("job_id"),
        "crew": row.get("crew"),
        "work_type": row.get("work_type"),
        "road_name": row.get("road_name"),
        "completed_date": completed.isoformat() if completed else None,
        "notes": row.get("notes"),
        "days_ago": days_ago,
        "message": message,
    }


def find_related_jobs(
    road_name: str | None,
    work_type: str | None,
    *,
    db=None,
    within_days: int | None = None,
    limit: int = 5,
) -> list[dict]:
    """Completed jobs on the same road with a compatible work type.

    Newest first. Returns an empty list when the road or work type gives us
    nothing to match on -- an empty result means "no related job found", never
    "the check failed": a query error is raised, not swallowed, so a failed
    check can never be mistaken for an all-clear.
    """
    road = (road_name or "").strip()
    candidates = related_job_work_types(work_type)
    if not road or not candidates:
        return []

    db = db or get_supabase_client()

    query = (
        db.table("jobs_history")
        .select("*")
        .ilike("road_name", road)
        .in_("work_type", candidates)
        .order("completed_date", desc=True)
        .limit(limit)
    )

    if within_days is not None:
        cutoff = datetime.now(timezone.utc).date() - timedelta(days=within_days)
        query = query.gte("completed_date", cutoff.isoformat())

    rows = query.execute().data or []
    return [_build_warning(row) for row in rows]


def check_recent_jobs(
    road_name: str | None,
    work_type: str | None,
    *,
    db=None,
    within_days: int | None = None,
) -> dict | None:
    """The most recent related completed job, or None.

    A result is a warning for the coordinator, never an automatic closure
    (CLAUDE.md section 5).
    """
    matches = find_related_jobs(
        road_name, work_type, db=db, within_days=within_days, limit=1
    )
    return matches[0] if matches else None


if __name__ == "__main__":
    # Runs against Supabase. Requires backend/.env and an imported jobs_history.
    checks = [
        ("Galle Road", "Manhole"),
        ("Havelock Road", "Drainage flooding"),
        ("Horton Place", "Streetlight"),
        ("Galle Road", "Bench"),
        ("Nowhere Street", "Pothole"),
        (None, "Pothole"),
        ("Galle Road", None),
        ("Galle Road", "Tree removal"),
    ]

    print("  work type -> historical work types")
    for work_type in ("Manhole", "Drainage flooding", "Tree removal", None):
        print(f"      {str(work_type):<20} {related_job_work_types(work_type)}")

    print()
    print("  recent-job checks")
    for road, work_type in checks:
        warning = check_recent_jobs(road, work_type)
        if warning:
            print(f"      {str(road):<16} {str(work_type):<20} -> {warning['job_id']} {warning['completed_date']} ({warning['days_ago']}d)")
        else:
            print(f"      {str(road):<16} {str(work_type):<20} -> no related job")

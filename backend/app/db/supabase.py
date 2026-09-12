"""Supabase access for the FastAPI backend.

The browser never talks to Supabase. Only this module builds a client, and it
uses the server-side secret key from backend/.env (see CLAUDE.md section 4).
"""

from functools import lru_cache

from supabase import Client, create_client

from app.core.config import get_settings, mask_secret

# Tables created by supabase/schema.sql.
EXPECTED_TABLES = (
    "raw_reports",
    "assets",
    "jobs_history",
    "incidents",
    "incident_reports",
    "assignments",
    "overrides",
)

# Row counts worth showing at startup, so an empty import is obvious.
COUNTED_TABLES = ("raw_reports", "assets", "jobs_history", "incidents")


class SupabaseNotConfigured(RuntimeError):
    """SUPABASE_URL or the server-side key is missing from backend/.env."""


@lru_cache
def get_supabase_client() -> Client:
    """Return a cached Supabase client, or raise a clear configuration error."""
    settings = get_settings()

    if not settings.supabase_configured:
        raise SupabaseNotConfigured(
            "Supabase is not configured. Set SUPABASE_URL and a server-side key "
            "(SUPABASE_KEY, SUPABASE_SECRET_KEY or SUPABASE_SERVICE_ROLE_KEY) "
            "in backend/.env."
        )

    return create_client(settings.supabase_url, settings.supabase_service_key)


def count_rows(table: str) -> int:
    """Count rows in a table without transferring them.

    `select("*")` rather than `select("id")` because incident_reports has a
    composite primary key and no `id` column.
    """
    db = get_supabase_client()
    response = db.table(table).select("*", count="exact").limit(1).execute()
    return response.count or 0


def check_connection() -> dict:
    """Probe Supabase and report what the backend can actually see.

    Never raises: the caller (startup banner, /api/health/supabase) wants a
    status, not an exception.
    """
    settings = get_settings()

    result: dict = {
        "configured": settings.supabase_configured,
        "connected": False,
        "url": settings.supabase_url or None,
        "key_source": settings.supabase_key_source,
        "key_preview": mask_secret(settings.supabase_service_key),
        "tables": {},
        "missing_tables": [],
        "error": None,
    }

    if not settings.supabase_configured:
        result["error"] = (
            "Missing SUPABASE_URL and/or a server-side Supabase key in backend/.env."
        )
        return result

    try:
        db = get_supabase_client()
    except Exception as exc:
        result["error"] = f"Could not create the Supabase client: {exc}"
        return result

    for table in EXPECTED_TABLES:
        try:
            result["tables"][table] = count_rows(table)
            result["connected"] = True
        except Exception as exc:
            result["tables"][table] = None
            result["missing_tables"].append(table)
            if result["error"] is None:
                result["error"] = f"Query on '{table}' failed: {exc}"

    if not result["connected"]:
        result["error"] = (
            result["error"]
            or "Reached Supabase but no expected table could be queried. "
            "Has supabase/schema.sql been run?"
        )

    return result

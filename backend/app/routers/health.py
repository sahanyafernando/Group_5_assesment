from fastapi import APIRouter

from app.core.config import get_settings
from app.db.supabase import check_connection

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.app_env,
        "demo_mode": settings.demo_mode,
        "supabase_configured": settings.supabase_configured,
        "claude_configured": settings.claude_configured,
    }


@router.get("/health/supabase")
def supabase_health() -> dict:
    """Live Supabase probe with per-table row counts. Secrets stay masked."""
    return check_connection()

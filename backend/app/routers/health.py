from fastapi import APIRouter

from app.core.config import get_settings

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

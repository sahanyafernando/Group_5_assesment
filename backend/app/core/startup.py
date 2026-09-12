"""Startup diagnostics printed to the console when the API boots.

Nothing about the Supabase key -- not even its masked preview -- is printed
here (CLAUDE.md section 4: never print full secrets; masking is not the same
as not printing, so the connection acknowledgement stays key-free entirely).
"""

from app.core.config import get_settings
from app.db.supabase import COUNTED_TABLES, check_connection

LINE = "=" * 66
THIN = "-" * 66


def _row(label: str, value: str) -> str:
    return f"  {label:<16}: {value}"


def print_startup_report() -> dict:
    """Print backend configuration and Supabase connectivity. Returns the check.

    The live Supabase probe is skipped in demo mode: demo mode exists so the
    app runs with no external dependencies at all (README.md "Quick start"),
    and every app boot -- including one inside a test's TestClient -- would
    otherwise make a real network call (CLAUDE.md section 14: unit tests must
    not call external APIs).
    """
    settings = get_settings()
    status = (
        {"configured": settings.supabase_configured, "connected": None, "tables": {}, "missing_tables": [], "error": None}
        if settings.demo_mode
        else check_connection()
    )

    print()
    print(LINE)
    print(f"  {settings.app_name}")
    print(THIN)
    print(_row("Environment", settings.app_env))
    print(_row("Demo mode", "ON (serving demo data)" if settings.demo_mode else "OFF (live Supabase)"))
    print(
        _row(
            "Claude",
            f"configured, model={settings.claude_model}"
            if settings.claude_configured
            else "NOT configured (ANTHROPIC_API_KEY missing)",
        )
    )
    print(THIN)

    if settings.demo_mode:
        print(_row("Supabase", "not checked (demo mode)"))
    elif not status["configured"]:
        print(_row("Supabase", "NOT CONFIGURED"))
        print(_row("Reason", status["error"]))
        print(_row("Fix", "set SUPABASE_URL and SUPABASE_SECRET_KEY in backend/.env"))
    elif status["connected"]:
        print(_row("Supabase", "CONNECTED"))
        print(_row("URL", status["url"]))
        counts = ", ".join(
            f"{table}={status['tables'].get(table)}"
            for table in COUNTED_TABLES
            if status["tables"].get(table) is not None
        )
        print(_row("Row counts", counts or "(none readable)"))
        if status["missing_tables"]:
            print(_row("Missing tables", ", ".join(status["missing_tables"])))
            print(_row("Fix", "run supabase/schema.sql in the Supabase SQL editor"))
    else:
        print(_row("Supabase", "NOT CONNECTED"))
        print(_row("URL", status["url"]))
        print(_row("Error", str(status["error"])[:200]))

    if not settings.demo_mode and not status["connected"]:
        print(THIN)
        print("  WARNING: DEMO_MODE=false but Supabase is unreachable.")
        print("           Data endpoints will return HTTP 503 until this is fixed.")

    print(LINE)
    print()

    return status

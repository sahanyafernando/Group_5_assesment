from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


def mask_secret(value: str, keep: int = 4) -> str:
    """Render a secret safely for logs: never print the full value."""
    if not value:
        return "(not set)"
    if len(value) <= keep * 2:
        return "*" * len(value)
    return f"{value[:keep]}...{value[-keep:]} (len={len(value)})"


class Settings(BaseSettings):
    app_name: str = "Muthuwella Works Dispatch API"
    app_env: str = "development"
    demo_mode: bool = True

    cors_origins: str = "http://localhost:5173"

    supabase_url: str = ""

    # The server-side Supabase credential. Supabase has renamed this key over
    # time and the team's prompts use different names, so all three spellings
    # are accepted and resolved by `supabase_service_key` below.
    supabase_key: str = ""
    supabase_secret_key: str = ""
    supabase_service_role_key: str = ""

    anthropic_api_key: str = ""
    claude_model: str = "claude-haiku-4-5"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def supabase_service_key(self) -> str:
        """The first server-side Supabase key that is actually set."""
        for candidate in (
            self.supabase_key,
            self.supabase_secret_key,
            self.supabase_service_role_key,
        ):
            if candidate.strip():
                return candidate.strip()
        return ""

    @property
    def supabase_key_source(self) -> str:
        """Which env var supplied the Supabase key, for startup diagnostics."""
        if self.supabase_key.strip():
            return "SUPABASE_KEY"
        if self.supabase_secret_key.strip():
            return "SUPABASE_SECRET_KEY"
        if self.supabase_service_role_key.strip():
            return "SUPABASE_SERVICE_ROLE_KEY"
        return "(none)"

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url.strip() and self.supabase_service_key)

    @property
    def claude_configured(self) -> bool:
        return bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Muthuwella Works Dispatch API"
    app_env: str = "development"
    demo_mode: bool = True

    cors_origins: str = "http://localhost:5173"

    supabase_url: str = ""
    # Supabase's newer key naming is SUPABASE_SECRET_KEY (server-side) /
    # SUPABASE_PUBLISHABLE_KEY (client-side). Accept the old SUPABASE_KEY too.
    supabase_key: str = Field(
        default="",
        validation_alias=AliasChoices("SUPABASE_KEY", "SUPABASE_SECRET_KEY"),
    )

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
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_key)

    @property
    def claude_configured(self) -> bool:
        return bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()

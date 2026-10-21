from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import os


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/sentinel.db"

    # Encryption
    encryption_key: str = ""

    # LLM Provider defaults (for probing)
    llm_api_key: str = ""
    llm_provider: str = "openai-compatible"
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = "https://api.openai.com/v1"

    # Probing
    probe_interval_sec: int = 300
    probe_timeout_sec: int = 30
    probe_enabled: bool = True

    # Routing
    max_concurrent_per_key: int = 10
    hedge_after_ms: int = 5000
    default_timeout_sec: int = 60

    # Keycloak/OIDC
    keycloak_url: str = "http://localhost:8080"
    keycloak_realm: str = "sentinel"
    keycloak_client_id: str = "sentinel-frontend"
    keycloak_client_secret: str = ""
    oidc_issuer: str = ""
    oidc_audience: str = "sentinel-api"

    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Demo mode
    demo_mode: bool = False

    def __post_init__(self):
        if self.demo_mode and not os.environ.get("SENTINEL_DEMO_ALLOWED"):
            raise RuntimeError("Demo mode refused in production. Set SENTINEL_DEMO_ALLOWED=1 to override.")


settings = Settings()
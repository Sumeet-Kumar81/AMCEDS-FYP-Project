from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


WEAK_JWT_SECRETS = frozenset({"", "dev-only-secret", "change_me", "change_me_to_a_long_random_string"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "dev"  # "dev" allows the weak development JWT secret; anything else refuses it
    database_url: str = "postgresql+asyncpg://dispatch:change_me@postgres:5432/dispatch"
    jwt_secret: str = "dev-only-secret"
    jwt_expire_minutes: int = 15  # access token lifetime (D-023)
    jwt_refresh_hours: int = 12  # absolute refresh-token lifetime, about one shift (developer assumption, B1-A1-14)
    cors_origins: str = "http://localhost:5173,http://localhost:5174"

    llm_provider: str = "groq"
    llm_model: str = "llama-3.3-70b-versatile"
    llm_api_key: str = ""
    llm_base_url: str = ""  # empty = the provider's standard URL (Groq: api.groq.com/openai/v1)
    llm_timeout_s: float = 8.0  # per model call (NFR-P1), B1-A2-02
    worker_concurrency: int = 2  # AI worker jobs in parallel, B1-A2-14
    ollama_url: str = "http://ollama:11434"
    osrm_url: str = "http://osrm:5000"
    nominatim_url: str = "https://nominatim.openstreetmap.org"

    # business rules (SRS Appendix C): startup defaults only. The authoritative, admin-changeable
    # values live in the `settings` table, read through app/services/settings.py (B1-A1-12).
    patients_per_ambulance: int = 2
    dup_distance_m: int = 300
    dup_window_min: int = 15
    dup_auto_link: int = 85
    dup_possible: int = 60
    triage_min_confidence: int = 60

    def check_secrets(self) -> None:
        """Refuse to start outside development with a weak or example JWT secret (B1-A1-14)."""
        if self.env != "dev" and (self.jwt_secret in WEAK_JWT_SECRETS or len(self.jwt_secret) < 32):
            raise RuntimeError("JWT_SECRET is missing, an example value or shorter than 32 characters (ENV is not 'dev')")

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://dispatch:change_me@postgres:5432/dispatch"
    jwt_secret: str = "dev-only-secret"
    jwt_expire_minutes: int = 30
    cors_origins: str = "http://localhost:5173,http://localhost:5174"

    llm_provider: str = "groq"
    llm_model: str = "llama-3.3-70b-versatile"
    llm_api_key: str = ""
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

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

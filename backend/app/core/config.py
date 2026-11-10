from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://tfg:tfg_local@127.0.0.1:5433/tfg"
    redis_url: str | None = None
    frontend_origin: str = "http://localhost:5173"
    backend_origin: str = "http://localhost:8000"
    cookie_secure: bool = False
    google_client_id: str | None = None
    google_client_secret: str | None = None
    media_dir: Path = Path(__file__).resolve().parents[1] / "media"
    backup_dir: Path | None = None
    pg_dump_path: str = "pg_dump"
    backup_db_container: str | None = None
    pdf_timeout_seconds: int = 10
    pdf_memory_mb: int = 256
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    openai_vacancy_model: str | None = None
    openai_interview_model: str | None = None
    openai_voice_model: str = "gpt-realtime-2.1-mini"
    openai_voice: str = "marin"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def vacancy_model(self) -> str:
        return self.openai_vacancy_model or self.openai_model

    @property
    def interview_model(self) -> str:
        return self.openai_interview_model or self.openai_model


settings = Settings()

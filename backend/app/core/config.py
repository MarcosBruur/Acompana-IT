from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://tfg:tfg_local@127.0.0.1:5433/tfg"
    frontend_origin: str = "http://localhost:5173"
    backend_origin: str = "http://localhost:8000"
    cookie_secure: bool = False
    google_client_id: str | None = None
    google_client_secret: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

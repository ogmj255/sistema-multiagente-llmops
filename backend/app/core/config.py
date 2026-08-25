from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """Configuración básica del back-end."""

    app_name: str = "Sistema Multiagente LLMOps"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    database_url: str = (
        "postgresql+psycopg://tesis_user:change_me@localhost:5432/clausulas_db"
    )

    chroma_host: str = "localhost"
    chroma_port: int = 8001
    chroma_collection: str = "legal_knowledge"

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_data_dir() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "data"
        if candidate.is_dir():
            return candidate
    return Path.cwd() / "data"


def _default_sqlite_url() -> str:
    backend_dir = Path(__file__).resolve().parents[2]
    target_dir = backend_dir if os.access(backend_dir, os.W_OK) else Path("/tmp")
    db_path = (target_dir / "aed_registry.db").as_posix()
    return f"sqlite+aiosqlite:///{db_path}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "Krajowy Rejestr AED"
    APP_VERSION: str = "1.0.0"
    DATABASE_URL: str = _default_sqlite_url()
    DEDUP_RADIUS_M: float = 25.0
    OVERPASS_URL: str = "https://overpass-api.de/api/interpreter"
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    DATA_DIR: Path = _default_data_dir()
    AUTO_SEED_ON_EMPTY: bool = True

    @property
    def is_postgres(self) -> bool:
        return self.DATABASE_URL.startswith("postgresql")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()

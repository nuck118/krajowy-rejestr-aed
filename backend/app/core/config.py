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
    here = Path(__file__).resolve()
    for candidate in (here.parents[2], Path.cwd() / "backend"):
        if (
            candidate.name == "backend"
            and (candidate / "pyproject.toml").is_file()
            and os.access(candidate, os.W_OK)
        ):
            db_path = (candidate / "aed_registry.db").as_posix()
            return f"sqlite+aiosqlite:///{db_path}"
    fallback_path = (Path("/tmp") / "aed_registry.db").as_posix()
    return f"sqlite+aiosqlite:///{fallback_path}"


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
    CORS_ORIGINS: str = "*"
    DATA_DIR: Path = _default_data_dir()
    AUTO_SEED_ON_EMPTY: bool = True
    ENABLE_REVERSE_GEOCODING: bool = True

    # dane.gov.pl (MCOD v2.63.0) integration & observability settings
    SLOW_SQL_LOGGING_ENABLED: bool = True
    SLOW_SQL_THRESHOLD_SECONDS: float = 1.0
    MCOD_API_VERSION: str = "1.4"
    MCOD_SUPPORTED_API_VERSIONS: tuple[str, ...] = ("1.0", "1.4")
    DANE_GOV_API_BASE_URL: str = "https://api.dane.gov.pl/1.4"
    ENABLE_DANE_GOV_LIVE_DISCOVERY: bool = False
    INSTITUTION_REGON: str = "00000012345678"

    @property
    def is_postgres(self) -> bool:
        return self.DATABASE_URL.startswith("postgresql")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()

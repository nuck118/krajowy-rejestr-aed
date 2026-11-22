import os
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from pydantic import PrivateAttr
from pydantic_settings import BaseSettings, SettingsConfigDict


_ASYNCPG_UNSUPPORTED_PARAMS = frozenset(
    {
        "sslmode",
        "channel_binding",
        "pgbouncer",
        "schema",
        "connection_limit",
        "pool_timeout",
        "connect_timeout",
    }
)


def prepare_async_database_url(raw_url: str) -> tuple[str, dict[str, Any]]:
    """Normalize Prisma Console / Neon / Supabase / Heroku Postgres URLs for SQLAlchemy asyncpg."""
    url = raw_url.strip()
    if url.startswith("prisma+postgres://"):
        raise ValueError(
            "prisma+postgres:// Accelerate URLs cannot be used with Python/SQLAlchemy. "
            "Use Prisma Console's Direct TCP connection string "
            "(postgres://...@db.prisma.io:5432/postgres?sslmode=require) instead."
        )

    if not url.startswith(("postgres://", "postgresql://", "postgresql+")):
        return url, {"timeout": 30}

    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://") :]
    elif url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    elif url.startswith("postgresql+psycopg2://"):
        url = "postgresql+asyncpg://" + url[len("postgresql+psycopg2://") :]
    elif url.startswith("postgresql+psycopg://"):
        url = "postgresql+asyncpg://" + url[len("postgresql+psycopg://") :]

    parts = urlsplit(url)
    query_items = parse_qsl(parts.query, keep_blank_values=True)
    params_map = {k.lower(): v for k, v in query_items}
    clean_query = [
        (k, v) for k, v in query_items if k.lower() not in _ASYNCPG_UNSUPPORTED_PARAMS
    ]

    connect_args: dict[str, Any] = {}
    sslmode = params_map.get("sslmode", "").lower()
    host = (parts.hostname or "").lower()
    is_managed_tls_host = host.endswith(
        (".prisma.io", ".neon.tech", ".supabase.co", ".supabase.com")
    )

    if sslmode in {"require", "verify-ca", "verify-full", "prefer"} or (
        not sslmode and is_managed_tls_host
    ):
        connect_args["ssl"] = "require"

    if params_map.get("pgbouncer", "").lower() in {"true", "1"} or host.endswith(".prisma.io"):
        connect_args["statement_cache_size"] = 0

    normalized_url = urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(clean_query), parts.fragment)
    )
    return normalized_url, connect_args


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
    USE_POSTGIS: bool | None = None

    _postgis_available: bool = PrivateAttr(default=False)

    @property
    def is_postgres(self) -> bool:
        return self.DATABASE_URL.startswith(("postgresql", "postgres://"))

    @property
    def use_postgis(self) -> bool:
        if not self.is_postgres:
            return False
        if self.USE_POSTGIS is not None:
            return self.USE_POSTGIS
        return self._postgis_available

    @property
    def database_dialect(self) -> str:
        if self.use_postgis:
            return "postgresql+postgis"
        if self.is_postgres:
            return "postgresql+spatial"
        return "sqlite+spatial"

    def set_postgis_available(self, available: bool) -> None:
        self._postgis_available = available

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()

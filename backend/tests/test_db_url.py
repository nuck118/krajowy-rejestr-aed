import pytest

from app.core.config import prepare_async_database_url


def test_prisma_console_direct_tcp_url_normalization() -> None:
    raw = "postgres://user:secret@db.prisma.io:5432/postgres?sslmode=require&connection_limit=5"
    normalized, connect_args = prepare_async_database_url(raw)
    assert normalized == "postgresql+asyncpg://user:secret@db.prisma.io:5432/postgres"
    assert connect_args["ssl"] == "require"
    assert connect_args["statement_cache_size"] == 0


def test_neon_postgresql_url_strips_channel_binding_and_sslmode() -> None:
    raw = "postgresql://user:pass@ep-test-123.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    normalized, connect_args = prepare_async_database_url(raw)
    assert normalized == "postgresql+asyncpg://user:pass@ep-test-123.eu-central-1.aws.neon.tech/neondb"
    assert connect_args["ssl"] == "require"


def test_prisma_accelerate_url_raises_clear_error() -> None:
    with pytest.raises(ValueError, match="Direct TCP connection string"):
        prepare_async_database_url("prisma+postgres://accelerate.prisma-data.net/?api_key=abc123")


def test_sqlite_url_unchanged() -> None:
    raw = "sqlite+aiosqlite:///tmp/aed_registry.db"
    normalized, connect_args = prepare_async_database_url(raw)
    assert normalized == raw
    assert connect_args == {"timeout": 30}

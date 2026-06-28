"""Async database engine, session factory, and declarative base for the application.

Handles asyncpg URL sanitization: strips libpq-only query params (sslmode,
channel_binding) that asyncpg rejects, and translates sslmode=require into
connect_args={"ssl": True}.
"""

from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

# asyncpg rejects these libpq-only query params — they must be stripped from the URL.
_LIBPQ_ONLY_PARAMS = {"sslmode", "channel_binding"}

# sslmode values that require an encrypted connection.
_SSL_REQUIRE_MODES = {"require", "verify-ca", "verify-full"}


class DatabaseConfig(BaseSettings):
    """Database-scoped settings — isolated per AGENTS.md one-BaseSettings-per-domain rule."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    DATABASE_URL: str


def _asyncpg_url_and_connect_args(url: str) -> tuple[str, dict]:
    """Strip libpq-only query params and derive asyncpg connect_args.

    Args:
        url: Raw DATABASE_URL that may contain libpq params like sslmode.

    Returns:
        (clean_url, connect_args) where connect_args contains ssl=True when
        the original sslmode was require/verify-ca/verify-full.
    """
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)

    ssl_mode = (params.pop("sslmode", [None])[0] or "").lower()
    for param in _LIBPQ_ONLY_PARAMS - {"sslmode"}:
        params.pop(param, None)

    clean_query = urlencode({k: v[0] for k, v in params.items()})
    clean_url = urlunparse(parsed._replace(query=clean_query))

    connect_args: dict = {}
    if ssl_mode in _SSL_REQUIRE_MODES:
        connect_args["ssl"] = True

    return clean_url, connect_args


db_settings = DatabaseConfig()

_db_url, _connect_args = _asyncpg_url_and_connect_args(db_settings.DATABASE_URL)

# Exposed for use in migrations/env.py which builds its own engine.
ASYNC_DATABASE_URL: str = _db_url
ASYNC_CONNECT_ARGS: dict = _connect_args

POSTGRES_INDEXES_NAMING_CONVENTION = {
    "ix": "%(column_0_label)s_idx",
    "uq": "%(table_name)s_%(column_0_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}

metadata = MetaData(naming_convention=POSTGRES_INDEXES_NAMING_CONVENTION)


class Base(DeclarativeBase):
    metadata = metadata


engine = create_async_engine(
    _db_url,
    connect_args=_connect_args,
    pool_pre_ping=True,
    echo=False,
)

SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncSession:  # type: ignore[return]
    async with SessionFactory() as session:
        yield session

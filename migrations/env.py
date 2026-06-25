"""Alembic migration environment (async).

Wires Alembic to the app's async engine: pulls the URL from ``DATABASE_URL`` via
``src.database.db_settings`` (ignoring the placeholder in ``alembic.ini``) and uses
``Base.metadata`` as the autogenerate target. Importing ``src.users.models``
registers the ``user`` table on that metadata.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.pool import NullPool

from alembic import context

# App metadata + settings. Importing models populates Base.metadata.
from src.database import ASYNC_CONNECT_ARGS, ASYNC_DATABASE_URL, Base
import src.users.models  # noqa: F401  (side effect: register tables)

config = context.config

# Use the sanitized URL (libpq-only params like sslmode stripped for asyncpg).
config.set_main_option("sqlalchemy.url", ASYNC_DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL without a DBAPI connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Configure the context against a live connection and run migrations."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations within a connection."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=NullPool,
        connect_args=ASYNC_CONNECT_ARGS,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using the async engine."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

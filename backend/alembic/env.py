import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Import ALL models so Base.metadata is fully populated ──────────
# GeoAlchemy2 must be imported so Alembic recognises Geometry columns.
import geoalchemy2  # noqa: F401
from src.models import Base  # noqa: F401  (side-effect: registers all models)

target_metadata = Base.metadata

# ── Allow DATABASE_URL env-var to override alembic.ini ─────────────
database_url = os.getenv("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)


# ── Only manage OUR application tables, ignore everything else ─────
# PostGIS tiger_geocoder and topology extensions create dozens of tables
# visible on the default search_path. We whitelist only our own tables.
APP_TABLES = set(target_metadata.tables.keys())  # {"accidents", "volunteers", "tasks"}


def include_object(object, name, type_, reflected, compare_to):
    """Only include objects that belong to our application models."""
    if type_ == "table":
        # Only manage tables defined in our SQLAlchemy models
        return name in APP_TABLES
    # For indexes, FKs, etc. — include only if they belong to our tables
    if hasattr(object, "table") and hasattr(object.table, "name"):
        return object.table.name in APP_TABLES
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

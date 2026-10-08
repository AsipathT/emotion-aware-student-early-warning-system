"""
backend/alembic/env.py

Alembic environment configuration.

Key design decisions
--------------------
1. Uses the **synchronous** psycopg2 DSN (sync_database_url) because Alembic
   does not support asyncpg natively.
2. Imports `Base` from `app.core.db` so autogenerate picks up every SQLAlchemy
   model that subclasses it.
3. Reads credentials from pydantic-settings (respects the .env file) rather
   than duplicating the URL in alembic.ini.
"""

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# ── Make sure `app.*` is importable ──────────────────────────────────────────
# alembic.ini sets prepend_sys_path = . (the backend/ directory), but we add
# it here as a belt-and-suspenders measure.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Project imports ───────────────────────────────────────────────────────────
from app.core.config import settings  # noqa: E402
from app.core.db import Base          # noqa: E402

# Import all model modules so their tables are registered on Base.metadata
# before autogenerate runs.  Add a line for every new model file you create.
import app.models.user          # noqa: F401
import app.models.profile       # noqa: F401

# ── Alembic Config ────────────────────────────────────────────────────────────
config = context.config

# Override sqlalchemy.url with the value from pydantic-settings so we don't
# have to hard-code credentials in alembic.ini.
config.set_main_option("sqlalchemy.url", settings.sync_database_url)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Target metadata ───────────────────────────────────────────────────────────
# This is the critical line: point Alembic at the shared declarative Base so
# `alembic revision --autogenerate` can diff the current DB schema against the
# SQLAlchemy model definitions.
target_metadata = Base.metadata


# ── Offline migrations ────────────────────────────────────────────────────────
def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine.  Calls to
    context.execute() emit the given string to the script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,          # detect column type changes
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ── Online migrations ─────────────────────────────────────────────────────────
def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    Creates an Engine and associates a connection with the context.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,   # don't pool in migration scripts
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

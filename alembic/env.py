from logging.config import fileConfig

from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from models import Base
target_metadata = Base.metadata

# Ensure DATABASE_URL is always used — never fall back to alembic.ini host
database_url = os.environ.get("DATABASE_URL")
if database_url:
    from db import normalize_database_url
    config.set_main_option("sqlalchemy.url", normalize_database_url(database_url))


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    CRITICAL FIX: Use the engine already built by db.py which reads DATABASE_URL
    from the environment. This avoids Alembic trying to connect using the raw
    hostname in alembic.ini which Render cannot resolve during build/startup.
    """
    from db import engine as db_engine

    with db_engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

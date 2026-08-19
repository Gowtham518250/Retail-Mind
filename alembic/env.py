from logging.config import fileConfig

from sqlalchemy import pool, inspect, text

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

    Uses the engine built by db.py, which reads DATABASE_URL from the
    environment. If the production database predates Alembic and already
    contains the application schema, adopt that existing schema as the
    initial revision instead of trying to recreate every table.
    """
    from db import engine as db_engine

    with db_engine.connect() as connection:
        if connection.dialect.name == 'postgresql':
            inspector = inspect(connection)
            tables = set(inspector.get_table_names())

            # PostgreSQL does not support IF EXISTS on ALTER COLUMN.
            if 'alembic_version' in tables:
                columns = [col['name'] for col in inspector.get_columns('alembic_version')]
                if 'version_num' in columns:
                    connection.execute(text(
                        "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(128)"
                    ))

                # Some older deployments have the Alembic table but no row.
                # If the application schema is already present, mark the
                # initial schema as applied so migration 001 is not replayed.
                current_version = connection.execute(
                    text("SELECT version_num FROM alembic_version LIMIT 1")
                ).scalar()
                if current_version is None and 'user_details' in tables:
                    connection.execute(text(
                        "INSERT INTO alembic_version (version_num) VALUES ('001_initial_schema')"
                    ))
                    connection.commit()
            elif 'user_details' in tables:
                # Legacy databases may have the application tables but no
                # Alembic bookkeeping table at all. Adopt the existing schema
                # as revision 001; subsequent migrations will still run.
                connection.execute(text(
                    "CREATE TABLE alembic_version (version_num VARCHAR(128) NOT NULL)"
                ))
                connection.execute(text(
                    "INSERT INTO alembic_version (version_num) VALUES ('001_initial_schema')"
                ))
                connection.commit()

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

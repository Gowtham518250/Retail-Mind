from logging.config import fileConfig

from sqlalchemy import inspect, text

from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from models import Base
target_metadata = Base.metadata

# Always use Render's DATABASE_URL when present.
database_url = os.environ.get("DATABASE_URL")
if database_url:
    from db import normalize_database_url
    config.set_main_option("sqlalchemy.url", normalize_database_url(database_url))


def run_migrations_offline() -> None:
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
    """Run migrations safely for both fresh and legacy PostgreSQL databases.

    Fresh database:
      - no application tables exist
      - Alembic starts normally from revision 001

    Legacy database:
      - application tables already exist
      - if Alembic has no recorded revision, adopt the existing schema at 001
        so the initial CREATE TABLE migration is not replayed.
    """
    from db import engine as db_engine

    with db_engine.connect() as connection:
        if connection.dialect.name == "postgresql":
            inspector = inspect(connection)
            tables = set(inspector.get_table_names())

            if "alembic_version" in tables:
                columns = [col["name"] for col in inspector.get_columns("alembic_version")]
                if "version_num" in columns:
                    connection.execute(text(
                        "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(128)"
                    ))

                current_version = connection.execute(
                    text("SELECT version_num FROM alembic_version LIMIT 1")
                ).scalar()

                # Only adopt a legacy schema when the Alembic table exists but
                # has no revision recorded and the application schema is present.
                if current_version is None and "user_details" in tables:
                    connection.execute(text(
                        "INSERT INTO alembic_version (version_num) VALUES ('001_initial_schema')"
                    ))
                    connection.commit()

            elif "user_details" in tables:
                # Legacy databases may have the application schema without
                # Alembic bookkeeping at all. Adopt it at revision 001.
                connection.execute(text(
                    "CREATE TABLE alembic_version (version_num VARCHAR(128) NOT NULL)"
                ))
                connection.execute(text(
                    "INSERT INTO alembic_version (version_num) VALUES ('001_initial_schema')"
                ))
                connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

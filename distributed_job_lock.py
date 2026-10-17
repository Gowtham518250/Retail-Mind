"""Transaction-scoped PostgreSQL advisory lock for singleton periodic jobs."""
import logging
from typing import Callable, Optional

from sqlalchemy import text

logger = logging.getLogger(__name__)


def run_with_advisory_lock(
    job: Callable[[], None],
    *,
    lock_id: int,
    engine=None,
) -> bool:
    """Run a job on one PostgreSQL process/replica at a time.

    The transaction remains open while the job runs, so the xact-scoped lock
    stays held across the job. On databases other than PostgreSQL the job runs
    directly for local/test compatibility; production deployments should use
    PostgreSQL for cross-replica coordination.
    """
    if engine is None:
        from db import engine as configured_engine

        engine = configured_engine

    if engine.dialect.name != "postgresql":
        job()
        return True

    try:
        with engine.connect() as connection:
            with connection.begin():
                acquired = bool(
                    connection.execute(
                        text("SELECT pg_try_advisory_xact_lock(:lock_id)"),
                        {"lock_id": int(lock_id)},
                    ).scalar()
                )
                if not acquired:
                    logger.debug("Periodic job skipped because another replica holds its lock")
                    return False
                job()
                return True
    except Exception as error:
        # Fail closed: do not execute a potentially duplicate job when the
        # database cannot provide its distributed lock.
        logger.error(
            "Periodic job was skipped because its database lock failed (error_type=%s)",
            type(error).__name__,
        )
        return False

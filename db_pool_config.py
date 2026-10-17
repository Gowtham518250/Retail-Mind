"""Conservative, environment-driven SQLAlchemy pool sizing.

Pool limits are per process. Multiply (pool_size + max_overflow) by the
number of server worker processes and instances to estimate the connection
ceiling presented to the PostgreSQL service.
"""
import logging
from typing import Mapping

logger = logging.getLogger(__name__)

DEFAULTS = {
    "DB_POOL_SIZE": (5, 1, 100),
    "DB_MAX_OVERFLOW": (5, 0, 100),
    "DB_POOL_TIMEOUT_SECONDS": (15, 1, 300),
    "DB_POOL_RECYCLE_SECONDS": (1800, 60, 86400),
    "WEB_CONCURRENCY": (1, 1, 128),
}


def _read_bounded_int(
    env: Mapping[str, str],
    name: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    """Read an integer setting without allowing invalid pool configuration."""
    raw = env.get(name)
    try:
        value = default if raw is None or not str(raw).strip() else int(raw)
    except (TypeError, ValueError):
        logger.warning("Invalid %s; using default %s", name, default)
        return default

    bounded = min(max(value, minimum), maximum)
    if bounded != value:
        logger.warning(
            "%s is outside the supported range; using the nearest bound (%s)",
            name,
            bounded,
        )
    return bounded


def pool_options_from_env(env: Mapping[str, str]) -> dict[str, int]:
    """Return SQLAlchemy QueuePool options, bounded to safe configuration."""
    return {
        "pool_size": _read_bounded_int(env, "DB_POOL_SIZE", 5, 1, 100),
        "max_overflow": _read_bounded_int(env, "DB_MAX_OVERFLOW", 5, 0, 100),
        "pool_timeout": _read_bounded_int(
            env, "DB_POOL_TIMEOUT_SECONDS", 15, 1, 300
        ),
        "pool_recycle": _read_bounded_int(
            env, "DB_POOL_RECYCLE_SECONDS", 1800, 60, 86400
        ),
    }


def estimated_connection_ceiling(
    options: Mapping[str, int],
    worker_count: int = 1,
    instance_count: int = 1,
) -> int:
    """Estimate the maximum app-to-database pool connections across workers."""
    workers = max(1, int(worker_count))
    instances = max(1, int(instance_count))
    per_process = int(options["pool_size"]) + int(options["max_overflow"])
    return per_process * workers * instances


def log_pool_budget(
    env: Mapping[str, str],
    options: Mapping[str, int],
) -> int:
    """Log the configured pool ceiling and warn when a budget is exceeded.

    DB_CONNECTION_BUDGET is optional because the actual provider limit is
    deployment-specific. This function never infers a database's real limit.
    """
    workers = _read_bounded_int(env, "WEB_CONCURRENCY", 1, 1, 128)
    instances = _read_bounded_int(env, "DB_APP_INSTANCE_COUNT", 1, 1, 1000)
    ceiling = estimated_connection_ceiling(options, workers, instances)
    logger.info(
        "Database pool ceiling: %s connections across %s instance(s) x %s worker(s)",
        ceiling,
        instances,
        workers,
    )

    raw_budget = env.get("DB_CONNECTION_BUDGET")
    if raw_budget:
        try:
            budget = int(raw_budget)
            if budget < 1:
                raise ValueError
        except (TypeError, ValueError):
            logger.warning("Invalid DB_CONNECTION_BUDGET; budget warning disabled")
        else:
            if ceiling > budget:
                logger.warning(
                    "Configured pool ceiling (%s) exceeds DB_CONNECTION_BUDGET (%s)",
                    ceiling,
                    budget,
                )
    return ceiling

import logging

from db_pool_config import (
    estimated_connection_ceiling,
    log_pool_budget,
    pool_options_from_env,
)


def test_pool_options_use_conservative_defaults():
    assert pool_options_from_env({}) == {
        "pool_size": 5,
        "max_overflow": 5,
        "pool_timeout": 15,
        "pool_recycle": 1800,
    }


def test_pool_options_accept_explicit_values():
    assert pool_options_from_env({
        "DB_POOL_SIZE": "8",
        "DB_MAX_OVERFLOW": "2",
        "DB_POOL_TIMEOUT_SECONDS": "20",
        "DB_POOL_RECYCLE_SECONDS": "3600",
    }) == {
        "pool_size": 8,
        "max_overflow": 2,
        "pool_timeout": 20,
        "pool_recycle": 3600,
    }


def test_invalid_values_fall_back_and_extreme_values_are_bounded(caplog):
    with caplog.at_level(logging.WARNING):
        options = pool_options_from_env({
            "DB_POOL_SIZE": "many",
            "DB_MAX_OVERFLOW": "-50",
            "DB_POOL_TIMEOUT_SECONDS": "999999",
        })

    assert options["pool_size"] == 5
    assert options["max_overflow"] == 0
    assert options["pool_timeout"] == 300
    assert "Invalid DB_POOL_SIZE" in caplog.text
    assert "outside the supported range" in caplog.text


def test_connection_ceiling_multiplies_pool_by_workers_and_instances():
    options = {"pool_size": 5, "max_overflow": 5}
    assert estimated_connection_ceiling(options, worker_count=2, instance_count=3) == 60


def test_configured_budget_warning_is_reported(caplog):
    with caplog.at_level(logging.WARNING):
        ceiling = log_pool_budget(
            {"WEB_CONCURRENCY": "2", "DB_APP_INSTANCE_COUNT": "3", "DB_CONNECTION_BUDGET": "50"},
            {"pool_size": 5, "max_overflow": 5},
        )

    assert ceiling == 60
    assert "exceeds DB_CONNECTION_BUDGET" in caplog.text

"""Timezone-safe helpers for legacy database datetime columns.

Several existing PostgreSQL columns use TIMESTAMP WITHOUT TIME ZONE. The
application convention for those naive timestamps is UTC, so normalize both
naive and aware values before comparing them in Python.
"""
from datetime import datetime, timezone
from typing import Optional


def as_utc_aware(value: Optional[datetime]) -> Optional[datetime]:
    """Return a datetime normalized to UTC with timezone information.

    Naive values from legacy timestamp-without-time-zone columns are treated
    as UTC. Aware values are converted to UTC.
    """
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def is_before_utc(
    value: Optional[datetime],
    reference: Optional[datetime] = None,
) -> bool:
    """Return whether value is earlier than reference/current UTC time."""
    normalized_value = as_utc_aware(value)
    if normalized_value is None:
        return False
    normalized_reference = as_utc_aware(
        reference if reference is not None else datetime.now(timezone.utc)
    )
    return normalized_value < normalized_reference


def is_after_utc(
    value: Optional[datetime],
    reference: Optional[datetime] = None,
) -> bool:
    """Return whether value is later than reference/current UTC time."""
    normalized_value = as_utc_aware(value)
    if normalized_value is None:
        return False
    normalized_reference = as_utc_aware(
        reference if reference is not None else datetime.now(timezone.utc)
    )
    return normalized_value > normalized_reference

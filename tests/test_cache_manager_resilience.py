import fnmatch

import caching_system


class FakeRedis:
    def __init__(self, ping_failures=0):
        self.ping_failures = ping_failures
        self.values = {}
        self.ttls = {}

    def ping(self):
        if self.ping_failures:
            self.ping_failures -= 1
            raise OSError("temporary Redis connection detail")
        return True

    def get(self, key):
        return self.values.get(key)

    def setex(self, key, ttl, value):
        self.values[key] = value
        self.ttls[key] = ttl
        return True

    def delete(self, *keys):
        removed = 0
        for key in keys:
            if key in self.values:
                del self.values[key]
                removed += 1
            self.ttls.pop(key, None)
        return removed

    def scan_iter(self, match, count=500):
        return iter(key for key in list(self.values) if fnmatch.fnmatchcase(key, match))

    def info(self):
        return {
            "used_memory_mb": 1,
            "connected_clients": 1,
            "keyspace_hits": 2,
            "keyspace_misses": 3,
        }

    def keys(self, *args, **kwargs):
        raise AssertionError("Cache deletion must not use Redis KEYS")


def test_cache_stays_disabled_when_redis_url_is_not_configured(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    manager = caching_system.CacheManager()

    assert manager.get("product:1") is None
    assert manager.set("product:1", {"id": 1}) is False
    assert manager.enabled is False


def test_cache_retries_after_transient_connection_failure(monkeypatch):
    fake = FakeRedis(ping_failures=1)
    monkeypatch.setenv("REDIS_URL", "redis://fake")
    monkeypatch.setattr(caching_system.CacheManager, "_build_client", lambda self: fake)

    manager = caching_system.CacheManager()
    assert manager.enabled is False

    # Simulate passage of the bounded retry interval.
    manager._retry_after = 0.0
    assert manager.set("product:1", {"id": 1}, ttl=15) is True
    assert manager.enabled is True
    assert manager.get("product:1") == {"id": 1}
    assert fake.ttls["app_cache:product:1"] == 15


def test_pattern_delete_uses_incremental_scan(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setenv("REDIS_URL", "redis://fake")
    monkeypatch.setattr(caching_system.CacheManager, "_build_client", lambda self: fake)
    manager = caching_system.CacheManager()

    fake.values.update({
        "app_cache:product:1": b"{}",
        "app_cache:product:2": b"{}",
        "app_cache:analytics:today": b"{}",
    })

    assert manager.delete_pattern("product:") == 2
    assert sorted(fake.values) == ["app_cache:analytics:today"]
    assert manager.clear_all() is True
    assert fake.values == {}

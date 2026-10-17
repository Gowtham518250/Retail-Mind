import time

import rate_limiter as rl


class FakeRedis:
    def __init__(self, failures=0, fail_counter=False):
        self.failures = failures
        self.fail_counter = fail_counter
        self.values = {}
        self.expiries = {}
        self.ping_calls = 0
        self.scripts = []

    def ping(self):
        self.ping_calls += 1
        if self.failures:
            self.failures -= 1
            raise OSError("temporary connection failure")
        return True

    def eval(self, script, count, key, window):
        self.scripts.append(script)
        if self.fail_counter:
            raise OSError("counter unavailable")
        value = int(self.values.get(key, 0)) + 1
        self.values[key] = value
        if value == 1:
            self.expiries[key] = time.monotonic() + int(window)
        return value

    def get(self, key):
        return self.values.get(key)


def test_rate_limit_window_does_not_extend_on_every_request(monkeypatch):
    client = FakeRedis()
    monkeypatch.setattr(rl, "REDIS_URL", "redis://localhost:6379")
    monkeypatch.setattr(rl, "redis_client", client)
    monkeypatch.setattr(rl, "USE_REDIS", True)
    limiter = rl.RateLimiter()

    assert limiter.is_allowed("192.0.2.1", "checkout")[0]
    key = "rate_limit:192.0.2.1:checkout"
    original_expiry = client.expiries[key]
    assert limiter.is_allowed("192.0.2.1", "checkout")[0]
    assert client.expiries[key] == original_expiry
    assert "if count == 1" in client.scripts[0]


def test_redis_recovers_after_a_transient_ping_failure(monkeypatch):
    client = FakeRedis(failures=1)
    monkeypatch.setattr(rl, "REDIS_URL", "redis://localhost:6379")
    monkeypatch.setattr(rl, "redis_client", client)
    monkeypatch.setattr(rl, "USE_REDIS", False)
    monkeypatch.setattr(rl, "_next_redis_retry_at", 0.0)

    assert rl._redis_available() is False
    monkeypatch.setattr(rl, "_next_redis_retry_at", 0.0)
    assert rl._redis_available() is True
    assert rl.USE_REDIS is True
    assert client.ping_calls == 2


def test_redis_command_failure_falls_back_without_crashing(monkeypatch):
    client = FakeRedis(fail_counter=True)
    monkeypatch.setattr(rl, "REDIS_URL", "redis://localhost:6379")
    monkeypatch.setattr(rl, "redis_client", client)
    monkeypatch.setattr(rl, "USE_REDIS", True)
    monkeypatch.setattr(rl, "_next_redis_retry_at", 0.0)
    limiter = rl.RateLimiter()

    allowed, remaining = limiter.is_allowed("192.0.2.2", "checkout")

    assert allowed
    assert remaining == limiter.limits["default"] - 1
    assert rl.USE_REDIS is False
    assert rl._next_redis_retry_at > 0

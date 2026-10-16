from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import security


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.ttls = {}

    def incr(self, key):
        self.values[key] = int(self.values.get(key, 0)) + 1
        return self.values[key]

    def expire(self, key, seconds):
        self.ttls[key] = seconds
        return True

    def get(self, key):
        return self.values.get(key)

    def ttl(self, key):
        return self.ttls.get(key, -1)

    def set(self, key, value, ex=None):
        self.values[key] = value
        if ex is not None:
            self.ttls[key] = ex
        return True

    def delete(self, *keys):
        removed = 0
        for key in keys:
            if key in self.values:
                del self.values[key]
                removed += 1
            self.ttls.pop(key, None)
        return removed


def test_request_rate_limit_uses_shared_redis_counter(monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr(security, "_get_security_redis_client", lambda: fake_redis)
    monkeypatch.setattr(security, "RATE_LIMIT_CALLS", 2)
    monkeypatch.setattr(security, "RATE_LIMIT_WINDOW_SECS", 60)
    security._rate_limit_store.clear()

    request = SimpleNamespace(client=SimpleNamespace(host="192.0.2.10"))
    security.check_rate_limit(request)
    security.check_rate_limit(request)

    with pytest.raises(HTTPException) as error:
        security.check_rate_limit(request)
    assert error.value.status_code == 429


def test_login_lockout_is_shared_and_success_clears_it(monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr(security, "_get_security_redis_client", lambda: fake_redis)
    monkeypatch.setattr(security, "LOGIN_MAX_FAILS", 2)
    monkeypatch.setattr(security, "LOGIN_LOCKOUT_SECS", 300)
    security._login_fail_store.clear()
    security._login_lockout.clear()

    ip = "192.0.2.11"
    security.record_login_failure(ip)
    security.check_login_lockout(ip)
    security.record_login_failure(ip)

    with pytest.raises(HTTPException) as error:
        security.check_login_lockout(ip)
    assert error.value.status_code == 429

    security.record_login_success(ip)
    security.check_login_lockout(ip)

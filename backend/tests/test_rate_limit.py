from app.core import rate_limit


def test_rate_windows_expire_and_return_capacity(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(rate_limit, "monotonic", lambda: clock[0])
    limiter = rate_limit.SlidingWindow(window=60, max_keys=2)
    assert limiter.check("a", 1)
    assert not limiter.check("a", 1)
    assert limiter.check("b", 1)
    assert not limiter.check("c", 1)
    clock[0] += 61
    assert limiter.check("c", 1)
    assert set(limiter.requests) == {"c"}
    limiter.refund("c")
    assert limiter.requests == {}


def test_shared_window_reserves_and_refunds_exact_attempt(monkeypatch):
    class FakeRedis:
        def __init__(self):
            self.values = {}

        def eval(self, _script, _count, key, _window, limit, reservation):
            values = self.values.setdefault(key, set())
            if len(values) >= limit:
                return 0
            values.add(reservation)
            return 1

        def zrem(self, key, reservation):
            self.values.get(key, set()).discard(reservation)

        def delete(self, key):
            self.values.pop(key, None)

    fake = FakeRedis()
    monkeypatch.setattr(rate_limit.redis.Redis, "from_url", lambda *_args, **_kwargs: fake)
    first = rate_limit.DistributedWindow("redis://localhost")
    second = rate_limit.DistributedWindow("redis://localhost")
    assert first.check("login:person", 2)
    assert second.check("login:person", 2)
    assert not first.check("login:person", 2)
    second.refund("login:person")
    assert first.check("login:person", 2)
    first.clear("login:person")
    assert second.check("login:person", 2)

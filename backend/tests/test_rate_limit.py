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

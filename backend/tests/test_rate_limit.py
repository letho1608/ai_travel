from app.services.rate_limit import RateLimiter


def test_memory_limiter_check_many_is_all_or_nothing():
    limiter = RateLimiter()
    assert limiter.check("session", 1, 60)

    allowed = limiter.check_many([
        ("ip", 10, 60),
        ("session", 1, 60),
    ])

    assert allowed is False
    assert limiter.check("ip", 10, 60) is True


def test_memory_limiter_check_many_fails_closed_when_unavailable():
    limiter = RateLimiter()
    limiter.available = False

    assert limiter.check_many([("ip", 10, 60), ("session", 1, 60)]) is False

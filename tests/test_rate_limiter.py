import time
import pytest


class TestRateLimiter:
    def test_allows_within_limit(self):
        from src.security.rate_limiter import RateLimiter

        limiter = RateLimiter(limits={"mouse": 60})
        for _ in range(60):
            assert limiter.check("mouse") is True

    def test_blocks_over_limit(self):
        from src.security.rate_limiter import RateLimiter

        limiter = RateLimiter(limits={"mouse": 5})
        for _ in range(5):
            limiter.check("mouse")
        assert limiter.check("mouse") is False

    def test_unknown_category_allowed(self):
        from src.security.rate_limiter import RateLimiter

        limiter = RateLimiter(limits={"mouse": 5})
        assert limiter.check("unknown_tool") is True

    def test_resets_after_window(self):
        from src.security.rate_limiter import RateLimiter

        limiter = RateLimiter(limits={"mouse": 2}, window_seconds=1)
        limiter.check("mouse")
        limiter.check("mouse")
        assert limiter.check("mouse") is False
        time.sleep(1.1)
        assert limiter.check("mouse") is True

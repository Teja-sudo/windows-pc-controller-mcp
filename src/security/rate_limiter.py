"""Sliding-window rate limiter per tool category."""
from __future__ import annotations

import time
from collections import defaultdict


class RateLimiter:
    """Per-category rate limiter using a sliding time window."""

    def __init__(self, limits: dict[str, int], window_seconds: float = 60.0):
        self._limits = limits
        self._window = window_seconds
        self._calls: dict[str, list[float]] = defaultdict(list)

    def check(self, category: str) -> bool:
        """Return True if the action is allowed, False if rate-limited."""
        if category not in self._limits:
            return True

        now = time.monotonic()
        cutoff = now - self._window

        # Prune old entries
        self._calls[category] = [t for t in self._calls[category] if t > cutoff]

        if len(self._calls[category]) >= self._limits[category]:
            return False

        self._calls[category].append(now)
        return True

"""Sensitive content masking for screenshots and text."""
from __future__ import annotations

from typing import Any


def filter_windows(
    windows: list[dict[str, Any]],
    blocked_apps: list[str],
) -> list[dict[str, Any]]:
    """Remove windows belonging to blocked apps from the list."""
    if not blocked_apps:
        return windows
    blocked_lower = [app.lower() for app in blocked_apps]
    return [
        w for w in windows
        if not any(blocked in w.get("title", "").lower() for blocked in blocked_lower)
        and not any(blocked in w.get("process", "").lower() for blocked in blocked_lower)
    ]


def should_redact_window(window_title: str, blocked_apps: list[str]) -> bool:
    """Check if a window's content should be redacted."""
    title_lower = window_title.lower()
    return any(app.lower() in title_lower for app in blocked_apps)

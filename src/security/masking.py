"""Sensitive content masking for screenshots and text."""
from __future__ import annotations

from typing import Any


def _get_process_name(w: dict[str, Any]) -> str:
    """Get process name from a window dict, handling both key conventions."""
    return (w.get("process_name") or w.get("process") or "").lower()


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
        and not any(blocked in _get_process_name(w) for blocked in blocked_lower)
    ]


def is_window_blocked(title: str, process_name: str, blocked_apps: list[str]) -> bool:
    """Check if a window with the given title/process is blocked."""
    if not blocked_apps:
        return False
    title_lower = title.lower()
    proc_lower = process_name.lower()
    return any(
        app.lower() in title_lower or app.lower() in proc_lower
        for app in blocked_apps
    )


def should_redact_window(window_title: str, blocked_apps: list[str]) -> bool:
    """Check if a window's content should be redacted."""
    title_lower = window_title.lower()
    return any(app.lower() in title_lower for app in blocked_apps)

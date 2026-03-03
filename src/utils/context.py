"""Lightweight context snapshot — cursor position + active window + timestamp."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pynput.mouse import Controller as MouseController

from src.utils.win32_helpers import get_active_window_title

_mouse = MouseController()

# Scale factor cache for screenshot coordinate conversion (Batch 2)
_last_screenshot_scale: float = 1.0


def set_screenshot_scale(scale: float) -> None:
    """Cache the most recent screenshot downscale factor."""
    global _last_screenshot_scale
    _last_screenshot_scale = scale


def get_screenshot_scale() -> float:
    """Return the cached screenshot downscale factor."""
    return _last_screenshot_scale


def get_context() -> dict[str, Any]:
    """Return a lightweight context snapshot (<1ms total).

    Includes cursor position, active window title, and ISO timestamp.
    Designed to be appended to every tool response as ``_context``.
    """
    try:
        x, y = _mouse.position
        cursor = {"x": int(x), "y": int(y)}
    except Exception:
        cursor = {"x": 0, "y": 0}

    try:
        active = get_active_window_title()
    except Exception:
        active = ""

    return {
        "cursor": cursor,
        "active_window": active,
        "timestamp": datetime.now(timezone.utc).strftime("%H:%M:%S"),
    }

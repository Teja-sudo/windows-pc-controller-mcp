"""Lightweight context snapshot — cursor position + active window + timestamp."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.utils.win32_helpers import get_active_window_title
from src.utils import mouse_backend as _mouse_backend

# Scale factor cache for screenshot coordinate conversion (Batch 2)
_last_screenshot_scale: float = 1.0
# Screen offset of the captured region (window captures start at window position)
_last_screenshot_offset: tuple[int, int] = (0, 0)


def set_screenshot_scale(scale: float, offset: tuple[int, int] = (0, 0)) -> None:
    """Cache the most recent screenshot downscale factor and screen offset."""
    global _last_screenshot_scale, _last_screenshot_offset
    _last_screenshot_scale = scale
    _last_screenshot_offset = offset


def get_screenshot_scale() -> float:
    """Return the cached screenshot downscale factor."""
    return _last_screenshot_scale


def get_screenshot_offset() -> tuple[int, int]:
    """Return the cached screenshot screen offset (left, top)."""
    return _last_screenshot_offset


def get_context() -> dict[str, Any]:
    """Return a lightweight context snapshot (<1ms total).

    Includes cursor position, active window title, and ISO timestamp.
    Designed to be appended to every tool response as ``_context``.
    """
    try:
        x, y = _mouse_backend.get_cursor_pos()
        cursor = {"x": x, "y": y}
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

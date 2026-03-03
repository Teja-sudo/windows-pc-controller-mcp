"""Parameter normalization — alias mapping + type coercion for lenient tool params."""
from __future__ import annotations

from typing import Any


# ── Per-tool alias maps ─────────────────────────────────────
# Maps common agent mistakes / natural language param names to the canonical names.
_ALIASES: dict[str, dict[str, str]] = {
    "focus_window": {
        "window_title": "title",
        "window": "title",
        "name": "title",
        "process_name": "process",
        "app": "process",
    },
    "close_window": {
        "window_title": "title",
        "window": "title",
        "name": "title",
        "process_name": "process",
        "app": "process",
    },
    "wait_for_window": {
        "window_title": "title",
        "window": "title",
        "process_name": "process",
    },
    "launch_app": {
        "application": "app",
        "program": "app",
        "executable": "app",
        "path": "app",
    },
    "keyboard_type": {
        "content": "text",
        "string": "text",
        "message": "text",
    },
    "keyboard_hotkey": {
        "shortcut": "keys",
        "hotkey": "keys",
        "combo": "keys",
    },
    "click_text": {
        "label": "text",
        "content": "text",
        "string": "text",
    },
    "clipboard_write": {
        "content": "text",
        "data": "text",
        "string": "text",
    },
    "mouse_click": {
        "count": "clicks",
    },
    "mouse_scroll": {
        "count": "clicks",
        "amount": "clicks",
        "steps": "clicks",
    },
    "type_text": {
        "content": "text",
        "string": "text",
        "message": "text",
    },
    "window_manage": {
        "window_title": "title",
        "window": "title",
        "process_name": "process",
    },
    "open_url": {
        "link": "url",
        "href": "url",
        "address": "url",
    },
}

# Fields that should be coerced to int (coordinate fields, counts)
_INT_FIELDS = frozenset({
    "x", "y", "x1", "y1", "x2", "y2",
    "start_x", "start_y", "end_x", "end_y",
    "clicks", "count", "monitor", "keycode",
    "width", "height", "left", "top",
    "occurrence", "dx", "dy",
})


def normalize_params(tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
    """Normalize tool parameters: apply aliases then coerce types.

    This is called once in the server before dispatch, making all tools
    tolerant of common agent mistakes without per-tool code.
    """
    aliases = _ALIASES.get(tool_name, {})
    result: dict[str, Any] = {}

    for key, value in params.items():
        # Apply alias if the canonical name isn't already present
        canonical = aliases.get(key, key)
        if canonical != key and canonical in params:
            # Don't override an explicitly provided canonical param
            canonical = key
        result[canonical] = value

    # Type coercion: string numbers → int for coordinate fields
    for key in _INT_FIELDS:
        if key in result and isinstance(result[key], str):
            try:
                result[key] = int(result[key])
            except (ValueError, TypeError):
                pass  # leave as-is, let the tool raise a meaningful error

    return result

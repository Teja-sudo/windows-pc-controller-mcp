"""Mouse control tools — move, click, drag, scroll, position."""
from __future__ import annotations

import time
from typing import Any

from pynput.mouse import Button, Controller


_mouse = Controller()

_BUTTON_MAP = {
    "left": Button.left,
    "right": Button.right,
    "middle": Button.middle,
}


def mouse_position() -> dict[str, Any]:
    """Get current mouse cursor position."""
    try:
        x, y = _mouse.position
        return {"success": True, "x": int(x), "y": int(y)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def mouse_move(x: int, y: int, relative: bool = False) -> dict[str, Any]:
    """Move cursor to absolute or relative coordinates."""
    try:
        if relative:
            current_x, current_y = _mouse.position
            _mouse.position = (current_x + x, current_y + y)
        else:
            _mouse.position = (x, y)
        final_x, final_y = _mouse.position
        return {"success": True, "x": int(final_x), "y": int(final_y)}
    except Exception as e:
        return {"success": False, "error": str(e), "suggestion": "Check coordinates are within screen bounds"}


def mouse_click(
    x: int | None = None,
    y: int | None = None,
    button: str = "left",
    clicks: int = 1,
) -> dict[str, Any]:
    """Click at coordinates. If x,y not given, clicks at current position."""
    try:
        if x is not None and y is not None:
            _mouse.position = (x, y)
            time.sleep(0.01)

        btn = _BUTTON_MAP.get(button, Button.left)
        _mouse.click(btn, clicks)
        return {"success": True, "button": button, "clicks": clicks}
    except Exception as e:
        return {"success": False, "error": str(e)}


def mouse_drag(
    start_x: int, start_y: int,
    end_x: int, end_y: int,
    button: str = "left",
    duration: float = 0.5,
) -> dict[str, Any]:
    """Click and drag from start to end coordinates."""
    try:
        btn = _BUTTON_MAP.get(button, Button.left)
        _mouse.position = (start_x, start_y)
        time.sleep(0.05)

        _mouse.press(btn)
        steps = max(int(duration * 60), 10)
        dx = (end_x - start_x) / steps
        dy = (end_y - start_y) / steps

        for i in range(steps):
            _mouse.position = (int(start_x + dx * (i + 1)), int(start_y + dy * (i + 1)))
            time.sleep(duration / steps)

        _mouse.release(btn)
        return {"success": True, "start": [start_x, start_y], "end": [end_x, end_y]}
    except Exception as e:
        return {"success": False, "error": str(e)}


def mouse_scroll(dx: int = 0, dy: int = 0) -> dict[str, Any]:
    """Scroll by dx (horizontal) and dy (vertical) clicks."""
    try:
        _mouse.scroll(dx, dy)
        return {"success": True, "dx": dx, "dy": dy}
    except Exception as e:
        return {"success": False, "error": str(e)}

"""Mouse control tools — move, click, drag, scroll, position."""
from __future__ import annotations

import time
from typing import Any

from pynput.mouse import Button, Controller

from src.utils.errors import tool_error, tool_success, OS_ERROR
from src.utils.context import get_screenshot_scale


_mouse = Controller()

_BUTTON_MAP = {
    "left": Button.left,
    "right": Button.right,
    "middle": Button.middle,
}


def _convert_coords(x: int, y: int, from_screenshot: bool) -> tuple[int, int]:
    """Convert screenshot pixel coords to screen coords if needed."""
    if from_screenshot:
        scale = get_screenshot_scale()
        if scale != 1.0:
            x = int(x * scale)
            y = int(y * scale)
    return x, y


def mouse_position() -> dict[str, Any]:
    """Get current mouse cursor position."""
    try:
        x, y = _mouse.position
        return tool_success(x=int(x), y=int(y))
    except Exception as e:
        return tool_error(str(e), OS_ERROR, suggestion="This tool requires a display session")


def mouse_move(
    x: int, y: int,
    relative: bool = False,
    from_screenshot: bool = False,
) -> dict[str, Any]:
    """Move cursor to absolute or relative coordinates."""
    try:
        if not relative:
            x, y = _convert_coords(x, y, from_screenshot)
        if relative:
            current_x, current_y = _mouse.position
            _mouse.position = (current_x + x, current_y + y)
        else:
            _mouse.position = (x, y)
        final_x, final_y = _mouse.position
        return tool_success(x=int(final_x), y=int(final_y))
    except Exception as e:
        return tool_error(str(e), OS_ERROR, suggestion="Check coordinates are within screen bounds")


def mouse_click(
    x: int | None = None,
    y: int | None = None,
    button: str = "left",
    clicks: int = 1,
    from_screenshot: bool = False,
) -> dict[str, Any]:
    """Click at coordinates. If x,y not given, clicks at current position."""
    try:
        if x is not None and y is not None:
            x, y = _convert_coords(x, y, from_screenshot)
            _mouse.position = (x, y)
            time.sleep(0.01)

        btn = _BUTTON_MAP.get(button, Button.left)
        _mouse.click(btn, clicks)
        return tool_success(button=button, clicks=clicks)
    except Exception as e:
        return tool_error(str(e), OS_ERROR, suggestion="Check coordinates are within screen bounds. Use get_screen_info to verify screen dimensions.")


def mouse_drag(
    start_x: int, start_y: int,
    end_x: int, end_y: int,
    button: str = "left",
    duration: float = 0.5,
    from_screenshot: bool = False,
) -> dict[str, Any]:
    """Click and drag from start to end coordinates."""
    try:
        start_x, start_y = _convert_coords(start_x, start_y, from_screenshot)
        end_x, end_y = _convert_coords(end_x, end_y, from_screenshot)

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
        return tool_success(start=[start_x, start_y], end=[end_x, end_y])
    except Exception as e:
        return tool_error(str(e), OS_ERROR, suggestion="Check that start and end coordinates are within screen bounds")


def mouse_scroll(dx: int = 0, dy: int = 0) -> dict[str, Any]:
    """Scroll by dx (horizontal) and dy (vertical) clicks."""
    try:
        _mouse.scroll(dx, dy)
        return tool_success(dx=dx, dy=dy)
    except Exception as e:
        return tool_error(str(e), OS_ERROR, suggestion="Move mouse to the target area first with mouse_move before scrolling")

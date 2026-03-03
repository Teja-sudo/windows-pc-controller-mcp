"""Mouse control tools — move, click, drag, scroll, position.

Uses direct ctypes SendInput for pixel-perfect, atomic operations.
No pynput dependency — pure Win32 API via ctypes.
"""
from __future__ import annotations

from typing import Any

from src.utils import mouse_backend as _backend
from src.utils.errors import tool_error, tool_success, OS_ERROR
from src.utils.context import get_screenshot_scale, get_screenshot_offset


def _convert_coords(x: int, y: int, from_screenshot: bool) -> tuple[int, int]:
    """Convert screenshot pixel coords to screen coords if needed.

    Applies both the downscale factor and the screen offset of the captured
    region (important for window captures which start at the window's position,
    not at screen origin).
    """
    if from_screenshot:
        scale = get_screenshot_scale()
        offset_x, offset_y = get_screenshot_offset()
        x = int(x * scale) + offset_x
        y = int(y * scale) + offset_y
    return x, y


def mouse_position() -> dict[str, Any]:
    """Get current mouse cursor position."""
    try:
        x, y = _backend.get_cursor_pos()
        return tool_success(x=x, y=y)
    except Exception as e:
        return tool_error(str(e), OS_ERROR, suggestion="This tool requires a display session")


def mouse_move(
    x: int, y: int,
    relative: bool = False,
    from_screenshot: bool = False,
) -> dict[str, Any]:
    """Move cursor to absolute or relative coordinates."""
    try:
        if relative:
            final_x, final_y = _backend.move_relative(x, y)
        else:
            x, y = _convert_coords(x, y, from_screenshot)
            final_x, final_y = _backend.move(x, y)
        return tool_success(x=final_x, y=final_y)
    except Exception as e:
        return tool_error(str(e), OS_ERROR, suggestion="Check coordinates are within screen bounds")


def mouse_click(
    x: int | None = None,
    y: int | None = None,
    button: str = "left",
    clicks: int = 1,
    from_screenshot: bool = False,
) -> dict[str, Any]:
    """Click at coordinates. If x,y not given, clicks at current position.

    Move and click are sent as a single atomic SendInput call — no
    coordinate drift between move and click.
    """
    try:
        if x is not None and y is not None:
            x, y = _convert_coords(x, y, from_screenshot)
        _backend.click(x=x, y=y, button=button, clicks=clicks)
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
        _backend.drag(start_x, start_y, end_x, end_y, button=button, duration=duration)
        return tool_success(start=[start_x, start_y], end=[end_x, end_y])
    except Exception as e:
        return tool_error(str(e), OS_ERROR, suggestion="Check that start and end coordinates are within screen bounds")


def mouse_scroll(dx: int = 0, dy: int = 0) -> dict[str, Any]:
    """Scroll by dx (horizontal) and dy (vertical) clicks."""
    try:
        _backend.scroll(dx=dx, dy=dy)
        return tool_success(dx=dx, dy=dy)
    except Exception as e:
        return tool_error(str(e), OS_ERROR, suggestion="Move mouse to the target area first with mouse_move before scrolling")

"""Direct ctypes SendInput mouse backend — pixel-perfect, zero-dependency.

Replaces pynput for mouse control. Key advantages:
- Atomic move+click in a single SendInput call (no coordinate drift)
- Proper virtual desktop coordinate conversion (multi-monitor)
- DPI-independent via 0-65535 absolute coordinate space
- No external dependencies (ctypes is stdlib)

All public functions accept physical screen pixel coordinates.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import time

# ── Win32 Constants ───────────────────────────────────────────
MOUSEEVENTF_MOVE        = 0x0001
MOUSEEVENTF_LEFTDOWN    = 0x0002
MOUSEEVENTF_LEFTUP      = 0x0004
MOUSEEVENTF_RIGHTDOWN   = 0x0008
MOUSEEVENTF_RIGHTUP     = 0x0010
MOUSEEVENTF_MIDDLEDOWN  = 0x0020
MOUSEEVENTF_MIDDLEUP    = 0x0040
MOUSEEVENTF_WHEEL       = 0x0800
MOUSEEVENTF_HWHEEL      = 0x1000
MOUSEEVENTF_ABSOLUTE    = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000

INPUT_MOUSE = 0
WHEEL_DELTA = 120

SM_XVIRTUALSCREEN  = 76
SM_YVIRTUALSCREEN  = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

# ── Button Maps ───────────────────────────────────────────────
BUTTON_DOWN = {
    "left":   MOUSEEVENTF_LEFTDOWN,
    "right":  MOUSEEVENTF_RIGHTDOWN,
    "middle": MOUSEEVENTF_MIDDLEDOWN,
}
BUTTON_UP = {
    "left":   MOUSEEVENTF_LEFTUP,
    "right":  MOUSEEVENTF_RIGHTUP,
    "middle": MOUSEEVENTF_MIDDLEUP,
}


# ── ctypes Structures (matches Windows INPUT union) ──────────
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx",          ctypes.wintypes.LONG),
        ("dy",          ctypes.wintypes.LONG),
        ("mouseData",   ctypes.wintypes.DWORD),
        ("dwFlags",     ctypes.wintypes.DWORD),
        ("time",        ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk",         ctypes.wintypes.WORD),
        ("wScan",       ctypes.wintypes.WORD),
        ("dwFlags",     ctypes.wintypes.DWORD),
        ("time",        ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg",    ctypes.wintypes.DWORD),
        ("wParamL", ctypes.wintypes.WORD),
        ("wParamH", ctypes.wintypes.WORD),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type",  ctypes.wintypes.DWORD),
        ("union", _INPUT_UNION),
    ]


# ── Win32 function bindings ──────────────────────────────────
_user32 = ctypes.windll.user32

_SendInput = _user32.SendInput
_SendInput.argtypes = [ctypes.wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
_SendInput.restype = ctypes.wintypes.UINT

_GetSystemMetrics = _user32.GetSystemMetrics
_GetSystemMetrics.argtypes = [ctypes.c_int]
_GetSystemMetrics.restype = ctypes.c_int

_GetCursorPos = _user32.GetCursorPos
_GetCursorPos.argtypes = [ctypes.POINTER(ctypes.wintypes.POINT)]
_GetCursorPos.restype = ctypes.wintypes.BOOL


# ── Coordinate Conversion ───────────────────────────────────
def _to_absolute(x: int, y: int) -> tuple[int, int]:
    """Convert physical pixel coords to SendInput 0-65535 absolute range.

    Uses virtual desktop metrics for multi-monitor support.
    The ``-1`` in the divisor is critical for pixel-perfect accuracy at screen edges.
    """
    vx = _GetSystemMetrics(SM_XVIRTUALSCREEN)
    vy = _GetSystemMetrics(SM_YVIRTUALSCREEN)
    vw = _GetSystemMetrics(SM_CXVIRTUALSCREEN)
    vh = _GetSystemMetrics(SM_CYVIRTUALSCREEN)

    abs_x = int((x - vx) * 65535 / (vw - 1))
    abs_y = int((y - vy) * 65535 / (vh - 1))
    return abs_x, abs_y


# ── Core SendInput helpers ───────────────────────────────────
def _make_mouse_input(
    dx: int = 0, dy: int = 0,
    flags: int = 0, mouse_data: int = 0,
) -> INPUT:
    """Build a single INPUT structure for a mouse event."""
    inp = INPUT()
    inp.type = INPUT_MOUSE
    inp.union.mi.dx = dx
    inp.union.mi.dy = dy
    inp.union.mi.dwFlags = flags
    inp.union.mi.mouseData = mouse_data
    inp.union.mi.time = 0
    inp.union.mi.dwExtraInfo = None
    return inp


def _send_inputs(*inputs: INPUT) -> int:
    """Send one or more INPUT events atomically via SendInput."""
    n = len(inputs)
    arr = (INPUT * n)(*inputs)
    return _SendInput(n, arr, ctypes.sizeof(INPUT))


_MOVE_FLAGS = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK


# ── Public API ───────────────────────────────────────────────
def get_cursor_pos() -> tuple[int, int]:
    """Return current cursor (x, y) in physical screen pixels."""
    point = ctypes.wintypes.POINT()
    _GetCursorPos(ctypes.byref(point))
    return point.x, point.y


def move(x: int, y: int) -> tuple[int, int]:
    """Move cursor to absolute physical pixel coordinates. Returns final (x, y)."""
    abs_x, abs_y = _to_absolute(x, y)
    _send_inputs(_make_mouse_input(dx=abs_x, dy=abs_y, flags=_MOVE_FLAGS))
    return get_cursor_pos()


def move_relative(dx: int, dy: int) -> tuple[int, int]:
    """Move cursor relative to current position. Returns final (x, y).

    Uses absolute positioning (get pos + offset) instead of relative mickeys,
    because mickeys are affected by mouse acceleration/speed settings.
    """
    cx, cy = get_cursor_pos()
    return move(cx + dx, cy + dy)


def click(
    x: int | None = None,
    y: int | None = None,
    button: str = "left",
    clicks: int = 1,
) -> tuple[int, int]:
    """Click at (x, y) or at current position if coords are None.

    Move + click are batched in a single SendInput call — atomic,
    no gap where another event could interfere.
    """
    down_flag = BUTTON_DOWN.get(button, MOUSEEVENTF_LEFTDOWN)
    up_flag = BUTTON_UP.get(button, MOUSEEVENTF_LEFTUP)

    events: list[INPUT] = []

    # Move to target (atomic with the click)
    if x is not None and y is not None:
        abs_x, abs_y = _to_absolute(x, y)
        events.append(_make_mouse_input(dx=abs_x, dy=abs_y, flags=_MOVE_FLAGS))

    # Click(s) — down + up for each click
    for _ in range(clicks):
        events.append(_make_mouse_input(flags=down_flag))
        events.append(_make_mouse_input(flags=up_flag))

    _send_inputs(*events)
    return get_cursor_pos()


def drag(
    start_x: int, start_y: int,
    end_x: int, end_y: int,
    button: str = "left",
    duration: float = 0.5,
) -> tuple[int, int]:
    """Smooth drag from start to end. Returns final position."""
    down_flag = BUTTON_DOWN.get(button, MOUSEEVENTF_LEFTDOWN)
    up_flag = BUTTON_UP.get(button, MOUSEEVENTF_LEFTUP)

    steps = max(int(duration * 60), 10)

    # Move to start + press button (atomic)
    abs_sx, abs_sy = _to_absolute(start_x, start_y)
    _send_inputs(
        _make_mouse_input(dx=abs_sx, dy=abs_sy, flags=_MOVE_FLAGS),
        _make_mouse_input(flags=down_flag),
    )

    # Interpolated smooth movement
    sleep_per_step = duration / steps
    for i in range(1, steps + 1):
        t = i / steps
        cx = int(start_x + (end_x - start_x) * t)
        cy = int(start_y + (end_y - start_y) * t)
        abs_cx, abs_cy = _to_absolute(cx, cy)
        _send_inputs(_make_mouse_input(dx=abs_cx, dy=abs_cy, flags=_MOVE_FLAGS))
        time.sleep(sleep_per_step)

    # Release button
    _send_inputs(_make_mouse_input(flags=up_flag))
    return get_cursor_pos()


def scroll(dx: int = 0, dy: int = 0) -> None:
    """Scroll by dx (horizontal) and dy (vertical) notches.

    Positive dy = scroll up, negative dy = scroll down.
    Positive dx = scroll right, negative dx = scroll left.
    """
    events: list[INPUT] = []
    if dy != 0:
        events.append(_make_mouse_input(
            flags=MOUSEEVENTF_WHEEL,
            mouse_data=dy * WHEEL_DELTA,
        ))
    if dx != 0:
        events.append(_make_mouse_input(
            flags=MOUSEEVENTF_HWHEEL,
            mouse_data=dx * WHEEL_DELTA,
        ))
    if events:
        _send_inputs(*events)

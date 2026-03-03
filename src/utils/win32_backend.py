"""Win32 SendMessage backend — Tier 1 targeting via native controls.

Enumerates child windows (buttons, checkboxes, static text, etc.) using
EnumChildWindows and sends BM_CLICK / WM_COMMAND messages directly — no
coordinates, no mouse movement, sub-millisecond.

Only works for classic Win32 controls (dialogs, message boxes, legacy apps).
Modern UI frameworks (WPF, UWP, Electron) draw their own controls and will
return an empty list from find_win32_controls().

All functions are synchronous and use ctypes only (no pywin32 required here).
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes
from typing import Any

# ── Win32 constants ─────────────────────────────────────────
BM_CLICK = 0x00F5
WM_GETTEXT = 0x000D
WM_GETTEXTLENGTH = 0x000E
GWL_ID = -12
GWL_STYLE = -16

# Window styles for control identification
BS_PUSHBUTTON = 0x0000
BS_CHECKBOX = 0x0002
BS_RADIOBUTTON = 0x0004
BS_GROUPBOX = 0x0007
BS_AUTOCHECKBOX = 0x0003
BS_AUTORADIOBUTTON = 0x0009
BS_PUSHLIKE = 0x1000

# Standard Win32 control class names → friendly type names
_CLASS_TYPE_MAP = {
    "button": "button",
    "static": "label",
    "edit": "textbox",
    "combobox": "combobox",
    "listbox": "listbox",
    "scrollbar": "scrollbar",
    "msctls_trackbar32": "slider",
    "msctls_progress32": "progressbar",
    "systreeview32": "treeview",
    "syslistview32": "listview",
    "systabcontrol32": "tab",
    "toolbarwindow32": "toolbar",
    "msctls_statusbar32": "statusbar",
}

# Button sub-types (from BS_* style bits)
_BUTTON_SUBTYPES = {
    BS_PUSHBUTTON: "pushbutton",
    BS_CHECKBOX: "checkbox",
    BS_AUTOCHECKBOX: "checkbox",
    BS_RADIOBUTTON: "radio",
    BS_AUTORADIOBUTTON: "radio",
    BS_GROUPBOX: "groupbox",
}

# ── Win32 function bindings ────────────────────────────────
_user32 = ctypes.windll.user32

_EnumChildWindows = _user32.EnumChildWindows
_SendMessageW = _user32.SendMessageW
_GetClassNameW = _user32.GetClassNameW
_GetWindowLongW = _user32.GetWindowLongW
_IsWindowVisible = _user32.IsWindowVisible
_IsWindowEnabled = _user32.IsWindowEnabled
_GetWindowRect = _user32.GetWindowRect

# Callback type for EnumChildWindows
WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)


def _get_window_text(hwnd: int) -> str:
    """Get the text of a window control via WM_GETTEXT (Unicode-safe)."""
    length = _SendMessageW(hwnd, WM_GETTEXTLENGTH, 0, 0)
    if length <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    _SendMessageW(hwnd, WM_GETTEXT, length + 1, buf)
    return buf.value


def _get_class_name(hwnd: int) -> str:
    """Get the window class name (e.g., 'Button', 'Static', 'Edit')."""
    buf = ctypes.create_unicode_buffer(256)
    _GetClassNameW(hwnd, buf, 256)
    return buf.value


def _get_control_rect(hwnd: int) -> dict[str, int]:
    """Get the bounding rectangle of a control in screen coordinates."""
    rect = ctypes.wintypes.RECT()
    _GetWindowRect(hwnd, ctypes.byref(rect))
    return {
        "left": rect.left,
        "top": rect.top,
        "right": rect.right,
        "bottom": rect.bottom,
    }


def _classify_control(class_name: str, style: int) -> str:
    """Determine the control type from class name and style bits."""
    cls_lower = class_name.lower()
    base_type = _CLASS_TYPE_MAP.get(cls_lower)

    if base_type == "button":
        # Refine button type from style bits
        button_type = style & 0x000F  # Lower nibble = button type
        return _BUTTON_SUBTYPES.get(button_type, "button")

    return base_type or cls_lower


def find_win32_controls(
    hwnd: int,
    *,
    name_filter: str | None = None,
    control_type: str | None = None,
    visible_only: bool = True,
) -> list[dict[str, Any]]:
    """Enumerate child controls of a window using Win32 EnumChildWindows.

    Args:
        hwnd: Parent window handle.
        name_filter: Case-insensitive substring to match control text.
        control_type: Filter by type ('button', 'checkbox', 'radio', 'label', etc.).
        visible_only: If True (default), skip invisible controls.

    Returns:
        List of control info dicts with: hwnd, text, class_name, control_type,
        control_id, rect, center, enabled, visible.
    """
    controls: list[dict[str, Any]] = []

    def _enum_callback(child_hwnd: int, _lparam: int) -> bool:
        visible = bool(_IsWindowVisible(child_hwnd))
        if visible_only and not visible:
            return True  # skip, continue enumeration

        text = _get_window_text(child_hwnd)
        class_name = _get_class_name(child_hwnd)
        style = _GetWindowLongW(child_hwnd, GWL_STYLE)
        ctrl_type = _classify_control(class_name, style)

        # Apply filters
        if name_filter and name_filter.lower() not in text.lower():
            return True
        if control_type and control_type.lower() != ctrl_type.lower():
            return True

        control_id = _GetWindowLongW(child_hwnd, GWL_ID)
        rect = _get_control_rect(child_hwnd)
        center_x = (rect["left"] + rect["right"]) // 2
        center_y = (rect["top"] + rect["bottom"]) // 2

        controls.append({
            "hwnd": child_hwnd,
            "text": text,
            "class_name": class_name,
            "control_type": ctrl_type,
            "control_id": control_id,
            "rect": rect,
            "center": {"x": center_x, "y": center_y},
            "enabled": bool(_IsWindowEnabled(child_hwnd)),
            "visible": visible,
        })
        return True  # continue enumeration

    callback = WNDENUMPROC(_enum_callback)
    _EnumChildWindows(hwnd, callback, 0)
    return controls


def click_win32_control(hwnd: int) -> bool:
    """Click a Win32 control via BM_CLICK message (no coordinates needed).

    This sends BM_CLICK directly to the control's window handle. The control
    processes the message as if the user clicked it — works for buttons,
    checkboxes, radio buttons. Returns True on success.

    Note: This does NOT move the mouse cursor. It's a message-based click.
    """
    try:
        _SendMessageW(hwnd, BM_CLICK, 0, 0)
        return True
    except Exception:
        return False


def find_window_by_title(title: str) -> int | None:
    """Find a top-level window by title substring, returning its hwnd.

    Uses EnumWindows + case-insensitive substring match.
    Returns the first match, or None if not found.
    """
    result: list[int] = []

    def _callback(hwnd: int, _lparam: int) -> bool:
        if not _IsWindowVisible(hwnd):
            return True
        text = _get_window_text(hwnd)
        if text and title.lower() in text.lower():
            result.append(hwnd)
            return False  # found — stop enumeration
        return True

    callback = WNDENUMPROC(_callback)
    _user32.EnumWindows(callback, 0)
    return result[0] if result else None
